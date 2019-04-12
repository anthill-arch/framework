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
from anthill.framework.db import db
from sqlalchemy import case, cast, func, Text
from sqlalchemy.sql import Alias, ColumnElement
from sqlalchemy.ext.compiler import compiles
from anthill.framework.auth import get_user_model
from ..abcs import AuthorizationAccountStore
import functools

from .models import (
    Credential,
    CredentialType,
    Domain,
    Action,
    Resource,
    Permission,
    Role,
    role_membership as role_membership_table,
    role_permission as role_permission_table,
)

User = get_user_model()

# -------------------------------------------------------
# Following is a recipe used to address postgres-json related shortcomings
# in sqlalchemy v1.1.4. This recipe will eventually be deprecated
# ----------------------------------------------------------


class as_row(ColumnElement):
    def __init__(self, expr):
        assert isinstance(expr, Alias)
        self.expr = expr


@compiles(as_row)
def _gen_as_row(element, compiler, **kw):
    return compiler.visit_alias(element.expr, ashint=True, **kw)

# -------------------------------------------------------
# -------------------------------------------------------


def session_context(fn):
    """
    Handles session setup and teardown
    """
    @functools.wraps(fn)
    def wrap(*args, **kwargs):
        session = args[0].session  # obtain from self
        result = fn(*args, session=session, **kwargs)
        session.close()
        return result
    return wrap


class AlchemyStore(AuthorizationAccountStore):
    """
    AlchemyStore provides the realm-facing API to the relational database
    that is managed through the SQLAlchemy ORM.
    step 1: generate an orm query
    step 2: execute the query
    step 3: return results
    """

    def __init__(self, session=None):
        self.session = db.session if session is None else session

    def _get_user_query(self, session, identifier):
        return session.query(User).filter(User.identifier == identifier)

    def _get_permissions_query(self, session, identifier):
        """
        select domain, json_agg(parts) as permissions from
            (select domain, row_to_json(r) as parts from
                    (select domain, action, array_agg(distinct target) as target from
                        (select (case when domain is null then '*' else domain end) as domain,
                                (case when target is null then '*' else target end) as target,
                                array_agg(distinct (case when action is null then '*' else action end)) as action
                           from permission
                          group by domain, target
                         ) x
                      group by domain, action)
              r) parts
        group by domain;
        """
        thedomain = case([(Domain.name is None, '*')], else_=Domain.name)
        theaction = case([(Action.name is None, '*')], else_=Action.name)
        theresource = case([(Resource.name is None, '*')], else_=Resource.name)

        action_agg = func.array_agg(theaction.distinct())

        stmt1 = (
            session.query(Permission.domain_id,
                          thedomain.label('domain'),
                          Permission.resource_id,
                          theresource.label('resource'),
                          action_agg.label('action')).
            select_from(User).
            join(role_membership_table, User.id == role_membership_table.c.user_id).
            join(role_permission_table, role_membership_table.c.role_id == role_permission_table.c.role_id).
            join(Permission, role_permission_table.c.permission_id == Permission.id).
            outerjoin(Domain, Permission.domain_id == Domain.id).
            outerjoin(Action, Permission.action_id == Action.id).
            outerjoin(Resource, Permission.resource_id == Resource.id).
            filter(User.identifier == identifier).
            group_by(Permission.domain_id, Domain.name, Permission.resource_id, Resource.name)).subquery()

        stmt2 = (session.query(stmt1.c.domain,
                               stmt1.c.action,
                               func.array_agg(stmt1.c.resource.distinct()).label('resource')).
                 select_from(stmt1).
                 group_by(stmt1.c.domain, stmt1.c.action)).subquery()

        stmt3 = (session.query(stmt2.c.domain,
                               func.row_to_json(as_row(stmt2)).label('parts')).
                 select_from(stmt2)).subquery()

        final = (session.query(stmt3.c.domain, cast(func.json_agg(stmt3.c.parts), Text)).
                 select_from(stmt3).
                 group_by(stmt3.c.domain))

        return final

    def _get_roles_query(self, session, identifier):
        """
        :type identifier: string
        """
        return (session.query(Role).
                join(role_membership_table, Role.id == role_membership_table.c.role_id).
                join(User, role_membership_table.c.user_id == User.id).
                filter(User.identifier == identifier))

    def _get_credential_query(self, session, identifier):
        return (session.query(CredentialType.title, Credential.credential).
                join(Credential, CredentialType.id == Credential.credential_type_id).
                join(User, Credential.user_id == User.id).
                filter(User.identifier == identifier))

    @session_context
    def get_authz_permissions(self, identifier, session=None):
        try:
            return dict(self._get_permissions_query(session, identifier).all())
        except (AttributeError, TypeError):
            return None

    @session_context
    def get_authz_roles(self, identifier, session=None):
        try:
            return [r.title for r in self._get_roles_query(session, identifier).all()]
        except (AttributeError, TypeError):
            return None
