from anthill.framework.auth import get_user_model
from anthill.framework.auth.token.jwt.authentication import JSONWebTokenAuthentication
from anthill.framework.auth.backends.authorizer import DefaultAuthorizer
from anthill.framework.auth.backends.realm import DatastoreRealm
from anthill.framework.auth.backends.jwt.storage import JWTStore
from anthill.framework.auth.backends.db import BaseModelBackend


UserModel = get_user_model()


class JWTBackend(BaseModelBackend):
    """Authenticates against JWT authentication token."""

    datastore_class = JWTStore

    # noinspection PyMethodMayBeStatic
    async def authenticate(self, request):
        user, payload = await JSONWebTokenAuthentication().authenticate(request)
        user.authz_info = payload
        return user
