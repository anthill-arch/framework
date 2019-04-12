from anthill.framework.handlers import JsonWebSocketHandler
from anthill.framework.core.jsonrpc.exceptions import JSONRPCInvalidRequestException
from anthill.framework.core.jsonrpc.jsonrpc import JSONRPCRequest
from anthill.framework.core.jsonrpc.manager import JSONRPCResponseManager
from anthill.framework.core.jsonrpc.dispatcher import Dispatcher
from anthill.framework.core.jsonrpc.utils import DatetimeDecimalEncoder
import json


def response_serialize(obj):
    """Serializes response's data object to JSON."""
    return json.dumps(obj, cls=DatetimeDecimalEncoder)


class JSONRPCMixin:
    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')

    def set_extra_headers(self, path):
        self.set_header('Cache-Control', 'no-store')

    async def json_rpc(self, message: str) -> str:
        try:
            json_rpc_request = JSONRPCRequest.from_json(message)
        except (TypeError, ValueError, JSONRPCInvalidRequestException):
            response = await JSONRPCResponseManager.handle(message, self.dispatcher)
        else:
            json_rpc_request.params = json_rpc_request.params or {}
            response = await JSONRPCResponseManager.handle_request(
                json_rpc_request, self.dispatcher)

        if response:
            response.serialize = response_serialize
            response = response.json

        return response

    def json_rpc_map(self):
        """Map of json-rpc available calls."""
        raise NotImplementedError


class WebSocketJSONRPCHandler(JSONRPCMixin, JsonWebSocketHandler):
    def __init__(self, application, request, dispatcher=None, **kwargs):
        super().__init__(application, request, **kwargs)
        self.dispatcher = dispatcher if dispatcher is not None else Dispatcher()

    async def on_message(self, message):
        """Handle incoming messages on the WebSocket."""
        await super().on_message(message)
        result = await self.json_rpc(message)
        if result is not None:
            self.write_message(result)

    def json_rpc_map(self):
        """Map of json-rpc available calls."""
        return dict((f_name, f.__doc__) for f_name, f in self.dispatcher.items())
