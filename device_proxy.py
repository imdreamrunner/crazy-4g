#!/usr/bin/env python 

import usb
import time
import threading
import signal
import enum


class CommandType(enum.Enum):
    CHECK_OK = 1
    INCLUDE_OK = 2
    WAIT_FOR_INPUT_MODE = 3


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
        self.auto_accept_call = True  # TODO: Add configuration.
        self.buffer_messages = []

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
        
    def execute_command(self, mode, command):
        self.mode = mode
        self.waiting = True
        self.send_command(command)
        self.result = None
        self.buffer_messages = []

        while self.waiting:
            time.sleep(1)

        if self.result is not None:
            return self.result
        return self.buffer_messages
        
    def handle_incoming_message(self, message):
        if message == '>' and not self.sending_text:
            # the current state of the device is wrong. terminate the current text sending.
            self.send_command('\x1a')

        if message == 'RING':
            # Phone call related message, handle differently.
            if self.auto_accept_call:
                self.send_command("ATA\r")
                time.sleep(1)
                self.send_command('AT+CHUP\r')
            return
            
        self.buffer_messages.append(message)

        if self.mode == CommandType.CHECK_OK:
            if message == 'OK':
                self.waiting = False
                self.result = True
            elif message == 'ERROR':
                self.waiting = False
                self.result = False
        elif self.mode == CommandType.INCLUDE_OK:
            if 'OK' in message:
                self.waiting = False
        elif self.mode == CommandType.WAIT_FOR_INPUT_MODE:
            if message == '>':
                self.waiting = False
    
    def set_text_sending_status(self, status):
        print 'Text sending mode: %s' % status
        self.sending_text = status

    def check_device_status(self):
        print 'Performing device health check.'
        result = self.execute_command(CommandType.CHECK_OK, 'AT\r')
        if result:
            print 'Device is OK.'
        else:
            print 'Device status error.'
        return result

    def check_signal(self):
        print 'Check signal.'
        self.execute_command(CommandType.INCLUDE_OK, 'AT+CSQ\r')
    
    def check_carrier(self):
        print 'Check carrier.'
        # Automatic Mode
        self.execute_command(CommandType.INCLUDE_OK, 'AT+CNMP=2\r')
        # Selet Network
        # self.execute_command(CommandType.INCLUDE_OK, 'AT+COPS=0\r')  # Auto Mode
        self.execute_command(CommandType.INCLUDE_OK, 'AT+COPS?\r')
        self.execute_command(CommandType.INCLUDE_OK, 'AT+COPS=?\r')
        self.execute_command(CommandType.INCLUDE_OK, 'AT+COPS=1,0,"SGP-M1"\r') # Select SGP-M1 M1 52503
    
    def send_message(self, number, message):
        print 'Step 1, Health check.'
        mode_ok = self.execute_command(CommandType.CHECK_OK, 'AT+CMGS=?\r')
        if not mode_ok:
            return False
        print 'Step 2, Set SMS mode to TEXT.'
        self.execute_command(CommandType.CHECK_OK, 'AT+CMGF=1\r')
        print 'Step 3, Set GSM character set.'
        self.execute_command(CommandType.CHECK_OK, 'AT+CSCS="GSM"\r')
        print 'Step 4, Set Number.'
        self.set_text_sending_status(True)
        self.execute_command(CommandType.WAIT_FOR_INPUT_MODE, 'AT+CMGS="%s"\r' % number)
        print 'Step 5, Send Message.'
        self.execute_command(CommandType.INCLUDE_OK, "%s\x1a" % message)
        self.set_text_sending_status(False)
        return True
    
    def read_messages(self):
        print 'Step 1, Set SMS mode text.'
        self.execute_command(CommandType.CHECK_OK, 'AT+CMGF=1\r')
        print 'Step 2, Set GSM character set.'
        self.execute_command(CommandType.CHECK_OK, 'AT+CSCS="GSM"\r')
        print 'Step 3, Check Self Number'
        self.execute_command(CommandType.INCLUDE_OK, 'AT+CNUM\r')
        print 'Step 4, Set Receive Message'
        self.execute_command(CommandType.CHECK_OK, 'AT+CNMI=2,0\r')
        print 'Step 5, Check storage'
        self.execute_command(CommandType.INCLUDE_OK, 'AT+CPMS?\r')
        print 'Step 6, Check Message List'
        response = self.execute_command(CommandType.INCLUDE_OK, 'AT+CMGL="ALL"\r')
        raw_sms_response = response[1].split('\r\n')
        assert raw_sms_response[-1].strip() == 'OK'
        raw_sms_response = raw_sms_response[:-2] # remove empty line and OK
        sms_list = []
        for line in raw_sms_response:
            line = line.strip()
            if line[:7] == '+CMGL: ':
                sms_list.append({
                    'meta': line,
                    'content': ''
                })
            else:
                sms_list[-1]['content'] += '\n' + line if len(sms_list[-1]['content']) > 0 else line

        for sms in sms_list:
            self.process_sms_meta(sms)

        # delete SMS
        for sms in sms_list:
            self.execute_command(CommandType.INCLUDE_OK, 'AT+CMGD=%s\r' % sms['index'])

        return sms_list
        # print 'Step 7, Read SMS'
        # for i in range(1, 35):
        #     self.execute_command(CommandType.CHECK_OK, 'AT+CMGR=%s\r' % i)
        # print 'Delete Read Messages.'
        # self.execute_command(CommandType.INCLUDE_OK, 'AT+CMGD=1\r')

    @staticmethod
    def process_sms_meta(sms):
        meta = sms['meta']
        meta = meta[7:]
        meta_splits = meta.split(',')
        sms['index'] = int(meta_splits[0])

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
