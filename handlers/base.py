from tornado.web import (
    RequestHandler as BaseRequestHandler,
    StaticFileHandler as BaseStaticFileHandler,
    HTTPError)
from tornado.websocket import WebSocketHandler as BaseWebSocketHandler
from anthill.framework.core.exceptions import ImproperlyConfigured
from anthill.framework.context_processors import build_context_from_context_processors
from anthill.framework.sessions.handlers import SessionHandlerMixin
from anthill.framework.utils.debug.report import ExceptionReporter
from anthill.framework.utils.format import bytes2human
from anthill.framework.utils.translation import default_locale
from anthill.framework.utils.module_loading import import_string
from anthill.framework.utils.urls import build_absolute_uri
from anthill.framework.utils.serializer import AlchemyJSONEncoder
from anthill.framework.http import HttpGoneError, Http404, HttpServerError
from anthill.framework.conf import settings
from tornado import httputil
import json
import logging
import os


class TranslationHandlerMixin:
    # noinspection PyMethodMayBeStatic
    def get_user_locale(self):
        """
        Override to determine the locale from the authenticated user.
        If None is returned, we fall back to `get_browser_locale()`.
        This method should return a `tornado.locale.Locale` object,
        most likely obtained via a call like ``tornado.locale.get("en")``
        """
        return default_locale()


class LogExceptionHandlerMixin:
    def log_exception(self, exc_type, exc_value, tb):
        # noinspection PyUnresolvedReferences
        super().log_exception(exc_type, exc_value, tb)
        logging.getLogger('anthill').exception(
            str(exc_value), extra={'handler': self})


class CommonRequestHandlerMixin:
    @property
    def config(self):
        """An alias for `self.application.config <Application.config>`."""
        return self.application.config

    @property
    def db(self):
        """An alias for `self.application.db <Application.db>`."""
        return self.application.db

    @property
    def debug(self):
        """An alias for `self.application.debug <Application.debug>`."""
        return self.application.debug

    def clear(self):
        """Resets all headers and content for this response."""
        super().clear()
        if settings.HIDE_SERVER_VERSION:
            self.clear_header('Server')

    def is_secure(self):
        return self.request.protocol in ('https',)


