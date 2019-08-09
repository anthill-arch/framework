from anthill.framework.core.management import Command, Option, InvalidCommand
from anthill.framework.utils.functional import cached_property
from anthill.framework.core.exceptions import ImproperlyConfigured
from anthill.framework.conf import settings
from anthill.framework.apps.builder import app
from anthill.framework.db import db
import functools
import glob
import gzip
import os
import sys
import yaml
import warnings
import zipfile
from io import StringIO
from itertools import product

try:
    import bz2
    has_bz2 = True
except ImportError:
    has_bz2 = False


# Use the C (faster) implementation if possible
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader


class DeserializationError(Exception):
    """Something bad happened during deserialization."""


READ_STDIN = '-'


class LoadData(Command):
    help = description = 'Installs the named fixture(s) in the database.'

    option_list = (
        Option('args', metavar='fixture', nargs='+', help='Fixture labels.'),
        Option('--ignorenonexistent', '-i', action='store_true', dest='ignore',
               help='Ignores entries in the serialized data for fields that do not '
                    'currently exist on the model.'),
        Option('-e', '--exclude', action='append', default=[],
               help='A model name to exclude. Can be used multiple times.'),
        Option('--format',
               help='Format of serialized data when reading from stdin.'),
    )

    # noinspection PyAttributeOutsideInit
    def run(self, *fixture_labels, **options):
        self.ignore = options['ignore']
        self.excluded_models = options['exclude']
        self.format = options['format']

        self.loaddata(fixture_labels)

    # noinspection PyAttributeOutsideInit
    def loaddata(self, fixture_labels):
        # Keep a count of the installed objects and fixtures
        self.fixture_count = 0
        self.loaded_object_count = 0
        self.fixture_object_count = 0
        self.models = set()

        self.serialization_formats = get_deserializers(keys=True)

        self.compression_formats = {
            None: (open, 'rb'),
            'gz': (gzip.GzipFile, 'rb'),
            'zip': (SingleZipReader, 'r'),
            'stdin': (lambda *args: sys.stdin, None),
        }
        if has_bz2:
            self.compression_formats['bz2'] = (bz2.BZ2File, 'r')

        # Anthill's test suite repeatedly tries to load initial_data fixtures
        # from apps that don't have any fixtures. Because disabling constraint
        # checks can be expensive on some database (especially MSSQL), bail
        # out early if no fixtures are found.
        for fixture_label in fixture_labels:
            if self.find_fixtures(fixture_label):
                break
        else:
            return

        for fixture_label in fixture_labels:
            self.load_label(fixture_label)

        if self.fixture_object_count == self.loaded_object_count:
            self.stdout.write(
                "Installed %d object(s) from %d fixture(s)"
                % (self.loaded_object_count, self.fixture_count)
            )
        else:
            self.stdout.write(
                "Installed %d object(s) (of %d) from %d fixture(s)"
                % (self.loaded_object_count, self.fixture_object_count, self.fixture_count)
            )

    def load_label(self, fixture_label):
        """Load fixtures files for a given label."""
        for fixture_file, fixture_dir, fixture_name in self.find_fixtures(fixture_label):
            _, ser_fmt, cmp_fmt = self.parse_name(os.path.basename(fixture_file))
            open_method, mode = self.compression_formats[cmp_fmt]
            fixture = open_method(fixture_file, mode)
            try:
                self.fixture_count += 1
                objects_in_fixture = 0
                loaded_objects_in_fixture = 0
                self.stdout.write(
                    "Installing %s fixture '%s' from %s."
                    % (ser_fmt, fixture_name, humanize(fixture_dir))
                )

                objects = deserialize(ser_fmt, fixture, ignorenonexistent=self.ignore)

                for obj in objects:
                    objects_in_fixture += 1
                    if obj.__class__.__name__ in self.excluded_models:
                        continue
                    loaded_objects_in_fixture += 1
                    self.models.add(obj.__class__)
                    try:
                        obj.save()
                        self.stdout.write(
                            '\rProcessed %i object(s).' % loaded_objects_in_fixture,
                            ending=''
                        )
                    except Exception as e:
                        e.args = ("Could not load %(class_name)s(id=%(id)s): %(error_msg)s" % {
                            'class_name': obj.__class__.__name__,
                            'id': obj.id,
                            'error_msg': e,
                        },)
                        raise
                if objects:
                    self.stdout.write('')  # add a newline after progress indicator
                self.loaded_object_count += loaded_objects_in_fixture
                self.fixture_object_count += objects_in_fixture
            except Exception as e:
                if not isinstance(e, InvalidCommand):
                    e.args = ("Problem installing fixture '%s': %s" % (fixture_file, e),)
                raise
            finally:
                fixture.close()

            # Warn if the fixture we loaded contains 0 objects.
            if objects_in_fixture == 0:
                warnings.warn(
                    "No fixture data found for '%s'. (File format may be "
                    "invalid.)" % fixture_name,
                    RuntimeWarning
                )

    @functools.lru_cache(maxsize=None)
    def find_fixtures(self, fixture_label):
        """Find fixture files for a given label."""
        if fixture_label == READ_STDIN:
            return [(READ_STDIN, None, READ_STDIN)]

        fixture_name, ser_fmt, cmp_fmt = self.parse_name(fixture_label)
        cmp_fmts = list(self.compression_formats) if cmp_fmt is None else [cmp_fmt]
        ser_fmts = self.serialization_formats if ser_fmt is None else [ser_fmt]

        self.stdout.write("Loading '%s' fixtures..." % fixture_name)

        if os.path.isabs(fixture_name):
            fixture_dirs = [os.path.dirname(fixture_name)]
            fixture_name = os.path.basename(fixture_name)
        else:
            fixture_dirs = self.fixture_dirs
            if os.path.sep in os.path.normpath(fixture_name):
                fixture_dirs = [
                    os.path.join(dir_, os.path.dirname(fixture_name))
                    for dir_ in fixture_dirs
                ]
                fixture_name = os.path.basename(fixture_name)

        suffixes = (
            '.'.join(ext for ext in combo if ext)
            for combo in product(ser_fmts, cmp_fmts)
        )
        targets = {'.'.join((fixture_name, suffix)) for suffix in suffixes}

        fixture_files = []
        for fixture_dir in fixture_dirs:
            self.stdout.write("Checking %s for fixtures..." % humanize(fixture_dir))
            fixture_files_in_dir = []
            path = os.path.join(fixture_dir, fixture_name)
            for candidate in glob.iglob(glob.escape(path) + '*'):
                if os.path.basename(candidate) in targets:
                    # Save the fixture_dir and fixture_name for future error messages.
                    fixture_files_in_dir.append((candidate, fixture_dir, fixture_name))

            if not fixture_files_in_dir:
                self.stdout.write("No fixture '%s' in %s." %
                                  (fixture_name, humanize(fixture_dir)))

            # Check kept for backwards-compatibility; it isn't clear why
            # duplicates are only allowed in different directories.
            if len(fixture_files_in_dir) > 1:
                raise InvalidCommand(
                    "Multiple fixtures named '%s' in %s. Aborting." %
                    (fixture_name, humanize(fixture_dir)))
            fixture_files.extend(fixture_files_in_dir)

        if not fixture_files:
            raise InvalidCommand("No fixture named '%s' found." % fixture_name)

        return fixture_files

    @cached_property
    def fixture_dirs(self):
        """Return a list of fixture directories."""
        dirs = []
        fixture_dirs = settings.FIXTURE_DIRS
        if len(fixture_dirs) != len(set(fixture_dirs)):
            raise ImproperlyConfigured("settings.FIXTURE_DIRS contains duplicates.")

        dirs.extend(fixture_dirs)
        dirs.append('')

        return [os.path.realpath(d) for d in dirs]

    def parse_name(self, fixture_name):
        """
        Split fixture name in name, serialization format, compression format.
        """
        if fixture_name == READ_STDIN:
            if not self.format:
                raise InvalidCommand('--format must be specified when reading from stdin.')
            return READ_STDIN, self.format, 'stdin'

        parts = fixture_name.rsplit('.', 2)

        if len(parts) > 1 and parts[-1] in self.compression_formats:
            cmp_fmt = parts[-1]
            parts = parts[:-1]
        else:
            cmp_fmt = None

        if len(parts) > 1:
            if parts[-1] in self.serialization_formats:
                ser_fmt = parts[-1]
                parts = parts[:-1]
            else:
                raise InvalidCommand(
                    "Problem installing fixture '%s': %s is not a known "
                    "serialization format." % ('.'.join(parts[:-1]), parts[-1]))
        else:
            ser_fmt = None

        name = '.'.join(parts)

        return name, ser_fmt, cmp_fmt


