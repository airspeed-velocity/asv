# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import SimpleHTTPServer
import SocketServer
import os

from ..config import Config
from ..console import console


class Preview(object):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "preview", help="Preview the results in a simple web server")

        parser.add_argument("--port", "-p", type=int, default=8080,
                            help="Port to run webserver on")

        parser.set_defaults(func=cls.run)

    @classmethod
    def run(cls, args):
        conf = Config.from_file(args.config)

        os.chdir(conf.html_dir)

        port = args.port

        Handler = SimpleHTTPServer.SimpleHTTPRequestHandler

        # Create a server that allows address reuse
        class MyTCPServer(SocketServer.TCPServer):
            allow_reuse_address = True

        httpd = MyTCPServer(("", port), Handler)

        console.message(
            "Serving at http://127.0.0.1:{0}/".format(port), "green")
        console.message("Press ^C to abort")
        httpd.serve_forever()
