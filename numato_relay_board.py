#! /usr/bin/env python
# -*- coding: utf-8 -*-

""" A control script for numato brand USB relay board.

This script is only designed to work with windows, and only tested on
Windows 10. Device driver is assumed installed properly by the OS/user.

Only requires default Python3 library serial

Product page:
https://numato.com/product/16-channel-usb-relay-module


Tested Part Numbers:

RL160001 (16 Relay Module)

"""

import serial


class RelayBoard(object):
    """ The usb relay board class. Should be able to use multiple devices
        simultaniously as long as different COM ports are defined.
    """
    number_of_relays = 0
    port_name = ''
    device = ''
    connected = False

    def __init__(self, port_name, number_of_relays):
        """
        Example: A 16 relay board installed on COM6

        b1 = n.RelayBoard('COM6', 16)

        :param port_name:
        :param number_of_relays:
        """
        self.number_of_relays = number_of_relays
        self.port_name = port_name
        try:
            self.device = serial.Serial(port_name.upper(), 19200, timeout=1)
            self.connected = True
        except Exception as _:
            print('Failed to connect to given COM port')

    def close_port(self):
        """ Closes the connection to the COM port. Good house keeping to close
            this connection when completed.
        :return:
        """
        self.device.close()

    def get_device_name(self):
        """ Gets the current programmed device name. This is device limited
            to 8 characters.
        :return:
        """
        _ = self.device.write(bytes('id get\r', 'utf-8'))
        response = self.device.read(100)
        response = str(response, 'utf-8').split('\r')[1].strip('\n')
        return response

    def set_device_name(self, name):
        """ Sets the device name in device memory. Device name must be
            alphanumeric and will be 0 left padded to reach 8 character
            size requirement. Function will also strip any punctuation and
            escape characters.
        :param name:
        :return:
        """
        name = "".join(x for x in name if 48 <= ord(x) <= 121)
        name = "".join(x for x in name if x.isalnum())
        name = name.zfill(8)
        name = name[:8]
        _ = self.device.write(bytes('id set %s\r' % name, 'utf-8'))
        _ = self.device.read(100)

    def clear_buffer(self, retry_limit=10):
        """ Will read from the buffer until it reads a blank buffer or has hit
            the given number of retries. Will read off 50 bits at a time.
            Returns a boolean for buffer cleared status.
        :return:
        """
        blank_buffer = False
        retry_count = 0
        while not blank_buffer:
            response = self.device.read(50)
            response = str(response, 'utf-8')
            retry_count += 1
            if len(response) == 0:
                blank_buffer = True
                break
            if retry_count > retry_limit:
                blank_buffer = False
                break
        return blank_buffer

    def read_gpio(self, port):
        """ Returns the digital status of a given GPIO pin. See device
            documentation for pin mapping. Returns a boolean value for
            selected pin status.

            Example usage:
            self.read_gpio(0)   #Returns the state of GPIO 0
            self.read_gpio(10)  #Throws an exception for bad GPIO port
        :param port:
        :return:
        """
        port = int(port)
        assert 0 <= port < 10, 'Invalid GPIO Port'
        _ = self.device.write(bytes('gpio read %s\n\r' % port, 'utf-8'))
        response = self.device.read(100)
        response = str(response, 'utf-8').split('\n')[2]
        return bool(int(response.strip('\r')))

    def set_gpio(self, port, status):
        """ Sets the GPIO pin status to high or low. Per the documentation, a
            series resistor is recommended to current limit the outputs.
            Pins support 2 to 8 mA depending on the port.
        :param port:
        :param status:
        :return:
        """
        port = int(port)
        assert 0 <= port < 10, 'Invalid GPIO Port'
        if status:
            cmd_string = 'gpio set %s \r' % port
        else:
            cmd_string = 'gpio clear %s \r' % port
        _ = self.device.write(bytes(cmd_string, 'utf-8'))
        # Read just to keep the buffer clean
        _ = self.device.read(50)

    def get_adc(self, port, raw=True):
        """ Returns the ADC value for the given ADC channel. If raw is True,
            returned value will be raw decimal ADC (based on 10bits). If raw
            is False, returned value will be the calculated floating point
            voltage of the ADC pin.
        :param port:
        :param raw:
        :return:
        """
        port = int(port)
        assert 0 <= port < 5, 'Invalid ADC Port'
        _ = self.device.write(bytes('adc read %s\r' % port, 'utf-8'))
        response = self.device.read(50)
        response = str(response, 'utf-8').split('\r')[1]
        response = int(response.strip('\n'))
        if not raw:
            response = (response/1023)*3.3
        return response

    def get_relay(self):
        """ Returns a list of current relay status. Will scale the returned
            list to the size of the connected relay board (passed by the user)
            during init.
        :return:
        """
        _ = self.device.write(bytes('relay readall\r', 'utf-8'))
        response = self.device.read(100)
        response = str(response, 'utf-8')
        response = int(response.split('\r')[1].strip('\n'), 16)
        relay_state = [(response & (2**x))//(2**x)
                       for x in range(self.number_of_relays)]
        return relay_state

    def set_relay(self, relay_vals):
        """ Set the state of relays. Input can either be a list of on off
        values or a hex value representing the desired state. Note, this will
        truncate your input state to match the number of relays initialized
        with.

        Example to turn arelay 0, 3, and 7 on
        set_relay(0x89)
        set_realy([1,0,0,1,0,0,0,1])

        :param relay_vals:
        :return:
        """
        assert type(relay_vals) != float, 'Relay setting can\'t be float'
        assert type(relay_vals) != str, 'Relay setting can\'t be string'
        if type(relay_vals) == int:
            # If input is an integer value (hex or decimal)
            relay_vals = hex(relay_vals)[2:]
            # Left pad with zeroes
            bits = self.number_of_relays//4
            relay_vals = relay_vals.zfill(bits)
        elif type(relay_vals) == list:
            temp_vals = 0
            if len(relay_vals) > 0:
                for val in range(len(relay_vals)):
                    if relay_vals[val] != 0:
                        temp_vals += 2**val
            else:
                temp_vals = 0
            temp_vals = hex(temp_vals)[2:]
            bits = self.number_of_relays//4
            relay_vals = temp_vals.zfill(bits)
        else:
            return False
        _ = self.device.write(bytes('relay writeall %s\r' % relay_vals,
                                    'utf-8'))
        _ = self.device.read(100)


def print_gpio_pins():
    """ Does a pretty print of the standard GPIO Pinout
    :return:
    """
    print('Pin ------ GPIO ------ ADC')
    print('1 --------- 0 --------- 0')
    print('2 --------- 1 --------- 1')
    print('3 --------- 2 --------- NA')
    print('4 --------- 3 --------- NA')
    print('5 --------- 4 --------- NA')
    print('6 --------- 5 --------- NA')
    print('7 --------- 6 --------- NA')
    print('8 --------- 7 --------- 2')
    print('9 --------- 8 --------- 3')
    print('10--------- 9 --------- 4')
