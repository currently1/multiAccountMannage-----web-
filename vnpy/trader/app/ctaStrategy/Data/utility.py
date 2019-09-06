# encoding: utf-8

import os
import json
import math
import time

#from .event import Event, EVENT_LOG, EVENT_ERROR
#from .generalObject import ErrorData, LogData

def convert_file_to_dict(file_location):
    with open(file_location) as f:
        _dict = json.load(f)
    return _dict

def get_temp_path(file_name):
    temp_path = os.path.join(os.getcwd(), 'temp')
    if not os.path.exists(temp_path):
        os.makedirs(temp_path)

    file_location = os.path.join(temp_path, file_name)
    return file_location

def floor_price(tick_size, price):
    new_price = math.floor(price/tick_size) * tick_size
    return new_price

def ceil_price(tick_size, price):
    new_price = math.ceil(price/tick_size) * tick_size
    return new_price



def check_time(time_range):
    '''check if in the given time ranges, regardless the day'''
    _now_string = time.strftime("%H:%M:%S", time.localtime())
    _now_time = time.strptime(_now_string, "%H:%M:%S")
    in_time_range = any(
        v[0] <= _now_time <= v[1]
        for v in time_range)
    if in_time_range:
        return True
    else:
        return False
