# encoding: utf-8

import os
import json
import math
import time


def convert_file_to_dict(file_location):
    with open(file_location) as f:
        _dict = json.load(f)
    return _dict

