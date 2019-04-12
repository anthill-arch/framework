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

from anthill.framework.auth.backends.exceptions import UnauthorizedException
from .abcs import (
    BasePermission, BasePermissionVerifier, BaseAuthorizer, BaseAuthorizingRealm)
import itertools
import logging
import json
import collections


logger = logging.getLogger('anthill.application')


class Permission(BasePermission):
    """
    In this example, the first token is the *domain* that is being operated on
    and the second token is the *action* that is performed. Each level can contain
    multiple values.  Given support for multiple values, you could simply grant
    a user the permission 'blogpost:view,edit,create', granting the user
    access to perform ``view``, ``edit``, and ``create`` actions in the ``blogpost``
    *domain*. Then you could check whether the user has the ``'blogpost:create'``
    permission by calling:::
        subject.is_permitted(['blogpost:create'])
    (which would return true)

    In addition to granting multiple permissions using a single string, you can
    grant all permission for a particular level:
        * If you want to grant a user permission to perform all actions in the
        ``blogpost`` domain, you could simply grant the user ``'blogpost:*'``.
        With this permission granted, any permission check for ``'blogpost:XXX'```
        will return ``True``.
        * It is also possible to use the wildcard token at the domain
        level (or both levels), granting a user the ``'view'`` action across all
        domains: ``'*:view'``.

    Instance-level Access Control
    -----------------------------
    Another usage of ``Permission`` is to model instance-level
    Access Control Lists (ACLs). In this scenario, you use three tokens:
        * the first token is the *domain*
        * the second token is the *action*
        * the third token is the *instance* that is acted upon (target)
    For example, suppose you grant a user ``'blogpost:edit:12,13,18'``.
    In this example, assume that the third token contains system identifiers of
    blogposts. That would allow the user to edit blogpost with id ``12``, ``13``, and ``18``.
    Representing permissions in this manner is an extremely powerful way to
    express permissions as you can state permissions like:
        *``'blogpost:*:13'``, granting a user permission to perform all actions for blogpost ``13``,
        *``'blogpost:view,create,edit:*'``, granting a user permission to ``view``,
                                            ``create``, or ``edit`` *any* blogpost
        *``'blogpost:*:*'``, granting a user permission to perform *any* action on *any* blogpost
    To perform checks against these instance-level permissions, the application
    should include the instance ID in the permission check like so:::
        subject.is_permitted(['blogpost:edit:13'])
    """

    WILDCARD_TOKEN = '*'
    PART_DIVIDER_TOKEN = ':'
    SUBPART_DIVIDER_TOKEN = ','

    def __init__(self, wildcard_perm=None, parts=None):
        if wildcard_perm:
            parts = iter(self.partify(wildcard_perm))
            try:
                self.domain = next(parts)
                self.actions = next(parts)
                self.targets = next(parts)
            except StopIteration:
                raise ValueError("Permission cannot identify required parts from string")
        else:
            self.domain = {parts.get('domain', self.WILDCARD_TOKEN)}
            self.actions = set(parts.get('actions', self.WILDCARD_TOKEN))
            self.targets = set(parts.get('targets', self.WILDCARD_TOKEN))

    def partify(self, wildcard_perm):
        return [set(a.strip() for a in y.split(self.SUBPART_DIVIDER_TOKEN))
                for y in [x[0] if x[0] else x[1]
                          for x in itertools.zip_longest(
                    wildcard_perm.split(self.PART_DIVIDER_TOKEN),
                    [self.WILDCARD_TOKEN] * 3)]
                ]

    def implies(self, permission):
        if self.domain != {self.WILDCARD_TOKEN}:
            if self.domain != permission.domain:
                return False

        if self.actions != {self.WILDCARD_TOKEN}:
            if not self.actions >= permission.actions:
                return False

        if self.targets != {self.WILDCARD_TOKEN}:
            if not self.actions >= permission.actions:
                return False

        return True

    @staticmethod
    def get_domain(wildcard_perm):
        domain = wildcard_perm.split(Permission.PART_DIVIDER_TOKEN)[0].strip()
        if not domain:
            return Permission.WILDCARD_TOKEN
        return domain


class DefaultPermissionVerifier(BasePermissionVerifier):
    def is_permitted_from_str(self, required, assigned):
        required_perm = Permission(wildcard_perm=required)
        for perm_str in assigned:
            assigned_perm = Permission(wildcard_perm=perm_str)
            if assigned_perm.implies(required_perm):
                return True
        return False

    def is_permitted_from_json(self, required, assigned):
        required = Permission(wildcard_perm=required)
        the_parts = json.loads(assigned.decode('utf-8'))
        for parts in the_parts:
            assigned_perm = Permission(parts=parts)
            if assigned_perm.implies(required):
                return True
        return False


