#!/usr/bin/env python 

import usb
import time
import threading
import signal

class DeviceProxy():

    def __init__(self, vendor_id, product_id, interface_id, input_endpoint_address, output_endpoint_address):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.interface_id = interface_id
        self.input_endpoint_address = input_endpoint_address
        self.output_endpoint_address = output_endpoint_address
        self.dev = None
        self.input_endpoint = None
        self.output_endpoint = None
        self.reattach = False
        self.mode = None
        self.waiting = False
        self.result = None

    def __enter__(self):
        self.dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)

        if self.dev is None:
            print 'Device is not found.'
            raise ValueError('Device not found.')
        print 'Device is found.'

        if self.dev.is_kernel_driver_active(self.interface_id):
            self.reattach = True
            print 'Kernel driver is active. Detach kernel driver.'
            self.dev.detach_kernel_driver(self.interface_id)
        
        # Reset the device.
        self.dev.reset()

        config = self.dev.get_active_configuration()
        at_interface = config[(self.interface_id, 0)]

        self.input_endpoint = usb.util.find_descriptor(
            at_interface,
            custom_match = lambda e: e.bEndpointAddress == self.input_endpoint_address
        )

        print 'input endpoint:'
        print self.input_endpoint

        self.output_endpoint = usb.util.find_descriptor(
            at_interface,
            custom_match = lambda e: e.bEndpointAddress == self.output_endpoint_address
        )
        print 'output endpoint:'
        print self.output_endpoint

        self.listener_thread = ListenerThread(self.input_endpoint, self.handle_incoming_message)
        self.listener_thread.start()

        print 'Device initialized.\n' + '=' * 50

        return self

    def __exit__(self, type, value, traceback):
        self.listener_thread.stop()
        self.listener_thread.join()

        usb.util.dispose_resources(self.dev)

        # We always re-attach kernel driver for now.
        if self.reattach or True:
            print 'Reattach kernel driver.'
            try:
                self.dev.attach_kernel_driver(self.interface_id)
            except Exception as ex:
                print 'Reattach kernel driver error:', ex

        print 'Exit.'

    def send_command(self, command):
        print 'Sending command [%s]' % (command.strip())
        try:
            self.output_endpoint.write(command.encode('ascii'))
        except Exception as ex:
            print 'write exception:', ex
        
    def execute_mode(self, mode, command):
        self.mode = mode
        self.waiting = True
        self.send_command(command)
        while self.waiting:
            time.sleep(1)
        return self.result
        
    def handle_incoming_message(self, message):
        if message == '>' and not self.sending_text:
            # the current state of the device is wrong. terminate the current text sending.
            self.send_command('\x1a')
            
        if self.mode == 'CheckOk':
            if message == 'OK':
                self.waiting = False
                self.result = True
            elif message == 'ERROR':
                self.waiting = False
                self.result = False
        elif self.mode == 'IncludeOk':
            if 'OK' in message:
                self.waiting = False
        elif self.mode == 'WaitForInput':
            if message == '>':
                self.waiting = False
        elif self.mode == 'AnyMessage':
            self.waiting = False
    
    def set_text_sending_status(self, status):
        print 'Text sending mode: %s' % status
        self.sending_text = status

    def check_device_status(self):
        print 'Performing device health check.'
        result = self.execute_mode('CheckOk', 'AT\r')
        if result:
            print 'Device is OK.'
        else:
            print 'Device status error.'
        return result

    def check_signal(self):
        print 'Check signal.'
        self.execute_mode('IncludeOk', 'AT+CSQ\r')
    
    def send_message(self, number, message):
        print 'Step 1, Health check.'
        mode_ok = self.execute_mode('CheckOk', 'AT+CMGS=?\r')
        if not mode_ok:
            return False
        print 'Step 2, Set SMS mode to TEXT.'
        self.execute_mode('CheckOk', 'AT+CMGF=1\r')
        print 'Step 3, Set GSM character set.'
        self.execute_mode('CheckOk', 'AT+CSCS="GSM"\r')
        print 'Step 4, Set Number.'
        self.set_text_sending_status(True)
        self.execute_mode('WaitForInput', 'AT+CMGS="%s"\r' % number)
        print 'Step 5, Send Message.'
        self.execute_mode('IncludeOk', "%s\x1a" % message)
        self.set_text_sending_status(False)
        return True
    
    def read_messages(self):
        print 'Step 1, Set SMS mode text.'
        self.execute_mode('CheckOk', 'AT+CMGF=1\r')
        print 'Step 2, Set GSM character set.'
        self.execute_mode('CheckOk', 'AT+CSCS="GSM"\r')
        print 'Step 3, Check Self Number'
        self.execute_mode('IncludeOk', 'AT+CNUM\r')
        print 'Step 4, Check Message List'
        self.execute_mode('CheckOk', 'AT+CMGL="ALL"\r')
        print 'Step 5, Read SMS'
        self.execute_mode('CheckOk', 'AT+CMGR=1')
        # print 'Delete Read Messages.'
        # self.execute_mode('IncludeOk', 'AT+CMGD=1\r')


class ListenerThread(threading.Thread):

    def __init__(self, input_endpoint, message_handler):
        super(ListenerThread, self).__init__()
        self.should_stop = False
        self.input_endpoint = input_endpoint
        self.message_handler = message_handler

    def run(self):
        # The device may take some time to be ready.
        # So we just sleep for 1s.
        time.sleep(1)
        counter = 1
        while not self.should_stop:
            try:
                response = self.input_endpoint.read(self.input_endpoint.wMaxPacketSize)
                ascii_response = ''.join([chr(c) for c in response])
                ascii_response = ascii_response.strip()
                print '[%s] Receive From Device:' % counter
                print '[%s] [Raw]' % counter, response
                print '[%s] [ASCII]' % counter, ascii_response
                self.message_handler(ascii_response)
                counter += 1
                time.sleep(1)
            except usb.core.USBError as ex:
                if ex.strerror != 'Operation timed out':
                    print 'listener thread error:', ex
    
    def stop(self):
        print 'Stopping the listener thread.'
        self.should_stop = True
