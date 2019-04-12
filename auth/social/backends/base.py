from anthill.framework.auth.social.core.backends import base
import inspect


# noinspection PyAbstractClass
class BaseAuth(base.BaseAuth):
    """
    A authentication backend that authenticates the user based on
    the provider response.
    """

    async def start(self):
        if await self.uses_redirect():
            return self.strategy.redirect(self.auth_url())
        else:
            return self.strategy.html(await self.auth_html())

    def auth_complete(self, *args, **kwargs):
        """Completes loging process, must return user instance."""
        raise NotImplementedError('Implement in subclass')

    def complete(self, *args, **kwargs):
        return self.auth_complete(*args, **kwargs)

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
                pipeline_index < 0 or pipeline_index >= len(pipeline):
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

    def get_user(self, user_id):
        """Return user with given ID from the User model used by this backend."""
        return self.strategy.get_user(user_id)

    async def continue_pipeline(self, partial):
        """Continue previous halted pipeline."""
        return await self.strategy.authenticate(
            self, pipeline_index=partial.next_step, *partial.args, **partial.kwargs)