class SingleZipReader(zipfile.ZipFile):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if len(self.namelist()) != 1:
            raise ValueError("Zip-compressed fixtures must contain one file.")

    # noinspection PyMethodOverriding
    def read(self):
        return zipfile.ZipFile.read(self, self.namelist()[0])


def humanize(dirname):
    return "'%s'" % dirname if dirname else 'absolute path'


def _get_model(model_name):
    """Look up a model from a "model_name" string."""
    model = app.get_model(model_name)
    if model is None:
        raise DeserializationError("Invalid model name: '%s'" % model_name)


def build_instance(model_class, data):
    Serializer = getattr(model_class, '__marshmallow__', None)
    if Serializer is None:
        raise DeserializationError("Invalid model serializer: '%s'" % model_class.__name__)
    obj = Serializer.load(data, session=db.session)
    return obj.data


def PythonDeserializer(object_list, *, ignorenonexistent=False, **options):
    """
    Deserialize simple Python objects back into sqlalchemy ORM instances.

    It's expected that you pass the Python objects themselves (instead of a
    stream or a string) to the constructor
    """
    for d in object_list:
        # Look up the model and starting build a dict of data for it.
        try:
            Model = _get_model(d['model'])
        except DeserializationError:
            if ignorenonexistent:
                continue
            else:
                raise

        data = d['fields']
        data.update(id=d['id'])

        yield build_instance(Model, data)


