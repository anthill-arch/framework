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
import itertools
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import declared_attr
from anthill.framework.db import db

"""
models.py features a basic, non-hierarchical, non-constrained RBAC data model,
also known as a flat model
-- Ref:  http://csrc.nist.gov/rbac/sandhu-ferraiolo-kuhn-00.pdf
+-----------------+          +-------------------+          +---------------+
|                 |          |                   |          |               |
|                 |          |    R o l e        |          |               |
|    R o l e      +----------+    Permission     +----------+   Permission  |
|                 |          |                   |          |               |
+-----------------+          +-------------------+          +---------------+
+-----------------+          +-------------------+          +---------------+
|                 |          |                   |          |               |
|                 |          |    R o l e        |          |               |
|    U s e r      +----------+    Membership     +----------+   R o l e     |
|                 |          |                   |          |               |
+-----------------+          +-------------------+          +---------------+
"""

role_permission = db.Table(
    'role_permission', db.metadata,
    db.Column('role_id', db.ForeignKey('role.id'), primary_key=True),
    db.Column('permission_id', db.ForeignKey('permission.id'), primary_key=True)
)

role_membership = db.Table(
    'role_membership', db.metadata,
    db.Column('role_id', db.ForeignKey('role.id'), primary_key=True),
    db.Column('user_id', db.ForeignKey('user.id'), primary_key=True)
)


class UserMixin(db.Model):
    __abstract__ = True

    @declared_attr
    def roles(self):
        return db.relationship('Role', secondary=role_membership, backref='users')

    @declared_attr
    def perms(self):
        return association_proxy('roles', 'permissions')

    @property
    def permissions(self):
        return list(itertools.chain(*self.perms))


class Credential(db.Model):
    __tablename__ = 'credential'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False, unique=False)
    credential = db.Column(db.String, nullable=False)
    credential_type_id = db.Column(db.ForeignKey('credential_type.id'), nullable=False)
    expiration_dt = db.Column(db.DateTime(timezone=True), nullable=False)

    user = db.relationship('User',
                           backref='credential',
                           cascade="all, delete-orphan",
                           single_parent=True)

    def __repr__(self):
        return ("Credential(credential_type_id={0}, user_id={1})".
                format(self.credential_type_id, self.user_id))


class CredentialType(db.Model):
    __tablename__ = 'credential_type'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)

    def __repr__(self):
        return "CredentialType(title={0})".format(self.title)


class Domain(db.Model):
    __tablename__ = 'domain'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return "Domain(id={0}, name={1})".format(self.id, self.name)


class Action(db.Model):
    __tablename__ = 'action'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return "Action(id={0}, name={1})".format(self.id, self.name)


class Resource(db.Model):
    __tablename__ = 'resource'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return "Resource(id={0}, name={1})".format(self.id, self.name)


class Scope(db.Model):
    __tablename__ = 'scope'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return "Scope(id={0}, name={1})".format(self.id, self.name)


class Permission(db.Model):
    __tablename__ = 'permission'

    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.ForeignKey('domain.id'), nullable=True)
    action_id = db.Column(db.ForeignKey('action.id'), nullable=True)
    resource_id = db.Column(db.ForeignKey('resource.id'), nullable=True)

    domain = db.relationship('Domain', backref='permission')
    action = db.relationship('Action', backref='permission')
    resource = db.relationship('Resource', backref='permission')

    roles = db.relationship('Role', secondary=role_permission,
                            backref='permissions')

    users = association_proxy('roles', 'users')

    def __repr__(self):
        return ("Permission(domain_id={0},action_id={1},resource_id={2})".
                format(self.domain_id, self.action_id, self.resource_id))


class Role(db.Model):
    __tablename__ = 'role'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))

    def __repr__(self):
        return "Role(title={0})".format(self.title)
