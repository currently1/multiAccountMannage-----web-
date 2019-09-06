#!/usr/bin/env python
# -*- coding: utf-8 -*-
from  tradeServer import wsgi_app
import logging

from wsgiref.simple_server import make_server

# configure the python logger to show debugging output
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('spyne.protocol.xml').setLevel(logging.DEBUG)

logging.info("listening to http://127.0.0.1:8000")
logging.info("wsdl is at: http://localhost:8000/?wsdl")

# step4:Deploying the service using Soap via Wsgi
# register the WSGI application as the handler to the wsgi server, and run the http server
server = make_server('127.0.0.1', 8000, wsgi_app)
server.serve_forever()