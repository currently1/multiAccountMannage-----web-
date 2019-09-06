#!/usr/bin/env python 
# -*- coding: utf-8 -*-
 
"""
preference:
    http://spyne.io/docs/2.10/index.html
    https://github.com/arskom/spyne/blob/master/examples/helloworld_soap.py
 
This is a simple HelloWorld example to show the basics of writing
a webservice using spyne, starting a server, and creating a service
client.
Here's how to call it using suds:
 
#>>> from suds.client import Client
#>>> hello_client = Client('http://localhost:8000/?wsdl')
#>>> hello_client.service.say_hello('punk', 5)
(stringArray){
   string[] =
      "Hello, punk",
      "Hello, punk",
      "Hello, punk",
      "Hello, punk",
      "Hello, punk",
 }
#>>>
 
"""
# Application is the glue between one or more service definitions, interface and protocol choices.
from spyne import Application
# @rpc decorator exposes methods as remote procedure calls
# and declares the data types it accepts and returns
from spyne import rpc
# spyne.service.ServiceBase is the base class for all service definitions.
from spyne import ServiceBase
# The names of the needed types for implementing this service should be self-explanatory.
from spyne import Iterable, Integer, Unicode
 
from spyne.protocol.soap import Soap11
# Our server is going to use HTTP as transport, It’s going to wrap the Application instance.
from spyne.server.wsgi import WsgiApplication
 
 
# step1: Defining a Spyne Service
class HelloWorldService(ServiceBase):
    @rpc(Unicode, Integer, _returns=Iterable(Unicode))
    def say_hello(self, name, times):
        """Docstrings for service methods appear as documentation in the wsdl.
        <b>What fun!</b>
        @param name: the name to say hello to
        @param times: the number of times to say hello
        @return  When returning an iterable, you can use any type of python iterable. Here, we chose to use generators.
        """
 
        for i in range(times):
            yield u'Hello, %s' % name
 
 
# step2: Glue the service definition, input and output protocols
soap_app = Application([HelloWorldService], 'spyne.examples.hello.soap',
                       in_protocol=Soap11(validator='lxml'),
                       out_protocol=Soap11())
 
# step3: Wrap the Spyne application with its wsgi wrapper
wsgi_app = WsgiApplication(soap_app)
 
if __name__ == '__main__':
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