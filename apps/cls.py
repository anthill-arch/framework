from anthill.framework.utils.text import slugify, camel_case_to_spaces, class_name
from anthill.framework.utils.module_loading import import_string
from anthill.framework.conf import settings
from marshmallow_sqlalchemy import ModelConversionError, ModelSchema, convert
from urllib.parse import urlparse, urljoin
from collections import defaultdict
from functools import lru_cache
from itertools import chain
from _thread import get_ident
import importlib
import logging
import re

logger = logging.getLogger('anthill.application')


class CommandNamesDuplicatedError(Exception):
    pass


class ApplicationExtensionNotRegistered(Exception):
    def __init__(self, extension):
        self.extension = extension


class CommandParser:
    raise_on_conflict_commands = True

    def __init__(self, raise_on_conflict_commands=None):
        if raise_on_conflict_commands is not None:
            self.raise_on_conflict_commands = raise_on_conflict_commands

    @staticmethod
    def is_command_class(cls):
        from anthill.framework.core.management import Command
        base_classes = (Command,)
        try:
            return issubclass(cls, base_classes) and cls not in base_classes
        except TypeError:
            return False

    @staticmethod
    def is_manager_instance(obj):
        from anthill.framework.core.management import Manager
        return isinstance(obj, Manager)

    @classmethod
    def is_command(cls, obj):
        return cls.is_command_class(obj) or cls.is_manager_instance(obj)

    @classmethod
    def command_instance(cls, obj):
        if cls.is_manager_instance(obj):
            return obj
        return obj()

    @classmethod
    def command_name(cls, obj):
        default_name = obj.__class__.__name__ if cls.is_manager_instance(obj) else obj.__name__
        return getattr(obj, 'name', None) or slugify(camel_case_to_spaces(default_name))

    @classmethod
    def check_names(cls, _commands):
        data = defaultdict(list)
        for name, instance in _commands:
            data[name].append(instance)
        for name, instances in data.items():
            if len(instances) > 1 and cls.raise_on_conflict_commands:
                raise CommandNamesDuplicatedError(
                    '%s => %s' % (name, [obj.__class__.__name__ for obj in instances]))

    @classmethod
    def get_commands(cls, management_conf):
        if callable(management_conf):
            management_conf = management_conf()
        management = importlib.import_module(management_conf)
        return [
            (cls.command_name(obj), cls.command_instance(obj))
            for obj in management.__dict__.values()
            if cls.is_command(obj)
        ]

    def parse(self, management_conf):
        if isinstance(management_conf, str):
            management_conf = [management_conf]

        commands = map(self.get_commands, management_conf)
        commands = list(chain.from_iterable(commands))

        self.check_names(commands)

        return commands


