from anthill.framework.handlers import RequestHandler, TemplateMixin
from graphql.execution.executors.asyncio import AsyncioExecutor
from graphql.type.schema import GraphQLSchema
from anthill.framework.conf import settings
from tornado.escape import json_decode, json_encode
from graphql.error import GraphQLError, format_error as format_graphql_error
from anthill.framework.http import HttpForbiddenError, HttpBadRequestError
from tornado.log import app_log
from tornado.escape import to_basestring
from graphql.execution import ExecutionResult
from tornado.web import HTTPError
import inspect
import importlib
import six

DEFAULTS = {
    'SCHEMA': None,
    'MIDDLEWARE': ()
}

# List of settings that may be in string import notation.
IMPORT_STRINGS = (
    'MIDDLEWARE',
    'SCHEMA',
)


def perform_import(val, setting_name):
    """
    If the given setting is a string import notation,
    then perform the necessary import or imports.
    """
    if val is None:
        return None
    elif isinstance(val, six.string_types):
        return import_from_string(val, setting_name)
    elif isinstance(val, (list, tuple)):
        return [import_from_string(item, setting_name) for item in val]
    return val


def import_from_string(val, setting_name):
    """
    Attempt to import a class from a string representation.
    """
    try:
        parts = val.split('.')
        module_path, class_name = '.'.join(parts[:-1]), parts[-1]
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        msg = "Could not import '%s' for Graphene setting '%s'. " \
              "%s: %s." % (val, setting_name, e.__class__.__name__, e)
        raise ImportError(msg)


class GrapheneSettings:
    """
    A settings object, that allows API settings to be accessed as properties.
    Any setting with string import paths will be automatically resolved
    and return the class, rather than the string literal.
    """

    def __init__(self, user_settings=None, defaults=None, import_strings=None):
        if user_settings:
            self._user_settings = user_settings
        self.defaults = defaults or DEFAULTS
        self.import_strings = import_strings or IMPORT_STRINGS

    @property
    def user_settings(self):
        if not hasattr(self, '_user_settings'):
            self._user_settings = getattr(settings, 'GRAPHENE', {})
        return self._user_settings

    def __getattr__(self, attr):
        if attr not in self.defaults:
            raise AttributeError("Invalid Graphene setting: '%s'" % attr)

        try:
            # Check if present in user settings
            val = self.user_settings[attr]
        except KeyError:
            # Fall back to defaults
            val = self.defaults[attr]

        # Coerce import strings into classes
        if attr in self.import_strings:
            val = perform_import(val, attr)

        # Cache the result
        setattr(self, attr, val)
        return val


graphene_settings = GrapheneSettings(None, DEFAULTS, IMPORT_STRINGS)


def instantiate_middleware(middlewares):
    for middleware in middlewares:
        if inspect.isclass(middleware):
            yield middleware()
            continue
        yield middleware


def error_status(exception):
    if isinstance(exception, HTTPError):
        return exception.status_code
    return 500