class DefaultAuthorizer(BaseAuthorizer):
    def __init__(self):
        self.realms = None

    def __repr__(self):
        return "DefaultAuthorizer(realms={0})".format(self.realms)

    def init_realms(self, realms):
        """
        :type realms: tuple
        """
        self.realms = tuple(realm for realm in realms
                            if isinstance(realm, BaseAuthorizingRealm))

    def assert_realms_configured(self):
        if not self.realms:
            msg = ("Configuration error: No realms have been configured! "
                   "One or more realms must be present to execute an "
                   "authorization operation.")
            raise ValueError(msg)

    def _has_role(self, identifier, role_s):
        """
        :type identifier: str
        :type role_s: Set of String(s)
        """
        for realm in self.realms:
            # the realm's has_role returns a generator
            yield from realm.has_role(identifier, role_s)

    def _is_permitted(self, identifier, permission_s):
        """
        :type identifier: str
        :param permission_s: a collection of 1..N permissions
        :type permission_s: List of permission string(s)
        """
        for realm in self.realms:
            # the realm's is_permitted returns a generator
            yield from realm.is_permitted(identifier, permission_s)

    def is_permitted(self, identifier, permission_s, log_results=True):
        """
        :type identifier: str
        :param permission_s: a collection of 1..N permissions
        :type permission_s: List of permission string(s)
        :param log_results:  states whether to log results (True) or allow the
                             calling method to do so instead (False)
        :type log_results:  bool
        :returns: a set of tuple(s), containing the Permission and a Boolean
                  indicating whether the permission is granted
        """
        self.assert_realms_configured()

        results = collections.defaultdict(bool)  # defaults to False

        is_permitted_results = self._is_permitted(identifier, permission_s)

        for permission, is_permitted in is_permitted_results:
            # permit expected format is: (Permission, Boolean)
            # As long as one realm returns True for a Permission, that Permission
            # is granted.  Given that (True or False == True), assign accordingly:
            results[permission] = results[permission] or is_permitted

        results = set(results.items())
        return results

    def is_permitted_collective(self, identifier, permission_s, logical_operator):
        """
        :type identifier: str
        :param permission_s: a collection of 1..N permissions
        :type permission_s: List of Permission object(s) or String(s)
        :param logical_operator:  indicates whether all or at least one
                                  permission check is true (any)
        :type: any OR all (from python standard library)
        :returns: a Boolean
        """
        self.assert_realms_configured()

        # interim_results is a set of tuples:
        interim_results = self.is_permitted(identifier, permission_s,
                                            log_results=False)

        results = logical_operator(is_permitted for perm, is_permitted
                                   in interim_results)

        return results

    def check_permission(self, identifier, permission_s, logical_operator):
        """
        :type identifier: str
        :param permission_s: a collection of 1..N permissions
        :type permission_s: List of Permission objects or Strings
        :param logical_operator:  indicates whether all or at least one
                                  permission check is true (any)
        :type: any OR all (from python standard library)
        :raises UnauthorizedException: if any permission is unauthorized
        """
        self.assert_realms_configured()
        permitted = self.is_permitted_collective(identifier,
                                                 permission_s, logical_operator)
        if not permitted:
            msg = "Subject lacks permission(s) to satisfy logical operation"
            raise UnauthorizedException(msg)

    def has_role(self, identifier, role_s, log_results=True):
        """
        :type identifier: str
        :param role_s: a collection of 1..N Role identifiers
        :type role_s: Set of String(s)
        :param log_results:  states whether to log results (True) or allow the
                             calling method to do so instead (False)
        :type log_results:  bool
        :returns: a set of tuple(s), containing the role and a Boolean
                  indicating whether the user is a member of the Role
        """
        self.assert_realms_configured()

        results = collections.defaultdict(bool)  # defaults to False

        for role, has_role in self._has_role(identifier, role_s):
            # checkrole expected format is: (role, Boolean)
            # As long as one realm returns True for a role, a subject is
            # considered a member of that Role.
            # Given that (True or False == True), assign accordingly:
            results[role] = results[role] or has_role

        results = set(results.items())
        return results

    def has_role_collective(self, identifier, role_s, logical_operator):
        """
        :type identifier: str
        :param role_s: a collection of 1..N Role identifiers
        :type role_s: Set of String(s)
        :param logical_operator:  indicates whether all or at least one
                                  permission check is true (any)
        :type: any OR all (from python standard library)
        :returns: a Boolean
        """
        self.assert_realms_configured()

        # interim_results is a set of tuples:
        interim_results = self.has_role(identifier, role_s, log_results=False)

        results = logical_operator(has_role for role, has_role in interim_results)

        return results

    def check_role(self, identifier, role_s, logical_operator):
        """
        :type identifier: str
        :param role_s: 1..N role identifiers
        :type role_s:  a String or Set of Strings
        :param logical_operator:  indicates whether all or at least one
                                  permission check is true (any)
        :type: any OR all (from python standard library)
        :raises UnauthorizedException: if Subject not assigned to all roles
        """
        self.assert_realms_configured()
        has_role_s = self.has_role_collective(identifier, role_s, logical_operator)
        if not has_role_s:
            msg = "Subject does not have role(s) assigned."
            raise UnauthorizedException(msg)
