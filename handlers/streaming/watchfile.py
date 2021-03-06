from tornado.websocket import WebSocketHandler
from tornado.process import Subprocess
from tornado.escape import to_unicode
from anthill.framework.conf import settings
import logging

__all__ = ['WatchFileHandler', 'WatchTextFileHandler', 'WatchLogFileHandler']

logger = logging.getLogger('anthill.application')


class WatchFileHandler(WebSocketHandler):
    """
    Sends new data to WebSocket client while file changing.
    """
    streaming_finished_message = 'File streaming has finished up'
    extra_args = []
    last_lines_limit = None
    filename = None

    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self._process = None

    def initialize(self, filename=None, last_lines_limit=0):
        if filename is not None:
            self.filename = filename
        self.last_lines_limit = last_lines_limit

    def get_filename(self) -> str:
        return self.filename

    async def _read_until(self):
        data = await self._process.stdout.read_until(b'\n')
        await self.write_line(data)

    async def open(self):
        cmd = ['tail']
        cmd += ['-n', str(self.last_lines_limit)]
        cmd += self.extra_args
        try:
            cmd += ['-f', self.get_filename()]
            self._process = Subprocess(cmd, stdout=Subprocess.STREAM, bufsize=1)
        except Exception as e:
            logger.error(str(e))
            self.close(reason=str(e))
        else:
            self._process.set_exit_callback(self._close)
            await self._read_until()

    def _close(self) -> None:
        self.close(reason=self.streaming_finished_message)

    def on_close(self, *args, **kwargs):
        if self._process is not None:
            self._process.proc.terminate()
            self._process.proc.wait()

    def transform_output_data(self, data: bytes) -> bytes:
        return data

    async def write_line(self, data: bytes) -> None:
        self.write_message(self.transform_output_data(data.strip()))
        await self._read_until()

    def check_origin(self, origin):
        return True
        # TODO: configuration from settings.py
        # return super().check_origin(origin)

    def on_message(self, message):
        pass

    def data_received(self, chunk):
        pass


class WatchTextFileHandler(WatchFileHandler):
    def transform_output_data(self, data: bytes) -> str:
        return to_unicode(data)


class WatchLogFileHandler(WatchTextFileHandler):
    def __init__(self, application, request, **kwargs):
        self.handler_name = None
        super().__init__(application, request, **kwargs)

    def initialize(self, filename=None, last_lines_limit=0, handler_name=None):
        super().initialize(filename, last_lines_limit)
        self.handler_name = handler_name

    def get_filename(self) -> str:
        if self.filename:
            return self.filename
        # Try to retrieve filename from logging configuration.
        try:
            return settings.LOGGING['handlers'][self.handler_name]['filename']
        except AttributeError:
            raise ValueError('Logging configuration not defined')
        except KeyError as e:
            key = e.args[0]
            if key is 'handlers':
                raise ValueError('Logging handlers not defined')
            elif key is self.handler_name:
                raise ValueError('Logging handler not defined: %s' % self.handler_name)
            elif key is 'filename':
                raise ValueError('Log file not defined for handler: %s' % self.handler_name)
