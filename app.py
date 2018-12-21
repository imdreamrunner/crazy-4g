#!/usr/bin/env python 

import time
import sys

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
    device_ok = device_proxy.check_device_status()

    if not device_ok:
        sys.exit(1)

    device_proxy.check_signal()
    device_proxy.check_carrier()

    while True:
        command = raw_input('Command (send_sms, read_sms, q): ')

        if command == 'send_sms':
            number = '+6584389984'
            message = 'Test Message.'
            device_proxy.send_message(number, message)
        elif command = 'read_sms':
            device_proxy.read_messages()
        else:
            break

