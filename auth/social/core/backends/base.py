from anthill.framework.utils.asynchronous import as_future
from ..utils import SSLHttpAdapter, module_member, parse_qs, user_agent
from requests import request, ConnectionError
from social_core.backends import base
from ..exceptions import AuthFailed
import time
import inspect


class BaseAuth(base.BaseAuth):
    """
    A authentication backend that authenticates the user based on
    the provider response.
    """
    async def start(self):
        if inspect.iscoroutinefunction(self.uses_redirect):
            uses_redirect = await self.uses_redirect()
        else:
            uses_redirect = self.uses_redirect()
        if uses_redirect:
            return self.strategy.redirect(await self.auth_url())
        else:
            return self.strategy.html(await self.auth_html())

    async def complete(self, *args, **kwargs):
        return await self.auth_complete(*args, **kwargs)

    async def auth_url(self):
        """Must return redirect URL to auth provider."""
        raise NotImplementedError('Implement in subclass')

    async def auth_html(self):
        """Must return login HTML content returned by provider."""
        raise NotImplementedError('Implement in subclass')

    async def auth_complete(self, *args, **kwargs):
        """Completes login process, must return user instance."""
        raise NotImplementedError('Implement in subclass')

    async def authenticate(self, *args, **kwargs):
        """
        Authenticate user using social credentials.

        Authentication is made if this is the correct backend, backend
        verification is made by kwargs inspection for current backend
        name presence.
        """
        # Validate backend and arguments. Require that the Social Auth
        # response be passed in as a keyword argument, to make sure we
        # don't match the username/password calling conventions of
        # authenticate.
        if 'backend' not in kwargs or kwargs['backend'].name != self.name or \
           'strategy' not in kwargs or 'response' not in kwargs:
            return None

        self.strategy = kwargs.get('strategy') or self.strategy
        self.redirect_uri = kwargs.get('redirect_uri') or self.redirect_uri
        self.data = self.strategy.request_data()
        kwargs.setdefault('is_new', False)
        pipeline = self.strategy.get_pipeline(self)
        args, kwargs = self.strategy.clean_authenticate_args(*args, **kwargs)
        return await self.pipeline(pipeline, *args, **kwargs)

    async def pipeline(self, pipeline, pipeline_index=0, *args, **kwargs):
        out = await self.run_pipeline(pipeline, pipeline_index, *args, **kwargs)
        if not isinstance(out, dict):
            return out
        user = out.get('user')
        if user:
            user.social_user = out.get('social')
            user.is_new = out.get('is_new')
        return user

    async def disconnect(self, *args, **kwargs):
        pipeline = self.strategy.get_disconnect_pipeline(self)
        kwargs['name'] = self.name
        kwargs['user_storage'] = self.strategy.storage.user
        return await self.run_pipeline(pipeline, *args, **kwargs)

    async def run_pipeline(self, pipeline, pipeline_index=0, *args, **kwargs):
        out = kwargs.copy()
        out.setdefault('strategy', self.strategy)
        out.setdefault('backend', out.pop(self.name, None) or self)
        out.setdefault('request', self.strategy.request_data())
        out.setdefault('details', {})

        if not isinstance(pipeline_index, int) or \
           pipeline_index < 0 or \
           pipeline_index >= len(pipeline):
            pipeline_index = 0

        for idx, name in enumerate(pipeline[pipeline_index:]):
            out['pipeline_index'] = pipeline_index + idx
            func = module_member(name)
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **out) or {}
            else:
                result = func(*args, **out) or {}
            if not isinstance(result, dict):
                return result
            out.update(result)
        return out

    async def get_user_details(self, response):
        """
        Must return user details in a know internal struct:
        {
            'username': <username if any>,
            'email': <user email if any>,
            'fullname': <user full name if any>,
            'first_name': <user first name if any>,
            'last_name': <user last name if any>
        }
        """
        raise NotImplementedError('Implement in subclass')

    def get_user(self, user_id):
        """
        Return user with given ID from the User model used by this backend.
        This is called by django.contrib.auth.middleware.
        """
        return self.strategy.get_user(user_id)

    async def continue_pipeline(self, partial):
        """Continue previous halted pipeline."""
        return await self.strategy.authenticate(self,
                                                pipeline_index=partial.next_step,
                                                *partial.args,
                                                **partial.kwargs)

    @as_future
    def request(self, url, method='GET', *args, **kwargs):
        kwargs.setdefault('headers', {})
        if self.setting('VERIFY_SSL') is not None:
            kwargs.setdefault('verify', self.setting('VERIFY_SSL'))
        kwargs.setdefault('timeout', self.setting('REQUESTS_TIMEOUT') or
                          self.setting('URLOPEN_TIMEOUT'))
        if self.SEND_USER_AGENT and 'User-Agent' not in kwargs['headers']:
            kwargs['headers']['User-Agent'] = (self.setting('USER_AGENT') or
                                               user_agent())

        try:
            if self.SSL_PROTOCOL:
                session = SSLHttpAdapter.ssl_adapter_session(self.SSL_PROTOCOL)
                response = session.request(method, url, *args, **kwargs)
            else:
                response = request(method, url, *args, **kwargs)
        except ConnectionError as err:
            raise AuthFailed(self, str(err))
        response.raise_for_status()
        return response

    async def get_json(self, url, *args, **kwargs):
        response = await self.request(url, *args, **kwargs)
        return response.json()

    async def get_querystring(self, url, *args, **kwargs):
        response = await self.request(url, *args, **kwargs)
        return parse_qs(response.text)
