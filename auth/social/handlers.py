from anthill.framework.handlers import RequestHandler
from anthill.framework.auth.social.core.actions import (
    do_auth, do_complete, do_disconnect
)
from anthill.framework.auth import REDIRECT_FIELD_NAME
from anthill.framework.conf import settings
from anthill.framework.auth.social.core.utils import setting_name
from .utils import psa

NAMESPACE = getattr(settings, setting_name('URL_NAMESPACE'), None) or 'social'


class BaseHandler(RequestHandler):
    def user_id(self):
        return self.get_secure_cookie('user_id')

    def get_current_user(self):
        user_id = self.user_id()
        if user_id:
            return self.backend.strategy.get_user(int(user_id))

    def login_user(self, user):
        self.set_secure_cookie('user_id', str(user.id))


class AuthHandler(BaseHandler):
    async def get(self, backend):
        await self._auth(backend)

    async def post(self, backend):
        await self._auth(backend)

    @psa('{0}:complete'.format(NAMESPACE))
    async def _auth(self, backend):
        await do_auth(self.backend, redirect_name=REDIRECT_FIELD_NAME)


class CompleteHandler(BaseHandler):
    """Authentication complete handler."""

    async def get(self, backend):
        await self._complete(backend)

    async def post(self, backend):
        await self._complete(backend)

    @psa('{0}:complete'.format(NAMESPACE))
    async def _complete(self, backend):
        await do_complete(
            self.backend,
            login=lambda backend, user, social_user: self.login_user(user),
            user=self.get_current_user(),
            redirect_name=REDIRECT_FIELD_NAME
        )


class DisconnectHandler(BaseHandler):
    """Disconnects given backend from current logged in user."""

    async def post(self, backend, association_id=None):
        await do_disconnect(
            self.backend,
            user=self.get_current_user(),
            association_id=association_id,
            redirect_name=REDIRECT_FIELD_NAME
        )
