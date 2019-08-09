from anthill.framework.core.management import Command, Option, InvalidCommand
from anthill.framework.apps.builder import app


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
                    object_count=object_count,
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


def get_serializer(fmt):
    raise NotImplementedError


def serialize(fmt, queryset, **options):
    """
    Serialize a queryset (or any iterator that returns database objects) using
    a certain serializer.
    """
    s = get_serializer(fmt)()
    s.serialize(queryset, **options)
    return s.data
