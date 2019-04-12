from anthill.framework.auth.backends.authorizer import DefaultAuthorizer
from anthill.framework.auth.backends.realm import DatastoreRealm
from anthill.framework.utils.module_loading import import_string
from anthill.framework.conf import settings


DEFAULTS = {
    'AUTHORIZER_CLASS': 'anthill.framework.auth.backends.authorizer.DefaultAuthorizer',
    'DATASTORE_REALMS': [
        {
            'REALM_CLASS': 'anthill.framework.auth.backends.realm.DatastoreRealm',
            'DATASTORE_CLASS': 'anthill.framework.auth.backends.jwt.storage.JWTStore',
        },
    ]
}


BACKEND_MANAGER_SETTINGS = getattr(settings, 'AUTHENTICATION_BACKEND_MANAGER', DEFAULTS)

AUTHORIZER_CLASS = BACKEND_MANAGER_SETTINGS['AUTHORIZER_CLASS']
DATASTORE_REALMS = BACKEND_MANAGER_SETTINGS['DATASTORE_REALMS']


class BackendManager:
    authorizer_class = AUTHORIZER_CLASS
    datastore_realms = DATASTORE_REALMS

    def __init__(self):
        self.authorizer = self.create_authorizer()

    def create_authorizer(self):
        authorizer = import_string(self.authorizer_class)()
        authorizer.init_realms(self.load_realms())
        return authorizer

    def load_realms(self):
        for realm_ in self.datastore_realms:
            realm_class = import_string(realm_['REALM_CLASS'])
            datastore_class = import_string(realm_['DATASTORE_CLASS'])
            yield realm_class(storage=datastore_class())
