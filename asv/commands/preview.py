# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from six.moves import SimpleHTTPServer, socketserver

import errno
import os
import random
import socket

from . import Command

from ..console import log
from .. import util


def random_ports(port, n):
    """Generate a list of n random ports near the given port.

    The first 5 ports will be sequential, and the remaining n-5 will be
    randomly selected in the range [port-2*n, port+2*n].
    """
    if port != 0:
        yield port
    else:
        port = 8080
        for i in range(min(5, n)):
            yield port + i
        for i in range(n-5):
            yield max(1, port + random.randint(-2*n, 2*n))


def create_httpd(handler_cls, port=0):
    # Create a server that allows address reuse
    class MyTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    for port in random_ports(port, 5):
        try:
            httpd = MyTCPServer(("", port), handler_cls)
            base_url = "http://127.0.0.1:{0}/".format(port)
            break
        except socket.error as e:
            if e.errno == errno.EADDRINUSE:
                continue
            else:
                raise
    else:
        raise util.UserError("Failed to find an unused port for "
                             "serving web pages")

    return httpd, base_url


class Preview(Command):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "preview",
            help="Preview the results using a local web server",
            description="Preview the results using a local web server")

        parser.add_argument("--port", "-p", type=int, default=0,
                            help="Port to run webserver on.  [8080]")
        parser.add_argument("--browser", "-b", action="store_true",
                            help="Open in webbrowser")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(conf=conf, port=args.port,
                       browser=args.browser)

    @classmethod
    def run(cls, conf, port=0, browser=False):
        os.chdir(conf.html_dir)

        Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
        httpd, base_url = create_httpd(Handler, port=port)

        log.info("Serving at {0}".format(base_url))

        if browser:
            import webbrowser
            webbrowser.open(base_url)

        log.info("Press ^C to abort")
        httpd.serve_forever()
