#!/usr/bin/env python 

import time

from device_proxy import DeviceProxy

VENDOR_ID = 0x1e0e
PRODUCT_ID = 0x9001
# AT_INTERFACE_ID = 0
# AT_ENDPOINT_IN_ADDRESS = 0x81
# AT_INTERFACE_ID = 1  # Seems Network Related
# AT_ENDPOINT_IN_ADDRESS = 0x82
# AT_ENDPOINT_IN_ADDRESS = 0x83  # Seems Network Related
AT_INTERFACE_ID = 2
AT_ENDPOINT_IN_ADDRESS = 0x84
AT_ENDPOINT_OUT_ADDRESS = 0x3

with DeviceProxy(VENDOR_ID, PRODUCT_ID, AT_INTERFACE_ID, AT_ENDPOINT_IN_ADDRESS, AT_ENDPOINT_OUT_ADDRESS) as device_proxy:
    device_proxy.add_message_to_wait('OK')
    device_proxy.send_command('AT\r')
    device_proxy.wait_for_all_messages()

    device_proxy.add_message_to_wait('OK')
    device_proxy.send_command('AT+CMGS=?\r')
    device_proxy.wait_for_all_messages()

    device_proxy.add_message_to_wait('OK')
    device_proxy.send_command('AT+CMGF=1\r')
    device_proxy.wait_for_all_messages()

    number = '+6584389984'
    message = 'Test Message.'
    # number = '+6582296036'
    # message = 'Hello from ZXZ\'s crazy 4G driver.'

    device_proxy.set_text_sending_status(True)
    device_proxy.add_message_to_wait('>')
    device_proxy.send_command('AT+CMGS="%s"\r' % number)
    device_proxy.wait_for_all_messages()

    device_proxy.add_message_to_wait('OK')
    device_proxy.send_command("%s\x1a" % message)
    device_proxy.wait_for_all_messages()
    device_proxy.set_text_sending_status(False)
