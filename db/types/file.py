from anthill.framework.core.files.storage import default_storage
from anthill.framework.core.files.base import File
from anthill.framework.core.files.images import ImageFile
from sqlalchemy.types import TypeDecorator, Unicode
from datetime import datetime
import posixpath


class FieldFile(File):
    def __init__(self, field, name):
        super().__init__(None, name)
        self.field = field
        self.storage = field.storage
        self._committed = True

    def __hash__(self):
        return hash(self.name)

    # The standard File contains most of the necessary properties, but
    # FieldFiles can be instantiated without a name, so that needs to
    # be checked for here.

    def _require_file(self):
        if not self:
            raise ValueError("The '%s' attribute has no file "
                             "associated with it." % self.field.name)

    def _get_file(self):
        self._require_file()
        if getattr(self, '_file', None) is None:
            self._file = self.storage.open(self.name, 'rb')
        return self._file

    def _set_file(self, file):
        self._file = file

    def _del_file(self):
        del self._file

    file = property(_get_file, _set_file, _del_file)

    @property
    def path(self):
        self._require_file()
        return self.storage.path(self.name)

    @property
    def url(self):
        self._require_file()
        return self.storage.url(self.name)

    @property
    def size(self):
        self._require_file()
        if not self._committed:
            return self.file.size
        return self.storage.size(self.name)

    def open(self, mode='rb'):
        self._require_file()
        if getattr(self, '_file', None) is None:
            self.file = self.storage.open(self.name, mode)
        else:
            self.file.open(mode)
        return self

    # In addition to the standard File API, FieldFiles have extra methods
    # to further manipulate the underlying file.

    def save(self, name, content):
        name = self.field.generate_filename(name)
        self.name = self.storage.save(
            name, content, max_length=self.field.max_length)
        self._committed = True

    def delete(self):
        if not self:
            return
        # Only close the file if it's already open, which we know by the
        # presence of self._file
        if hasattr(self, '_file'):
            self.close()
            del self.file

        self.storage.delete(self.name)

        self.name = None
        self._committed = False

    @property
    def closed(self):
        file = getattr(self, '_file', None)
        return file is None or file.closed

    def close(self):
        file = getattr(self, '_file', None)
        if file is not None:
            file.close()


class ImageFieldFile(ImageFile, FieldFile):
    def delete(self):
        # Clear the image dimensions cache
        if hasattr(self, '_dimensions_cache'):
            del self._dimensions_cache
        super().delete()


class FileDescriptor:
    """
    The descriptor for the file attribute on the model instance.
    Return a FieldFile when accessed so you can write code like::

        >>> from myapp.models import MyModel
        >>> instance = MyModel.query.get(1)
        >>> instance.file.size

    Assign a file object on assignment so you can do::

        >>> with open('/path/to/hello.world', 'r') as f:
        ...     instance.file = File(f)
    """
    def __init__(self, field):
        self.field = field

    def __get__(self, instance, cls=None):
        if instance is None:
            return self

    def __set__(self, instance, value):
        pass


class ImageFileDescriptor(FileDescriptor):
    """
    Just like the FileDescriptor, but for ImageFields. The only difference is
    assigning the width/height, if appropriate.
    """
    def __set__(self, instance, value):
        super().__set__(instance, value)


class FileType(TypeDecorator):
    impl = Unicode(100)
    python_type = File

    def __init__(self, *args, upload_to='', storage=None, max_length=100, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage = storage or default_storage
        self.upload_to = upload_to
        self.impl = Unicode(max_length)
        self.max_length = max_length
        self.check()

    def check(self):
        self._check_upload_to()

    def process_literal_param(self, value, dialect):
        pass

    def process_bind_param(self, value, dialect):
        if value is not None:
            return value

        if isinstance(value, FieldFile):
            value = value.name

        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return value

        if isinstance(value, str):
            value = FieldFile(self, value)

        return value

    def generate_filename(self, filename):
        """
        Apply (if callable) or prepend (if a string) upload_to to the filename,
        then delegate further processing of the name to the storage backend.
        Until the storage layer, all file paths are expected to be Unix style
        (with forward slashes).
        """
        if callable(self.upload_to):
            filename = self.upload_to(filename)
        else:
            dirname = datetime.now().strftime(self.upload_to)
            filename = posixpath.join(dirname, filename)
        return self.storage.generate_filename(filename)

    # noinspection PyMethodMayBeStatic
    def before_save(self, value, create=False):
        """Need for configuring model events before_insert/before_update."""
        # noinspection PyProtectedMember
        if value and not value._committed:
            # Commit the file to storage prior to saving the model
            value.save(value.name, value.file)

    # noinspection PyMethodMayBeStatic
    def after_delete(self, value):
        """Need for configuring model event after_delete."""
        if value:
            value.delete()

    def _check_upload_to(self):
        if isinstance(self.upload_to, str) and self.upload_to.startswith('/'):
            raise ValueError("%s's 'upload_to' argument must be a relative path, not an "
                             "absolute path." % self.__class__.__name__)


class ImageType(FileType):
    python_type = ImageFile

    def __init__(self, *args, width=None, height=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.width = width
        self.height = height
        self.check()

    def check(self):
        self._check_image_library_installed()

    # noinspection PyMethodMayBeStatic
    def _check_image_library_installed(self):
        try:
            from PIL import Image  # NOQA
        except ImportError:
            raise ValueError('Cannot use ImageType because Pillow is not installed. '
                             'Get Pillow at https://pypi.org/project/Pillow/ '
                             'or run command "pip install Pillow".')

    def process_literal_param(self, value, dialect):
        pass

    def process_bind_param(self, value, dialect):
        if value is not None:
            return value

        if isinstance(value, ImageFieldFile):
            value = value.name

        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return value

        if isinstance(value, str):
            value = ImageFieldFile(self, value)

        return value
