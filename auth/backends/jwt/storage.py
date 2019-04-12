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
from tornado.web import RequestHandler
from ..abcs import AuthorizationAccountStore
from ..authorizer import Permission
import functools
import json


def request_context(fn):
    @functools.wraps(fn)
    def wrap(*args, **kwargs):
        handler = args[0].handler  # obtain from self
        if 'handler' not in kwargs or kwargs['handler'] is None:
            kwargs['handler'] = handler
        return fn(*args, **kwargs)
    return wrap


class JWTStore(AuthorizationAccountStore):
    allow_caching = False

    def __init__(self, handler: RequestHandler = None):
        self.handler = handler

    @request_context
    def get_authz_permissions(self, identifier, handler: RequestHandler = None):
        payload = handler.current_user.authz_info
        permissions = payload.get('permissions', '')
        try:
            permissions = json.loads(permissions)
        except json.JSONDecodeError:
            permissions = [p.strip() for p in permissions.split(',')]
        permissions = map(lambda p: (Permission.get_domain(p), p), permissions)
        # TODO: permissions is a dict: {'domain': json blob of lists of dicts}
        return permissions

    @request_context
    def get_authz_roles(self, identifier, handler: RequestHandler = None):
        payload = handler.current_user.authz_info
        roles = payload.get('roles', '')
        try:
            roles = json.loads(roles)
        except json.JSONDecodeError:
            roles = [r.strip() for r in roles.split(',')]
        return roles
