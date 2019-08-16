from anthill.framework.core.management import Command, Option, InvalidCommand
from anthill.framework.utils.serializer import AnthillJSONEncoder
from io import StringIO
import collections
import decimal
import json
import yaml


# Use the C (faster) implementation if possible
try:
    from yaml import CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeDumper


class AnthillSafeDumper(SafeDumper):
    def represent_decimal(self, data):
        return self.represent_scalar('tag:yaml.org,2002:str', str(data))

    def represent_ordered_dict(self, data):
        return self.represent_mapping('tag:yaml.org,2002:map', data.items())


AnthillSafeDumper.add_representer(decimal.Decimal, AnthillSafeDumper.represent_decimal)
AnthillSafeDumper.add_representer(collections.OrderedDict, AnthillSafeDumper.represent_ordered_dict)
# Workaround to represent dictionaries in insertion order.
# See https://github.com/yaml/pyyaml/pull/143.
AnthillSafeDumper.add_representer(dict, AnthillSafeDumper.represent_ordered_dict)


class SerializerDoesNotExist(KeyError):
    """The requested serializer was not found."""


class DumpData(Command):
    help = description = 'Output the contents of the database as a fixture of the given format.'

    option_list = (
        Option('args', metavar='model_name', nargs='*',
               help='Restricts dumped data to the specified model name.'),
        Option('--format', default='json',
               help='Specifies the output serialization format for fixtures.'),
        Option('--indent', type=int,
               help='Specifies the indent level to use when pretty-printing output.'),
        Option('-e', '--exclude', action='append', default=[],
               help='A model name to exclude '
                    '(use multiple --exclude to exclude multiple models).'),
        Option('--pks', dest='primary_keys',
               help='Only dump objects with given primary keys. Accepts a comma-separated '
                    'list of keys. This option only works when you specify one model.'),
        Option('-o', '--output',
               help='Specifies file to which the output is written.')
    )

    # noinspection PyAttributeOutsideInit
    def run(self, *model_names, **options):
        self.format = options['format']
        self.indent = options['indent']
        self.excluded_models = options['exclude']
        self.output = options['output']

        pks = options['primary_keys']
        if pks:
            self.primary_keys = [pk.strip() for pk in pks.split(',')]
        else:
            self.primary_keys = []

        from anthill.framework.apps.builder import app

        if not model_names:
            if self.primary_keys:
                raise InvalidCommand("You can only use --pks option with one model")
            self.models = list(filter(lambda m: m.__name__ not in self.excluded_models, app.get_models()))
        else:
            if len(model_names) > 1 and self.primary_keys:
                raise InvalidCommand("You can only use --pks option with one model")
            self.models = []
            for model_name in model_names:
                model = app.get_model(model_name)
                if model is None:
                    raise InvalidCommand("Unknown model: %s" % model_name)
                self.models.append(model)

        try:
            self.stdout.ending = None
            progress_output = None
            object_count = 0
            # If dumpdata is outputting to stdout, there is no way to display progress
            if self.output and self.stdout.isatty():
                progress_output = self.stdout
                object_count = sum(self.get_objects(count_only=True))
            stream = open(self.output, 'w') if self.output else None
            try:
                serialize(
                    self.format, self.get_objects(), indent=indent,
                    stream=stream or self.stdout, progress_output=progress_output,
                    object_count=object_count
                )
            finally:
                if stream:
                    stream.close()
        except Exception as e:
            raise InvalidCommand("Unable to serialize database: %s" % e)

    def get_objects(self, count_only=False):
        """
        Collate the objects to be serialized. If count_only is True, just
        count the number of objects to be serialized.
        """
        for model in self.models:
            if model in excluded_models:
                continue
            query = Model.query
            if self.primary_keys:
                query = query.filter(Model.id.in_(self.primary_keys))
            if count_only:
                yield query.count()
            else:
                yield query.all()


class ProgressBar:
    progress_width = 75

    def __init__(self, output, total_count):
        self.output = output
        self.total_count = total_count
        self.prev_done = 0

    def update(self, count):
        if not self.output:
            return
        perc = count * 100 // self.total_count
        done = perc * self.progress_width // 100
        if self.prev_done >= done:
            return
        self.prev_done = done
        cr = '' if self.total_count == 1 else '\r'
        self.output.write(cr + '[' + '.' * done + ' ' * (self.progress_width - done) + ']')
        if done == self.progress_width:
            self.output.write('\n')
        self.output.flush()


