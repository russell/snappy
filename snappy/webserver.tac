# -*- mode: Python -*-
# You can run this .tac file directly with:
#    twistd -ny webserver.tac

"""
"""

from twisted.application import service, internet
from twisted.web import server
from snappy import webserver

# this is the core part of any tac file, the creation of the root-level
# application object
application = service.Application("Snappy Server")

snappy = webserver.SnapServer()
serviceCollection = service.IServiceCollection(application)
snappy.setServiceParent(serviceCollection)
internet.TCPServer(8888, server.Site(snappy.getResource())
                   ).setServiceParent(serviceCollection)
