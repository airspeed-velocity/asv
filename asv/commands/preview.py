# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from six.moves import SimpleHTTPServer, socketserver

import os

from ..config import Config
from ..console import console


class Preview(object):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "preview",
            help="Preview the results using a local web server",
            description="Preview the results using a local web server")

        parser.add_argument("--port", "-p", type=int, default=8080,
                            help="Port to run webserver on.  [8080]")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_args(cls, args):
        return cls.run(conf=Config.load(args.config), port=args.port)

    @classmethod
    def run(cls, conf, port=8080):
        os.chdir(conf.html_dir)

        Handler = SimpleHTTPServer.SimpleHTTPRequestHandler

        # Create a server that allows address reuse
        class MyTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        httpd = MyTCPServer(("", port), Handler)

        console.message(
            "Serving at http://127.0.0.1:{0}/".format(port), "green")
        console.message("Press ^C to abort")
        httpd.serve_forever()
