"""
Base file upload handler classes, and the built-in concrete subclasses
"""
from anthill.framework.core.files.uploadedfile import TemporaryUploadedFile, InMemoryUploadedFile
from anthill.framework.utils.module_loading import import_string
from anthill.framework.conf import settings
from io import BytesIO

__all__ = [
    'UploadFileException', 'FileUploadHandler',
    'TemporaryFileUploadHandler', 'MemoryFileUploadHandler', 'load_handler',
    'StopFutureHandlers'
]


class UploadFileException(Exception):
    """
    Any error having to do with uploading files.
    """


class StopFutureHandlers(UploadFileException):
    """
    Upload handlers that have handled a file and do not want future handlers to
    run should raise this exception instead of returning None.
    """


class FileUploadHandler:
    """Base class for streaming upload handlers."""

    def __init__(self, request=None):
        self.field_name = None
        self.file_name = None
        self.content_type = None
        self.content_length = None
        self.charset = None
        self.content_type_extra = None
        self.request = request

    async def start(self, content_length, encoding=None):
        """
        Signal that a uploading has been started.

        Parameters:
            :content_length:
                The value (integer) of the Content-Length header from the client.
        """

    async def new_file(self, field_name, file_name, content_type, content_length,
                       charset=None, content_type_extra=None):
        """
        Signal that a new file has been started.

        Warning: As with any data from the client, you should not trust
        content_length (and sometimes won't even get it).
        """
        self.field_name = field_name
        self.file_name = file_name
        self.content_type = content_type
        self.content_length = content_length
        self.charset = charset
        self.content_type_extra = content_type_extra

    async def receive_data_chunk(self, raw_data):
        """
        Receive data from the streamed upload parser.
        """
        raise NotImplementedError('subclasses of FileUploadHandler must provide a receive_data_chunk() method')

    async def complete_file(self, file_size):
        """Called when a file has been received."""

    async def complete(self):
        """
        Signal that the upload is complete. Subclasses should perform cleanup
        that is necessary for this handler.
        """


class TemporaryFileUploadHandler(FileUploadHandler):
    """Upload handler that streams data into a temporary file."""

    def __init__(self, request=None):
        super().__init__(request)
        self.file = None

    async def new_file(self, *args, **kwargs):
        await super().new_file(*args, **kwargs)
        self.file = TemporaryUploadedFile(
            self.file_name, self.content_type, 0, self.charset, self.content_type_extra)

    async def receive_data_chunk(self, raw_data):
        self.file.write(raw_data)

    async def complete_file(self, file_size):
        self.file.seek(0)
        self.file.size = file_size
        return self.file


class MemoryFileUploadHandler(FileUploadHandler):
    """
    File upload handler to stream uploads into memory (used for small files).
    """

    def __init__(self, request=None):
        super().__init__(request)
        self.activated = True
        self.file = None

    async def start(self, content_length, encoding=None):
        """
        Use the content_length to signal whether or not this handler should be used.
        """
        # Check the content-length header to see if we should
        # If the post is too large, we cannot use the Memory handler.
        if content_length > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
            self.activated = False
        await super().start(content_length, encoding)

    async def new_file(self, *args, **kwargs):
        await super().new_file(*args, **kwargs)
        if self.activated:
            self.file = BytesIO()
            raise StopFutureHandlers

    async def receive_data_chunk(self, raw_data):
        """Add the data to the BytesIO file."""
        if self.activated:
            self.file.write(raw_data)
        else:
            return raw_data

    async def complete_file(self, file_size):
        """Return a file object if this handler is activated."""
        if not self.activated:
            return
        self.file.seek(0)
        return InMemoryUploadedFile(
            file=self.file,
            field_name=self.field_name,
            name=self.file_name,
            content_type=self.content_type,
            size=file_size,
            charset=self.charset,
            content_type_extra=self.content_type_extra
        )


def load_handler(path, *args, **kwargs):
    """
    Given a path to a handler, return an instance of that handler.

    E.g.::
        >>> load_handler('anthill.framework.core.files.uploadhandler.TemporaryFileUploadHandler', request)
        <TemporaryFileUploadHandler object at 0x...>
    """
    return import_string(path)(*args, **kwargs)
