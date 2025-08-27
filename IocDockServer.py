#!/usr/bin/python3

import sys
from imutils.IocDockServer import SocketServer

if __name__ == "__main__":
    if "--server" in sys.argv:
        IocDockServer = SocketServer(with_cli=False, connection_debug=False)
    else:
        IocDockServer = SocketServer()
    IocDockServer.run()
