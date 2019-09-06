#!/usr/bin/python
# coding:utf-8
from spyne import Integer, Unicode, Array, ComplexModel
class accountInfo(ComplexModel):
    strategy_name = Unicode
    account_ID  = Integer
    var_list = Unicode