class BaseSerializer:
    """Abstract serializer base class."""
    progress_class = ProgressBar
    stream_class = StringIO

    # noinspection PyAttributeOutsideInit
    def serialize(self, queryset, *, stream=None, fields=None,
                  progress_output=None, object_count=0, **options):
        """Serialize a queryset."""
        self.options = options

        self.stream = stream if stream is not None else self.stream_class()
        self.selected_fields = fields
        progress_bar = self.progress_class(progress_output, object_count)

        self.start_serialization()
        self.first = True

        for count, obj in enumerate(queryset, start=1):
            self.start_object(obj)
            self.end_object(obj)
            progress_bar.update(count)
            if self.first:
                self.first = False

        self.end_serialization()

    def start_serialization(self):
        """
        Called when serializing of the queryset starts.
        """
        raise NotImplementedError('subclasses of Serializer must provide a start_serialization() method')

    def end_serialization(self):
        """
        Called when serializing of the queryset ends.
        """

    def start_object(self, obj):
        """
        Called when serializing of an object starts.
        """
        raise NotImplementedError('subclasses of Serializer must provide a start_object() method')

    def end_object(self, obj):
        """
        Called when serializing of an object ends.
        """

    def getvalue(self):
        """
        Return the fully serialized queryset (or None if the output stream is
        not seekable).
        """
        if callable(getattr(self.stream, 'getvalue', None)):
            return self.stream.getvalue()


# noinspection PyAttributeOutsideInit
class PythonSerializer(BaseSerializer):
    """Serialize a QuerySet to basic Python objects."""

    def start_serialization(self):
        self.objects = []

    def end_serialization(self):
        pass

    def start_object(self, obj):
        pass

    def end_object(self, obj):
        self.objects.append(self.get_dump_object(obj))

    def get_dump_object(self, obj):
        schema = None
        Model = obj.__class__
        if self.selected_fields:
            from anthill.framework.apps.builder import app
            schema = app.get_model_schema(Model, selected_fields=self.selected_fields)
        fields = obj.dump(schema=schema).data
        del fields['id']
        return {
            'model': Model.__name__,
            'id': obj.id,
            'fields': fields
        }

    def getvalue(self):
        return self.objects


class YAMLSerializer(PythonSerializer):
    """Convert a queryset to YAML."""

    def end_serialization(self):
        yaml.dump(self.objects, self.stream, Dumper=AnthillSafeDumper, **self.options)


# noinspection PyAttributeOutsideInit
class JSONSerializer(PythonSerializer):
    """Convert a queryset to JSON."""

    def _init_options(self):
        self.json_kwargs = self.options.copy()
        self.json_kwargs.pop('stream', None)
        self.json_kwargs.pop('fields', None)
        if self.options.get('indent'):
            # Prevent trailing spaces
            self.json_kwargs['separators'] = (',', ': ')
        self.json_kwargs.setdefault('cls', AnthillJSONEncoder)

    def start_serialization(self):
        self._init_options()
        self.stream.write("[")

    def end_serialization(self):
        if self.options.get("indent"):
            self.stream.write("\n")
        self.stream.write("]")
        if self.options.get("indent"):
            self.stream.write("\n")

    def end_object(self, obj):
        indent = self.options.get("indent")
        if not self.first:
            self.stream.write(",")
            if not indent:
                self.stream.write(" ")
        if indent:
            self.stream.write("\n")
        json.dump(self.get_dump_object(obj), self.stream, **self.json_kwargs)


class XMLSerializer(PythonSerializer):
    pass


def get_serializer(fmt):
    try:
        return get_serializers()[fmt]
    except KeyError:
        raise SerializerDoesNotExist(fmt)


def get_serializers():
    return {
        'yaml': YAMLSerializer,
        'json': JSONSerializer,
        'xml': XMLSerializer,
    }


def serialize(fmt, queryset, **options):
    """
    Serialize a queryset (or any iterator that returns database objects) using
    a certain serializer.
    """
    s = get_serializer(fmt)()
    s.serialize(queryset, **options)
    return s.getvalue()
