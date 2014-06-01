# -*- mode: Python -*-
# You can run this .tac file directly with:
#    twistd -ny service.tac

"""
"""

import os
from twisted.application import service, internet
from twisted.web import static, server
from snappy import webserver

def getWebService():
    # create a resource to serve static files
    snappyserver= server.Site(webserver.SnappySite())
    return internet.TCPServer(8888, snappyserver)

# this is the core part of any tac file, the creation of the root-level
# application object
application = service.Application("Snappy Server")

# attach the service to its parent application
service = getWebService()
service.setServiceParent(application)
