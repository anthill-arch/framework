from .core.strategy import BaseStrategy, BaseTemplateStrategy
from .core.utils import build_absolute_uri
from tornado.template import Loader, Template
from anthill.framework.utils.crypto import get_random_string
from anthill.framework.utils.encoding import force_text
from anthill.framework.utils.functional import Promise
from anthill.framework.auth import authenticate
from anthill.framework.conf import settings
from anthill.framework.utils.asynchronous import as_future
import six
import os


class TornadoTemplateStrategy(BaseTemplateStrategy):
    def render_template(self, tpl, context):
        try:
            path, tpl = tpl.rsplit('/', 1)
        except ValueError:
            path = ''
        path = os.path.join(settings.TEMPLATE_PATH, 'social', path)
        return Loader(path).load(tpl).generate(**context)

    def render_string(self, html, context):
        return Template(html).generate(**context)


class TornadoStrategy(BaseStrategy):
    DEFAULT_TEMPLATE_STRATEGY = TornadoTemplateStrategy

    def __init__(self, storage, request_handler, tpl=None):
        self.request_handler = request_handler
        self.request = self.request_handler.request if self.request_handler else None
        self.session = self.request_handler.session if self.request_handler else {}
        super().__init__(storage, tpl)

    def get_setting(self, name):
        """Return value for given setting name."""
        value = getattr(settings, name)
        # Force text on URL named settings that are instance of Promise
        if name.endswith('_URL'):
            if isinstance(value, Promise):
                value = force_text(value)
            value = self.request_handler.resolve_url(value)
        return value

    def request_data(self, merge=True):
        """Return current request data (POST or GET)."""
        # Multiple valued arguments not supported yet
        if not self.request:
            return {}
        return {
            (key, val[0].decode()) for key, val
            in six.iteritems(self.request.arguments)
        }

    def request_host(self):
        """Return current host value."""
        return self.request.host

    def request_is_secure(self):
        """Is the request using HTTPS?"""
        return self.request_handler.is_secure()

    def redirect(self, url):
        self.request_handler.redirect(url)

    def html(self, content):
        self.request_handler.write(content)

    def session_get(self, name, default=None):
        return self.session.get(name, default)

    def session_set(self, name, value):
        self.session[name] = value
        if hasattr(self.session, 'modified'):
            self.session.modified = True

    def session_pop(self, name):
        return self.session.pop(name, None)

    def session_setdefault(self, name, value):
        return self.session.setdefault(name, value)

    def build_absolute_uri(self, path=None):
        if self.request:
            return build_absolute_uri(
                '{0}://{1}'.format(self.request.protocol, self.request.host), path)
        else:
            return path

    async def authenticate(self, backend, *args, **kwargs):
        """Trigger the authentication mechanism tied to the current framework."""
        kwargs['strategy'] = self
        kwargs['storage'] = self.storage
        kwargs['backend'] = backend
        args, kwargs = self.clean_authenticate_args(*args, **kwargs)
        return await backend.authenticate(*args, **kwargs)

    def get_language(self):
        """Return current language."""
        return self.request_handler.locale

    def random_string(self, length=12, chars=BaseStrategy.ALLOWED_CHARS):
        return get_random_string(length, chars)

    def request_path(self):
        """Path of the current request."""
        return self.request.path

    def request_port(self):
        """Port in use for this request."""
        return self.request_handler.application.app.port

    def request_get(self):
        pass

    def request_post(self):
        pass
