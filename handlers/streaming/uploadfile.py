from tornado.web import stream_request_body
from anthill.framework.conf import settings
from anthill.framework.core.files.storage import default_storage
from anthill.framework.core.files.uploadhandler import load_handler
from anthill.framework.handlers import RequestHandler
from anthill.framework.handlers.streaming.multipartparser import StreamingMultiPartParser


# noinspection PyAttributeOutsideInit
class UploadFileStreamHandlerMixin:
    max_upload_size = settings.FILE_UPLOAD_MAX_BODY_SIZE
    multipart_parser_class = StreamingMultiPartParser

    async def prepare(self):
        await super().prepare()
        self._content_type = self.request.headers.get('Content-Type', '')
        if self._content_type.startswith('multipart/form-data'):
            self.request.connection.set_max_body_size(self.max_upload_size)
            self.mp = self.multipart_parser_class(self.request.headers, self.upload_handlers)
            self.request.files = self.mp.files
            self.request.arguments = self.mp.arguments
            self.request.body_arguments = self.mp.arguments

    async def data_received(self, chunk):
        if self._content_type.startswith('multipart/form-data'):
            await self.mp.data_received(chunk)

    def _initialize_handlers(self):
        self._upload_handlers = list(map(
            lambda x: load_handler(x, self.request), settings.FILE_UPLOAD_HANDLERS))

    @property
    def upload_handlers(self):
        if not getattr(self, '_upload_handlers', None):
            # If there are no upload handlers defined, initialize them from settings.
            self._initialize_handlers()
        return self._upload_handlers

    @upload_handlers.setter
    def upload_handlers(self, upload_handlers):
        if hasattr(self.request, 'files'):
            raise AttributeError(
                "You cannot set the upload handlers after the upload has been processed.")
        self._upload_handlers = upload_handlers

    # noinspection PyMethodMayBeStatic
    def filename_transform(self, name):
        return name

    async def process_files(self):
        for files in self.request.files.values():
            for f in files:
                f_name = self.filename_transform(f.name)
                default_storage.save(f_name, f.file)
                f.close()

    async def post(self):
        # Finalize uploading
        await self.process_files()
        await self.mp.complete()


@stream_request_body
class UploadFileStreamHandler(UploadFileStreamHandlerMixin, RequestHandler):
    pass
