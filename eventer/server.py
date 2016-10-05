import os.path

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.log

from eventer.handlers.ui import IndexHandler, DocumentationHandler, LoginHandler, RegisterHandler
from eventer.handlers.endpoints import RegisterEndpointHandler


def make_app(settings):
    return tornado.web.Application([
        # html routes
        (r'/', IndexHandler),
        (r'/doc', DocumentationHandler),
        (r'/login', LoginHandler),
        (r'/register', RegisterHandler),

        # endpoints
        (r'/endpoint/register', RegisterEndpointHandler),

        # static routes
        (r'/static/(.*)', tornado.web.StaticFileHandler),

        # api routes
    ], **settings)


if __name__ == '__main__':
    settings = {
        "static_path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
        "template_path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"),
        "cookie_secret": "!$FF#@T&%NRfWG%$h6J45t2#!deDSBn7j5^g43dQWadFDBn7^7%$r",
        "xsrf_cookies": True,
    }
    tornado.log.enable_pretty_logging()

    server = tornado.httpserver.HTTPServer(make_app(settings))
    server.bind(8888)
    server.start()
    tornado.ioloop.IOLoop.current().start()