class Application:
    raise_on_conflict_commands = True
    extra_models_modules = None
    system_models_modules = ('anthill.framework.sessions.models',)

    def __init__(self):
        self.settings = self.config = settings
        self.debug = settings.DEBUG
        self.name = settings.APPLICATION_NAME
        self.label = self.name.rpartition('.')[2]
        self.verbose_name = settings.APPLICATION_VERBOSE_NAME or self.label.title()
        self.description = settings.APPLICATION_DESCRIPTION
        self.icon_class = settings.APPLICATION_ICON_CLASS

        self.routes_conf = self.getdefault('ROUTES_CONF', '.'.join([self.name, 'routes']))
        self.service_class = self.getdefault('SERVICE_CLASS', '.'.join([self.name, 'services', 'Service']))
        self.management_conf = self.getdefault('MANAGEMENT_CONF', '.'.join([self.name, 'management']))
        self.models_conf = self.getdefault('MODELS_CONF', '.'.join([self.name, 'models']))
        self.ui_module = self.getdefault('UI_MODULE', '.'.join([self.name, 'ui']))

        self.protocol, self.host, self.port = self.split_location()
        self.host_regex = r'^(%s)$' % re.escape(self.host)
        self.extensions = {}

        self.command_parser = CommandParser(self.raise_on_conflict_commands)

        self._version = None

        setattr(self, '__ident_func__', get_ident)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.label)

    # noinspection SpellCheckingInspection
    def getdefault(self, key, default=None):
        return getattr(self.settings, key, None) or default

    def split_location(self):
        loc = urlparse(getattr(self.settings, 'LOCATION'))
        return loc.scheme, loc.hostname, loc.port

    @property
    def db(self):
        return self.get_extension('sqlalchemy').db

    @property
    def ma(self):
        return self.get_extension('marshmallow')

    @property
    def https_enabled(self):
        return self.protocol == 'https'

    @property
    def version(self):
        if self._version:
            return self._version
        mod = importlib.import_module(self.name)
        return getattr(mod, 'version', None)

    @version.setter
    def version(self, value):
        self._version = value

    @property
    def registry_entry(self):
        entry = {
            network: self.settings.LOCATION
            for network in self.settings.NETWORKS
        }
        entry.update(broker=settings.BROKER)
        return entry

    def get_extension(self, name):
        """Returns an extension by name or raise an exception."""
        if name not in self.extensions:
            raise ApplicationExtensionNotRegistered(name)
        return self.extensions[name]

    # noinspection PyProtectedMember,PyBroadException
    def get_models(self):
        classes, models, table_names = [], [], []
        for clazz in self.db.Model._decl_class_registry.values():
            try:
                table_names.append(clazz.__tablename__)
                classes.append(clazz)
            except Exception:
                pass
        for table in self.db.metadata.tables.items():
            if table[0] in table_names:
                models.append(classes[table_names.index(table[0])])
        return models

    # noinspection PyProtectedMember
    def get_model(self, name):
        return self.db.Model._decl_class_registry.get(name, None)

    # noinspection PyProtectedMember
    def get_model_by_tablename(self, tablename):
        for clazz in self.db.Model._decl_class_registry.values():
            if hasattr(clazz, '__tablename__') and clazz.__tablename__ == tablename:
                return clazz

    @property
    @lru_cache()
    def commands(self):
        return self.command_parser.parse(self.management_conf)

    @property
    @lru_cache()
    def routes(self):
        """Returns routes map."""
        from anthill.framework.utils.urls import include, to_urlspec
        routes_mod = importlib.import_module(self.routes_conf)
        routes_list = getattr(routes_mod, 'route_patterns', [])
        if callable(routes_list):
            routes_list = routes_list()
        routes_list = include(routes_list)
        new_routes_list = []
        for route in routes_list:
            route = to_urlspec(route)
            if route.name is None:
                route.name = class_name(route.target)
            new_routes_list.insert(0, route)
        return new_routes_list

    @property
    def ui_modules(self):
        """
        Returns module object with UIModule subclasses and plain functions.
        Use for ``service.ui_modules`` and ``service.ui_methods`` initializing.
        """
        try:
            return importlib.import_module('.'.join([self.ui_module, 'modules']))
        except ModuleNotFoundError:
            return {}

    def get_models_modules(self):
        models_modules = []
        models_modules += list(self.system_models_modules or [])
        models_modules += list(self.extra_models_modules or [])
        if isinstance(self.models_conf, str):
            models_modules += [self.models_conf]
        elif isinstance(self.models_conf, (tuple, list)):
            models_modules += list(self.models_conf)
        return models_modules

    class ModelConverter(convert.ModelConverter):
        """Anthill model converter for marshmallow model schema."""

    def update_models(self, models):
        def add_schema(cls):
            if hasattr(cls, '__tablename__'):
                if cls.__name__.endswith('Schema'):
                    raise ModelConversionError(
                        "For safety, setup_schema can not be used when a "
                        "Model class ends with 'Schema'")

                class Meta:
                    model = cls
                    model_converter = self.ModelConverter
                    sqla_session = self.db.session

                schema_class_name = '%sSchema' % cls.__name__

                schema_class = type(schema_class_name, (ModelSchema,), {'Meta': Meta})

                setattr(cls, '__marshmallow__', schema_class)

        for model in models:
            add_schema(model)

    # noinspection PyMethodMayBeStatic
    def pre_setup_models(self):
        # Add versions supporting.
        # __versioned__ = {} must be added to all models that are to be versioned.
        from sqlalchemy_continuum.plugins import (
            property_mod_tracker, transaction_changes, activity)
        from sqlalchemy_continuum import make_versioned
        plugins = (
            property_mod_tracker.PropertyModTrackerPlugin(),
            transaction_changes.TransactionChangesPlugin(),
            # activity.ActivityPlugin()
        )
        make_versioned(user_cls=None, plugins=plugins)

    def post_setup_models(self, installed_models):
        import sqlalchemy as sa
        sa.orm.configure_mappers()

    def setup_extra_models(self):
        pass

    def setup_models(self):
        self.pre_setup_models()

        logger.debug('\\_ Models loading started.')
        for module in self.get_models_modules():
            importlib.import_module(module)
            logger.debug('  \\_ Models from `%s` loaded.' % module)

        self.setup_extra_models()

        installed_models = self.get_models()

        self.post_setup_models(installed_models)

        logger.debug('\\_ Installed models:')
        for model in installed_models:
            logger.debug('  \\_ Model %s.' % class_name(model))

        self.update_models(installed_models)

    def pre_setup(self):
        pass

    def post_setup(self):
        pass

    def setup(self):
        """Setup application."""
        logger.debug('Application setup started.')
        self.pre_setup()
        self.setup_models()
        self.post_setup()
        logger.debug('Application setup finished.')

    @property
    @lru_cache()
    def service(self):
        """
        Returns an instance of service class ``self.service_class``.
        """
        service_class = import_string(self.service_class)
        service_instance = service_class(app=self)
        return service_instance

    @property
    @lru_cache()
    def metadata(self):
        return {
            'name': self.config.APPLICATION_NAME,
            'title': str(self.config.APPLICATION_VERBOSE_NAME),
            'icon_class': self.config.APPLICATION_ICON_CLASS,
            'description': str(self.config.APPLICATION_DESCRIPTION),
            'color': self.config.APPLICATION_COLOR,
            'version': self.version,
            'debug': self.debug,
        }

    def reverse_url(self, name, *args, external=False):
        """
        Returns a URL path for handler named ``name``.
        """
        url = self.service.reverse_url(name, *args)
        if external:
            return urljoin(self.settings.LOCATION, url)
        return url

    def run(self, **kwargs):
        """Run server."""
        logger.debug('Go starting server...')
        self.service.start(**kwargs)
