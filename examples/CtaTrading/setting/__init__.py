# encoding: utf-8

import os

from utility import convert_file_to_dict

current_path = os.path.abspath(os.path.dirname(__file__))


# gateway
gateway_setting_name = 'gateway_setting.json'
gateway_setting_location = os.path.join(current_path, gateway_setting_name)
gateway_setting_dict = convert_file_to_dict(gateway_setting_location)



__all__ = [
    gateway_setting_dict

]
