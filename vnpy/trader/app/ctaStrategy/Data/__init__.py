# encoding: utf-8

import os

from utility import convert_file_to_dict

current_path = os.path.abspath(os.path.dirname(__file__))


# gateway
Param_Setting_name = 'Param_Setting.json'
Param_setting_location = os.path.join(current_path, Param_Setting_name)
Param_setting_dict = convert_file_to_dict(Param_setting_location)



__all__ = [
    Param_setting_dict
  
]
