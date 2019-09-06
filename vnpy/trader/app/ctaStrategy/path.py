# encoding: UTF-8

import os
import sys

# 将根目录路径添加到环境变量中
ROOT_PATH =os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))
sys.path.append(ROOT_PATH)