class RequestHandler(TranslationHandlerMixin, LogExceptionHandlerMixin, SessionHandlerMixin,
                     CommonRequestHandlerMixin, BaseRequestHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.init_session()

    def get_content_type(self):
        content_type = self.request.headers.get('Content-Type', 'text/plain')
        # noinspection PyProtectedMember
        return httputil._parse_header(content_type)

    def reverse_url(self, name, *args):
        url = super().reverse_url(name, *args)
        return url.rstrip('?')

    def get_current_user(self):
        """
        Override to determine the current user from, e.g., a cookie.
        This method may not be a coroutine.
        """
        return None

    def data_received(self, chunk):
        """
        Implement this method to handle streamed request data.
        Requires the `.stream_request_body` decorator.
        """

    def is_ajax(self):
        return self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    async def prepare(self):
        """Called at the beginning of a request before  `get`/`post`/etc."""
        self.setup_session()

    def finish(self, chunk=None):
        """Finishes this response, ending the HTTP request."""
        self.update_session()
        super().finish(chunk)

    def on_finish(self):
        """Called after the end of a request."""

    def set_default_headers(self):
        """
        Override this to set HTTP headers at the beginning of the request.
        """


class BaseClientsWatcher:
    """Base websocket handlers watcher."""

    def get_user_id(self, handler: 'WebSocketHandler') -> str:
        raise NotImplementedError

    async def append(self, handler: 'WebSocketHandler') -> None:
        raise NotImplementedError

    async def remove(self, handler: 'WebSocketHandler') -> None:
        raise NotImplementedError

    async def count(self) -> int:
        raise NotImplementedError


class InMemoryClientsWatcher(BaseClientsWatcher):
    """Default websocket handlers watcher."""

    def __init__(self):
        self.items = []

    async def append(self, handler: 'WebSocketHandler') -> None:
        self.items.append(handler)

    async def remove(self, handler: 'WebSocketHandler') -> None:
        self.items.remove(handler)

    async def count(self) -> int:
        return len(self.items)

    def get_user_id(self, handler: 'WebSocketHandler') -> str:
        return handler.current_user.id


class WebSocketHandler(TranslationHandlerMixin, LogExceptionHandlerMixin, SessionHandlerMixin,
                       CommonRequestHandlerMixin, BaseWebSocketHandler):
    clients = None

    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.settings.update(websocket_ping_interval=settings.WEBSOCKET_PING_INTERVAL)
        self.settings.update(websocket_ping_timeout=settings.WEBSOCKET_PING_TIMEOUT)
        self.settings.update(websocket_max_message_size=settings.WEBSOCKET_MAX_MESSAGE_SIZE)
        self.init_session()

    async def prepare(self):
        """
        Called at the beginning of a request before websocket
        connection is opened.
        """
        self.setup_session()

    async def on_message(self, message):
        """Handle incoming messages on the WebSocket."""
        self.update_session()

    def data_received(self, chunk):
        """Implement this method to handle streamed request data."""

    async def open(self, *args, **kwargs):
        """Invoked when a new WebSocket is opened."""
        if self.clients is not None:
            await self.clients.append(self)

    async def close(self, code=None, reason=None):
        if self.clients is not None:
            await self.clients.remove(self)
        await super().close(code, reason)

    def on_ping(self, data):
        """Invoked when the a ping frame is received."""

    def on_pong(self, data):
        """Invoked when the response to a ping frame is received."""

    def get_compression_options(self):
        if not settings.WEBSOCKET_COMPRESSION_LEVEL:
            return
        options = dict(compression_level=settings.WEBSOCKET_COMPRESSION_LEVEL)
        if settings.WEBSOCKET_MEM_LEVEL is not None:
            options.update(mem_level=settings.WEBSOCKET_MEM_LEVEL)
        return options

    def check_origin(self, origin):
        """Override to enable support for allowing alternate origins."""
        return super().check_origin(origin)


class JsonWebSocketHandler(WebSocketHandler):
    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')


class JSONHandlerMixin:
    extra_context = None

    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')

    def write_error(self, status_code: int, **kwargs) -> None:
        """
        Override to implement custom error pages.

        ``write_error`` may call `write`, `render`, `set_header`, etc
        to produce output as usual.

        If this error was caused by an uncaught exception (including
        HTTPError), an ``exc_info`` triple will be available as
        ``kwargs["exc_info"]``. Note that this exception may not be
        the "current" exception for purposes of methods like
        ``sys.exc_info()`` or ``traceback.format_exc``.
        """
        if self.settings.get("serve_traceback") and "exc_info" in kwargs:
            # in debug mode, try to send a traceback
            self.set_header('Content-Type', 'text/plain')
            reporter = ExceptionReporter(self, exc_info=kwargs["exc_info"])
            self.finish(reporter.get_traceback_text())
        else:
            http_error = None
            for line in kwargs["exc_info"]:
                if isinstance(line, HTTPError):
                    http_error = line
                    break
            error_message = ''
            if http_error:
                error_message = http_error.log_message
            self.write_json(status_code=status_code, message=error_message)

    def write_json(self, status_code: int = 200, message: str = None, data: any = None) -> None:
        """
        Writes json response to client, decoding `data` to json with HTTP-header.

        :param status_code: HTTP response code
        :param message: status code message
        :param data: data to pass to client
        :return:
        """
        self.set_header('Content-Type', 'application/json')
        self.set_status(status_code, message)
        if status_code == 204:
            # status code expects no body
            self.finish()
        else:
            result = {
                'meta': {
                    'code': self._status_code,
                    'message': self._reason,
                },
                'data': data,
            } if status_code != 204 else None
            self.finish(self.dumps(result))

    # noinspection PyMethodMayBeStatic
    def dumps(self, data):
        return json.dumps(data, cls=AlchemyJSONEncoder).replace("</", "<\\/")

    async def get_context_data(self, **kwargs):
        if self.extra_context is not None:
            kwargs.update(self.extra_context)
        return kwargs


class ContextMixin:
    """
    A default context mixin that passes the keyword arguments received by
    get_context_data() as the template context.
    """
    extra_context = None

    async def get_context_data(self, **kwargs):
        if self.extra_context is not None:
            kwargs.update(self.extra_context)
        # noinspection PyTypeChecker
        kwargs.update(await build_context_from_context_processors(self))
        return kwargs


class RedirectMixin:
    query_string = False
    handler_name = None
    url = None

    def initialize(self, query_string=None, handler_name=None, url=None):
        if query_string is not None:
            self.query_string = query_string
        if handler_name is not None:
            self.handler_name = handler_name
        if url is not None:
            self.url = url

    def get_redirect_url(self, *args, **kwargs):
        """
        Return the URL redirect to. Keyword arguments from the URL pattern
        match generating the redirect request are provided as kwargs to this
        method.
        """
        if self.url:
            url = self.url.format(*args)
        elif self.handler_name:
            try:
                from anthill.framework.utils.urls import reverse as reverse_url
                url = reverse_url(self.handler_name, *args, **kwargs)
            except KeyError:
                return
        else:
            return

        # noinspection PyUnresolvedReferences
        request_query = self.request.query
        if request_query and self.query_string:
            url = "%s?%s" % (url, request_query)
        return url


class TemplateMixin:
    """A mixin that can be used to render a template."""
    template_name = None
    content_type = 'text/html'

    def initialize(self, template_name=None, content_type=None):
        if template_name is not None:
            self.template_name = template_name
        if content_type is not None:
            self.content_type = content_type

    def render(self, template_name=None, **kwargs):
        template_name = template_name or self.get_template_name()
        self.set_header('Content-Type', self.content_type)
        # noinspection PyUnresolvedReferences
        super().render(template_name, **kwargs)

    def get_template_namespace(self):
        from anthill.framework.apps import app
        # noinspection PyUnresolvedReferences
        namespace = super().get_template_namespace()
        namespace.update(app_version=app.version)
        namespace.update(debug=app.debug)
        namespace.update(metadata=app.metadata)
        namespace.update(bytes2human=bytes2human)
        namespace.update(build_absolute_uri=build_absolute_uri)
        return namespace

    def get_template_name(self):
        """Return a template name to be used for the request."""
        if self.template_name is None:
            raise ImproperlyConfigured(
                "TemplateMixin requires either a definition of "
                "'template_name' or an implementation of 'get_template_name()'")
        else:
            return self.template_name

    def create_template_loader(self, template_path):
        """
        Returns a new template loader for the given path.

        May be overridden by subclasses. By default returns a
        directory-based loader on the given path, using the
        ``autoescape`` and ``template_whitespace`` application
        settings. If a ``template_loader`` application setting is
        supplied, uses that instead.
        """
        session = getattr(self, 'session', None)
        if "template_loader" in self.settings:
            return self.settings["template_loader"]
        kwargs = {}
        if "autoescape" in self.settings:
            # autoescape=None means "no escaping", so we have to be sure
            # to only pass this kwarg if the user asked for it.
            kwargs["autoescape"] = self.settings["autoescape"]
        if "template_whitespace" in self.settings:
            kwargs["whitespace"] = self.settings["template_whitespace"]
        template_loader_class = getattr(
            settings, "TEMPLATE_LOADER_CLASS", "anthill.framework.core.template.Loader")
        # ``session`` used for caching special template root.
        return import_string(template_loader_class)(template_path, session=session, **kwargs)

    def write_error(self, status_code, **kwargs):
        """
        Override to implement custom error pages.

        ``write_error`` may call `write`, `render`, `set_header`, etc
        to produce output as usual.

        If this error was caused by an uncaught exception (including
        HTTPError), an ``exc_info`` triple will be available as
        ``kwargs["exc_info"]``. Note that this exception may not be
        the "current" exception for purposes of methods like
        ``sys.exc_info()`` or ``traceback.format_exc``.
        """
        if self.settings.get("serve_traceback") and "exc_info" in kwargs:
            # in debug mode, try to send a traceback
            self.set_header('Content-Type', 'text/html')
            reporter = ExceptionReporter(self, exc_info=kwargs["exc_info"])
            self.finish(reporter.get_traceback_html())
        else:
            if status_code in range(500, 600):
                self.render("errors/500.html")
            elif status_code in range(400, 500):
                self.render("errors/404.html")
            else:
                self.render("errors/500.html")


class TemplateHandler(TemplateMixin, ContextMixin, RequestHandler):
    """
    Render a template. Pass keyword arguments to the context.
    """

    async def get(self, *args, **kwargs):
        context = await self.get_context_data(**kwargs)
        self.render(**context)


class RedirectHandler(RedirectMixin, RequestHandler):
    """Provide a redirect on any GET request."""
    permanent = False

    async def get(self, *args, **kwargs):
        url = self.get_redirect_url(*args, **kwargs)
        if url:
            self.redirect(url, permanent=self.permanent)
        else:
            raise HttpGoneError

    async def head(self, *args, **kwargs):
        await self.get(*args, **kwargs)

    async def post(self, *args, **kwargs):
        await self.get(*args, **kwargs)

    async def options(self, *args, **kwargs):
        await self.get(*args, **kwargs)

    async def delete(self, *args, **kwargs):
        await self.get(*args, **kwargs)

    async def put(self, *args, **kwargs):
        await self.get(*args, **kwargs)

    async def patch(self, *args, **kwargs):
        await self.get(*args, **kwargs)


class JSONHandler(JSONHandlerMixin, RequestHandler):
    async def get(self, *args, **kwargs):
        context = await self.get_context_data(**kwargs)
        self.write(context)

    def write(self, data):
        super().write(self.dumps(data))


class StaticFileHandler(SessionHandlerMixin, BaseStaticFileHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.init_session()

    async def prepare(self):
        self.setup_session()
        # noinspection PyAttributeOutsideInit
        self.root = self.get_root()

    def get_root(self):
        """
        Returns static path dynamically retrieved from session storage.
        Adding ability to change ui theme directly from admin interface.
        """
        return self.session.get('static_path', self.root)

    def data_received(self, chunk):
        pass


class Handler404(TemplateHandler):
    template_name = 'errors/404.html'

    def prepare(self):
        self.set_status(404)
        self.render()
