from anthill.framework.conf import settings
from anthill.framework.handlers.base import (
    TranslationHandlerMixin, LogExceptionHandlerMixin, SessionHandlerMixin,
    CommonRequestHandlerMixin
)
import socketio
import logging

__all__ = ['BaseSocketIOHandler', 'SocketIOHandler', 'socketio_server', 'socketio_client']

logger = logging.getLogger('anthill.application')

socketio_server = socketio.AsyncServer(
    client_manager=socketio.AsyncRedisManager('redis://', logger=logger),
    async_mode='tornado',
    engineio_logger=logger,
    logger=logger,
    ping_timeout=settings.WEBSOCKET_PING_TIMEOUT,
    ping_interval=settings.WEBSOCKET_PING_INTERVAL,
    max_http_buffer_size=settings.WEBSOCKET_MAX_MESSAGE_SIZE,
    cookie=settings.SESSION_COOKIE_NAME
)
socketio_client = socketio.AsyncClient(
    logger=logger,
    engineio_logger=logger,
    reconnection_delay=1,
    reconnection_delay_max=600
)
BaseSocketIOHandler = socketio.get_tornado_handler(socketio_server)


class SocketIOHandler(TranslationHandlerMixin, LogExceptionHandlerMixin, SessionHandlerMixin,
                      CommonRequestHandlerMixin, BaseSocketIOHandler):
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
        await super().on_message(message)
        self.update_session()

    async def open(self, *args, **kwargs):
        """Invoked when a new WebSocket is opened."""
        if self.clients is not None:
            await self.clients.append(self)

    async def close(self, code=None, reason=None):
        if self.clients is not None:
            await self.clients.remove(self)
        await super().close(code, reason)

    # noinspection PyMethodMayBeStatic
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
