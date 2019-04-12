"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
"""

from anthill.framework.auth.backends.authorizer import DefaultPermissionVerifier, Permission
from anthill.framework.auth.backends.db.storage import AlchemyStore
from anthill.framework.core.cache import cache
from .abcs import BaseAuthorizingRealm
from uuid import uuid4
import logging
import functools


logger = logging.getLogger('anthill.application')


DEFAULT_CACHE_TIMEOUT = 300  # 5min


def cached(key, timeout=DEFAULT_CACHE_TIMEOUT):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            k = key() if callable(key) else key
            result = cache.get(k)
            if result is None:
                result = func(*args, **kwargs)
                cache.set(k, result, timeout)
            return result
        return wrapper
    return decorator


class DatastoreRealm(BaseAuthorizingRealm):
    """
    A Realm interprets information from a datastore.
    """
    def __init__(self,
                 name='datastore_realm_' + str(uuid4()),
                 storage=AlchemyStore(),
                 permission_verifier=DefaultPermissionVerifier()):
        self.name = name
        self.storage = storage
        self.permission_verifier = permission_verifier

    def clear_cached_authorization_info(self, identifiers):
        pass

    def do_clear_cache(self, identifiers):
        """
        :type identifiers: SimpleRealmCollection
        """
        pass

    def get_authzd_permissions(self, identifier, perm_domain):
        """
        :type identifier: str
        :type perm_domain: str
        :returns: a list of relevant json blobs, each a list of permission dicts
        """
        cache_key = ':'.join([self.name, 'authorization', 'permissions', identifier])

        def query_permissions(self_):
            msg = ("Could not obtain cached permissions for [{0}]. "
                   "Will try to acquire permissions from account store."
                   .format(identifier))
            logger.debug(msg)

            # permissions is a dict: {'domain': json blob of lists of dicts}
            permissions = self_.storage.get_authz_permissions(identifier)
            if not permissions:
                raise ValueError(
                    "Could not get permissions from storage for {0}".format(identifier))
            return permissions

        if self.storage.allow_caching:
            query_permissions = cached(cache_key, timeout=300)(query_permissions)
        queried_permissions = query_permissions(self)

        related_perms = [
            queried_permissions.get('*'),
            queried_permissions.get(perm_domain)
        ]

        return related_perms

    def get_authzd_roles(self, identifier):
        cache_key = ':'.join([self.name, 'authorization', 'roles', identifier])

        def query_roles(self_):
            msg = ("Could not obtain cached roles for [{0}]. "
                   "Will try to acquire roles from account store."
                   .format(identifier))
            logger.debug(msg)

            roles_ = self_.storage.get_authz_roles(identifier)
            if not roles_:
                raise ValueError(
                    "Could not get roles from storage for {0}".format(identifier))
            return roles_

        if self.storage.allow_caching:
            query_roles = cached(cache_key, timeout=300)(query_roles)
        roles = query_roles(self)

        return set(roles)

    def is_permitted(self, identifier, permission_s):
        """
        If the authorization info cannot be obtained from the accountstore,
        permission check tuple yields False.
        :type identifier: str
        :param permission_s: a collection of one or more permissions, represented
                             as string-based permissions or Permission objects
                             and NEVER comingled types
        :type permission_s: list of string(s)
        :yields: tuple(Permission, Boolean)
        """
        for required in permission_s:
            domain = Permission.get_domain(required)

            # assigned is a list of json blobs:
            assigned = self.get_authzd_permissions(identifier, domain)

            is_permitted = False
            for perms_blob in assigned:
                is_permitted = self.permission_verifier.\
                    is_permitted_from_json(required, perms_blob)

            yield (required, is_permitted)

    def has_role(self, identifier, required_role_s):
        """
        Confirms whether a subject is a member of one or more roles.
        If the authorization info cannot be obtained from the accountstore,
        role check tuple yields False.
        :type identifier: str
        :param required_role_s: a collection of 1..N Role identifiers
        :type required_role_s: Set of String(s)
        :yields: tuple(role, Boolean)
        """
        # assigned_role_s is a set
        assigned_role_s = self.get_authzd_roles(identifier)

        if not assigned_role_s:
            logger.warning(
                'has_role:  no roles obtained from storage for [{0}]'.format(identifier))
            for role in required_role_s:
                yield (role, False)
        else:
            for role in required_role_s:
                hasrole = ({role} <= assigned_role_s)
                yield (role, hasrole)
