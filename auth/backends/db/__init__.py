from anthill.framework.auth import get_user_model
from anthill.framework.auth.backends.authorizer import DefaultAuthorizer
from anthill.framework.auth.backends.realm import DatastoreRealm
from anthill.framework.auth.backends.db.storage import AlchemyStore
from anthill.framework.core.exceptions import ObjectDoesNotExist
from anthill.framework.utils.asynchronous import as_future


UserModel = get_user_model()


class BaseModelBackend:
    datastore_class = None

    def __init__(self):
        self.authorizer = self.create_authorizer()

    def create_authorizer(self):
        authorizer = DefaultAuthorizer()
        datastore = self.create_datastore()
        authorizer.init_realms((DatastoreRealm(storage=datastore),))
        return authorizer

    def create_datastore(self):
        return self.datastore_class()

    def can_authenticate(self, user):
        """
        Reject users with is_active=False.
        Custom user models that don't have that attribute are allowed.
        """
        is_active = getattr(user, 'is_active', None)
        return is_active or is_active is None


class ModelBackend(BaseModelBackend):
    """Authenticates against settings.AUTH_USER_MODEL."""
    datastore_class = AlchemyStore

    @as_future
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        user = UserModel.query.filter_by(username=username).first()
        if user is None:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a nonexistent user.
            UserModel(username=None, email=None).set_password(password)
        else:
            if user.check_password(password) and self.can_authenticate(user):
                return user

    # noinspection PyMethodMayBeStatic
    def get_permissions(self, user):
        return user.perms

    # noinspection PyMethodMayBeStatic
    def get_roles(self, user):
        return user.roles

    @as_future
    def is_permitted(self, user, permission_s):
        return self.authorizer.is_permitted(user.username, permission_s, log_results=True)

    @as_future
    def is_permitted_collective(self, user, permission_s, logical_operator=all):
        return self.authorizer.is_permitted_collective(user.username, permission_s,
                                                       logical_operator)

    @as_future
    def check_permission(self, user, permission_s, logical_operator=all):
        return self.authorizer.check_permission(user.username, permission_s,
                                                logical_operator)

    @as_future
    def has_role(self, user, role_s):
        return self.authorizer.has_role(user.username, role_s, log_results=True)

    @as_future
    def has_role_collective(self, user, role_s, logical_operator=all):
        return self.authorizer.has_role_collective(user.username, role_s,
                                                   logical_operator)

    @as_future
    def check_role(self, user, role_s, logical_operator=all):
        return self.authorizer.check_role(user.username, role_s, logical_operator)

    @as_future
    def get_user(self, user_id):
        user = UserModel.query.get(user_id)
        if user is None:
            raise ObjectDoesNotExist('User does not exist.')
        else:
            if self.can_authenticate(user):
                return user


class AllowAllUsersModelBackend(ModelBackend):
    def can_authenticate(self, user):
        return True