def JSONDeserializer(stream_or_string, **options):
    """Deserialize a stream or string of JSON data."""
    if not isinstance(stream_or_string, (bytes, str)):
        stream_or_string = stream_or_string.read()
    if isinstance(stream_or_string, bytes):
        stream_or_string = stream_or_string.decode()
    try:
        objects = json.loads(stream_or_string)
        yield from PythonDeserializer(objects, **options)
    except (GeneratorExit, DeserializationError):
        raise
    except Exception as exc:
        raise DeserializationError() from exc


def YAMLDeserializer(stream_or_string, **options):
    """Deserialize a stream or string of YAML data."""
    if isinstance(stream_or_string, bytes):
        stream_or_string = stream_or_string.decode()
    if isinstance(stream_or_string, str):
        stream = StringIO(stream_or_string)
    else:
        stream = stream_or_string
    try:
        objects = yaml.load(stream, Loader=SafeLoader)
        yield from PythonDeserializer(objects, **options)
    except (GeneratorExit, DeserializationError):
        raise
    except Exception as exc:
        raise DeserializationError() from exc


def XMLDeserializer(stream_or_string, **options):
    """Deserialize a stream or string of XML data."""
    raise NotImplementedError


def get_deserializers(keys=False):
    deserializers = {
        'yaml': YAMLDeserializer,
        'json': JSONDeserializer,
        'xml': XMLDeserializer,
    }
    return deserializers.keys() if keys else deserializers


def get_deserializer(fmt):
    return get_deserializers()[fmt]


def deserialize(fmt, stream_or_string, **options):
    """
    Deserialize a stream or a string.
    """
    d = get_deserializer(fmt)
    return d(stream_or_string, **options)