class GraphQLHandler(TemplateMixin, RequestHandler):
    SUPPORTED_METHODS = ('GET', 'POST')

    graphiql_template = 'graphene/graphiql.html'
    graphiql_version = '0.11.11'

    schema = None
    middleware = None
    graphiql = False
    executor = None
    root = None
    pretty = False
    batch = False
    context = None

    def initialize(
            self,
            graphiql_template=None,
            graphiql_version=None,
            schema=None,
            middleware=None,
            graphiql=False,
            executor=None,
            root=None,
            pretty=False,
            batch=False,
            context=None):
        super().initialize(graphiql_template)
        if not schema:
            schema = graphene_settings.SCHEMA
        if middleware is None:
            middleware = graphene_settings.MIDDLEWARE
        if middleware is not None:
            self.middleware = list(instantiate_middleware(middleware))
        if not executor:
            executor = AsyncioExecutor()
        self.graphiql_version = graphiql_version
        self.schema = self.schema or schema
        self.graphiql = self.graphiql or graphiql
        self.executor = self.executor or executor
        self.root = root
        self.pretty = pretty
        self.batch = batch
        self.context = context

    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.template_name = self.graphiql_template
        self.enable_async = isinstance(self.executor, AsyncioExecutor)
        assert isinstance(self.schema, GraphQLSchema), \
            'A Schema is required to be provided to %s.' % self.__class__.__name__
        assert isinstance(self.executor, AsyncioExecutor), \
            'An executor is required to be subclassed from `AsyncioExecutor`.'
        assert not all((self.graphiql, self.batch)), \
            'Use either graphiql or batch processing'

    async def post(self):
        try:
            data = self.parse_body()
            if self.batch:
                responses = []
                for entry in data:
                    responses.append(await self.get_graphql_response(entry))
                result = '[{}]'.format(','.join([response[0] for response in responses]))
                status_code = responses and max(responses, key=lambda response: response[1])[1] or 200
            else:
                result, status_code = await self.get_graphql_response(data)
        except Exception as e:
            if isinstance(e, (HTTPError,)):
                app_log.error('{0}'.format(e))
            else:
                app_log.exception('{0}'.format(e))
            status_code = error_status(e)
            result = json_encode({'errors': [self.format_error(e)]})

        self.set_status(status_code)
        self.write(result)

    def get(self):
        if self.is_graphiql():
            return self.render()
        raise HttpForbiddenError('Method `GET` not allowed.')

    def is_graphiql(self):
        return all([
            self.graphiql,
            self.request.method.lower() == 'get',
            'raw' not in self.request.query_arguments,
            settings.DEBUG,
            any([
                'text/html' in self.request.headers.get('accept', {}),
                '*/*' in self.request.headers.get('accept', {}),
            ]),
        ])

    def is_pretty(self):
        return any([
            self.pretty,
            self.is_graphiql(),
            # self.request.query_arguments('pretty')
        ])

    async def get_graphql_response(self, data):
        query, values, operation_name, id = self.get_graphql_params(data)
        execution_result = await self.execute_graphql_request(
            query, values, operation_name)

        status_code = 200
        if execution_result:
            response = {}

            if execution_result.errors:
                response['errors'] = [
                    self.format_error(e) for e in execution_result.errors]
                app_log.error(
                    '\n'.join(map(lambda e: e['message'], response['errors'])))

            if execution_result.invalid:
                status_code = 400
            else:
                response['data'] = execution_result.data

            if self.batch:
                response['id'] = id
                response['status'] = status_code

            result = json_encode(response)
        else:
            result = None

        return result, status_code

    async def execute_graphql_request(self, query, values, operation_name):
        if not query:
            if self.is_graphiql():
                return None
            raise HttpBadRequestError('Must provide query string.')
        try:
            result = await self.schema.execute(
                query,
                values=values,
                operation_name=operation_name,
                context=self.get_context(),
                middleware=self.middleware,
                return_promise=self.enable_async,
                root=self.root,
                executor=self.executor
            )
        except Exception as e:
            return ExecutionResult(errors=[e], invalid=True)
        return result

    def get_graphql_params(self, data):
        query = data.get('query')

        id = data.get('id')
        if id == 'null':
            id = None

        variables = data.get('variables')
        if variables and isinstance(variables, six.text_type):
            try:
                variables = json_decode(variables)
            except Exception as e:
                raise HttpBadRequestError(
                    'Variables are invalid JSON.', reason=str(e))

        operation_name = data.get('operationName')
        if operation_name == 'null':
            operation_name = None

        return query, variables, operation_name, id

    def get_template_namespace(self):
        namespace = super().get_template_namespace()
        namespace.update(graphiql_version=self.graphiql_version)
        return namespace

    def parse_body(self):
        content_type = self.get_content_type()

        if content_type == 'application/graphql':
            return {'query': to_basestring(self.request.body)}

        elif content_type == 'application/json':
            try:
                request_json = json_decode(self.request.body)
            except Exception as e:
                raise HttpBadRequestError(
                    'The received data is not a valid JSON query.', reason=str(e))
            if self.batch:
                assert isinstance(request_json, list), (
                    'Batch requests should receive a list, but received {}.'
                ).format(repr(request_json))
                assert len(request_json) > 0, (
                    'Received an empty list in the batch request.'
                )
            else:
                assert isinstance(request_json, dict), (
                    'The received data is not a valid JSON query.'
                )
            return request_json

        elif content_type in ('application/x-www-form-urlencoded', 'multipart/form-data'):
            return {
                k: self.decode_argument(v[0]) for k, v
                in self.request.arguments.items()
            }

        return {}

    def get_content_type(self):
        content_type = self.request.headers.get('Content-Type', 'text/plain')
        return content_type.split(';', 1)[0].lower()

    @staticmethod
    def format_error(error):
        if isinstance(error, GraphQLError):
            return format_graphql_error(error)
        elif isinstance(error, HTTPError):
            return {
                'message': error.log_message,
                'reason': error.reason
            }
        return {'message': six.text_type(error)}

    def get_context(self):
        if self.context and isinstance(self.context, dict):
            context = self.context.copy()
        else:
            context = {}
        if isinstance(context, dict) and 'request' not in context:
            context.update({'request': self.request})
        context.update({'handler': self})
        return context
