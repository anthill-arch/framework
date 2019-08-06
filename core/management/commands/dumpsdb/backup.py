from anthill.framework.core.files.storage import get_storage_class
from anthill.framework.utils.functional import LazyObject, cached_property
from anthill.framework.conf import settings
from typing import Optional, Iterator
from gzip import compress, decompress
from time import gmtime, strftime
from datetime import datetime
import re
import os
import copy


DEFAULT_DUMPS_SETTINGS = {
    'FILE_PREFIX': 'db',
    'FILE_STORAGE': {
        'CLASS_NAME': 'anthill.framework.core.files.storage.FileSystemStorage',
        'KWARGS': {
            'location': os.path.join(settings.BASE_DIR, 'dumps')
        }
    },
    'COMPRESS_LEVEL': 9
}

USER_DUMPS_SETTINGS = getattr(settings, 'SQLALCHEMY_DUMPS', {})


def _merge_dumps_settings():
    default = copy.deepcopy(DEFAULT_DUMPS_SETTINGS)
    default.update(USER_DUMPS_SETTINGS or {})
    return default


DUMPS_SETTINGS = _merge_dumps_settings()


class BackupStorage(LazyObject):
    def _setup(self):
        class_name = DUMPS_SETTINGS['FILE_STORAGE']['CLASS_NAME']
        kwargs = DUMPS_SETTINGS['FILE_STORAGE'].get('KWARGS') or {}
        self._wrapped = get_storage_class(class_name)(**kwargs)


class Backup:
    TIMESTAMP = strftime('%Y%m%d%H%M%S', gmtime())
    COMPRESSLEVEL = DUMPS_SETTINGS['COMPRESS_LEVEL']

    def __init__(self):
        self.storage = BackupStorage()
        self.prefix = DUMPS_SETTINGS['FILE_PREFIX']

    @cached_property
    def files(self) -> tuple:
        return tuple(self.get_files())

    @staticmethod
    def get_timestamp(name: str) -> Optional[str]:
        """
        Gets the timestamp from a given file name.
        :param name: name of a file generated by AlchemyDumps
        :return: backup numeric id (in case of success) or None
        """
        pattern = r'(.*)(-)(?P<timestamp>[\d]{14})(-)(.*)(.gz)'
        match = re.search(pattern, name)
        if match:
            return match.group('timestamp')

    @staticmethod
    def parse_timestamp(ts: str) -> str:
        """Transforms a timestamp ID in a humanized date."""
        date_parsed = datetime.strptime(ts, '%Y%m%d%H%M%S')
        return date_parsed.strftime('%b %d, %Y at %H:%M:%S')

    def get_timestamps(self) -> Iterator:
        """
        Gets the different existing timestamp numeric IDs.
        :return: existing timestamps in backup directory
        """
        for name in self.files:
            ts = self.get_timestamp(name)
            if ts and ts not in timestamps:
                yield ts

    def by_timestamp(self, ts: str) -> Iterator:
        """
        Gets the list of all backup files with a given timestamp.
        :param ts: timestamp to be used as filter
        :return: backup file names matching the timestamp
        """
        return filter(lambda nm: ts == self.get_timestamp(nm), self.files)

    def valid(self, ts: str) -> bool:
        """Check backup files for the given timestamp."""
        return bool(ts and ts in self.get_timestamps())

    def create_file(self, name: str, content: bytes) -> str:
        """
        Creates a gzip file.
        :param name: name of the file to be created
        :param content: content to be written in the file
        """
        content = compress(content, self.COMPRESSLEVEL)
        return self.storage.save(name, content)

    def delete_file(self, name: str) -> None:
        """
        Delete a file.
        :param name: name of the file to be deleted
        """
        self.storage.delete(name)

    def read_file(self, name: str) -> bytes:
        """
        Reads the content of a gzip file.
        :param name: name of the file to be read
        :return: content of the file
        """
        with self.storage.open(name) as f:
            return decompress(f.read())

    def get_files(self) -> Iterator:
        """List all files in the backup directory."""
        _, files = self.storage.listdir('.')
        return filter(lambda nm: self.get_timestamp(nm), files)

    def generate_filename(self, class_name: str, ts: Optional[str] = None) -> str:
        """
        Generate file name given the timestamp and the name of the
        SQLAlchemy mapped class.
        """
        return '{}-{}-{}.gz'.format(self.prefix, ts or self.TIMESTAMP, class_name)
