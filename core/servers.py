from anthill.framework.core.exceptions import ImproperlyConfigured
from anthill.framework.utils.module_loading import import_string
from tornado.web import Application as TornadoWebApplication
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from tornado.netutil import bind_unix_socket
import signal
import logging
import sys

logger = logging.getLogger('anthill.application')


class BaseService(TornadoWebApplication):
    server_class = HTTPServer

    def __init__(self, handlers=None, default_host=None, transforms=None, app=None, **kwargs):
        kwargs.update(debug=app.debug)
        kwargs.update(compress_response=app.settings.COMPRESS_RESPONSE)

        self.setup_static(app, kwargs)

        static_handler_class = getattr(
            app.settings, 'STATIC_HANDLER_CLASS', 'anthill.framework.handlers.StaticFileHandler')
        kwargs.update(static_handler_class=import_string(static_handler_class))

        transforms = transforms or list(map(import_string, app.settings.OUTPUT_TRANSFORMS or []))
        super().__init__(handlers, default_host, transforms, **kwargs)

        self.io_loop = IOLoop.current()
        self.app = app

        self.config = app.settings
        self.name = app.label
        self.db = app.db
        self.version = app.version
        self.debug = app.debug

        self.setup()

    # noinspection PyMethodMayBeStatic
    def setup_static(self, app, kwargs):
        kwargs.update(static_path=app.settings.STATIC_PATH)
        kwargs.update(static_url_prefix=app.settings.STATIC_URL)

    def setup(self):
        # Override `io_loop.handle_callback_exception` method to catch exceptions globally.
        self.io_loop.handle_callback_exception = self.__io_loop_handle_callback_exception__

        self.add_handlers(self.app.host_regex, self.app.routes)
        logger.debug('Service routes installed.')

        self.settings.update(cookie_secret=self.config.SECRET_KEY)
        self.settings.update(xsrf_cookies=self.config.CSRF_COOKIES)
        self.settings.update(template_path=self.config.TEMPLATE_PATH)
        self.settings.update(login_url=self.config.LOGIN_URL)

        default_handler_class = getattr(
            self.config, 'DEFAULT_HANDLER_CLASS', 'anthill.framework.handlers.Handler404')
        if default_handler_class is not None:
            self.settings.update(default_handler_class=import_string(default_handler_class))
            self.settings.update(default_handler_args=self.config.DEFAULT_HANDLER_ARGS)

        # template_loader_class = getattr(
        #     self.app.settings, 'TEMPLATE_LOADER_CLASS', 'anthill.framework.core.template.Loader')
        # template_loader_kwargs = dict()
        # if "autoescape" in self.settings:
        #     # autoescape=None means "no escaping", so we have to be sure
        #     # to only pass this kwarg if the user asked for it.
        #     template_loader_kwargs["autoescape"] = self.settings["autoescape"]
        # if "template_whitespace" in self.settings:
        #     template_loader_kwargs["whitespace"] = self.settings["template_whitespace"]
        # template_loader = import_string(template_loader_class)(
        #     self.app.settings.TEMPLATE_PATH, **template_loader_kwargs)
        # self.settings.update(template_loader=template_loader)
        # logger.debug('Template loader `%s` installed.' % template_loader_class)

        self._load_ui_modules(self.app.ui_modules)
        self._load_ui_methods(self.app.ui_modules)
        logger.debug('Service ui modules loaded.')

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.app.name)

    def __sig_handler__(self, sig, frame):
        logger.warning('Caught signal: %s', sig)
        self.io_loop.add_callback(self.stop)

    # noinspection PyMethodMayBeStatic
    def __io_loop_handle_callback_exception__(self, callback):
        """
        Shortcut for `self.io_loop.handle_callback_exception`.
        This method is called whenever a callback run by the `IOLoop`
        throws an exception.

        The exception itself is not passed explicitly, but is available
        in `sys.exc_info`.
        """
        logger.exception("Exception in callback %r", callback)
        logging.getLogger('anthill').exception(str(sys.exc_info()[1]))

    @property
    def server(self):
        """Returns an instance of server class ``self.server_class``."""
        return self.server_class(self, **self.get_server_kwargs())

    def get_server_kwargs(self):
        kwargs = {
            'no_keep_alive': False,
            'xheaders': False,
            'ssl_options': None,
            'protocol': None,
            'decompress_request': False,
            'chunk_size': None,
            'max_header_size': None,
            'idle_connection_timeout': None,
            'body_timeout': None,
            'max_body_size': self.config.FILE_UPLOAD_MAX_BODY_SIZE,
            'max_buffer_size': None,
            'trusted_downstream': None
        }

        # HTTPS supporting
        https_config = getattr(self.config, 'HTTPS', None)
        if self.app.https_enabled and https_config is not None:
            if not all(['key_file' in https_config, https_config['key_file']]):
                raise ImproperlyConfigured('Key file not configured')
            if not all(['crt_file' in https_config, https_config['crt_file']]):
                raise ImproperlyConfigured('Crt file not configured')

            import ssl

            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain(
                https_config['crt_file'], https_config['key_file'])
            kwargs.update(ssl_options=ssl_ctx)
            logger.debug('HTTPS status: ON.')
        else:
            logger.warning('HTTPS status: OFF.')

        return kwargs

    def setup_server(self, **kwargs):
        if self.config.UNIX_SOCKET is not None:
            socket = bind_unix_socket(self.config.UNIX_SOCKET)
            self.server.add_socket(socket)
        else:
            self.server.listen(self.app.port, self.app.host)
        for s in ('SIGTERM', 'SIGHUP', 'SIGINT'):
            signal.signal(getattr(signal, s), self.__sig_handler__)

    def start(self, **kwargs):
        """Start server."""
        self.setup_server(**kwargs)
        self.io_loop.add_callback(self.on_start)
        self.io_loop.start()

    def stop(self):
        """Stop server."""
        if self.server:
            self.io_loop.add_callback(self.on_stop)
            self.io_loop.stop()

    async def on_start(self):
        raise NotImplementedError

    async def on_stop(self):
        raise NotImplementedError
