#!/usr/bin/python3

import sys
from imutils.IocDockServer import IocDockServer

if __name__ == "__main__":
    if "--server" in sys.argv:
        IocDockServer = IocDockServer(with_cli=False, connection_debug=False, pull_interval=5)
    else:
        IocDockServer = IocDockServer(pull_interval=5)
    IocDockServer.run()
