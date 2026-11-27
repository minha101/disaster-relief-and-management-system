from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .base import *


class Role(Base):
    __tablename__ = 'roles'
    code = Str(40, unique=True, nullable=False)
    name = Str(80, nullable=False)
    description = Str(255)
    is_system = Bool(False)


class Permission(Base):
    __tablename__ = 'permissions'
    __label__ = '{code}'
    code = Str(80, unique=True, nullable=False)
    module = Str(60, index=True)
    action = Str(20)
    description = Str(255)


class RolePermission(Base):
    __tablename__ = 'role_permissions'
    __label__ = 'role {role_id} / permission {permission_id}'
    __table_args__ = (db.UniqueConstraint('role_id', 'permission_id'),)
    role_id = FK('roles', False)
    permission_id = FK('permissions', False)
    role = db.relationship('Role', backref=db.backref('role_permissions', cascade='all, delete-orphan'))
    permission = db.relationship('Permission', backref=db.backref('role_permissions', cascade='all, delete-orphan'))


class User(UserMixin, Base):
    __tablename__ = 'users'
    __label__ = '{full_name}'
    __hidden__ = ('failed_logins', 'locked_until', 'last_login')
    email = Str(150, unique=True, nullable=False)
    full_name = Str(120, nullable=False)
    phone = Str(30)
    password_hash = Str(255, nullable=False)
    organization_id = FK('organizations')
    district_id = FK('districts')
    active = Bool(True)
    failed_logins = Int(default=0, nullable=False)
    locked_until = Dt()
    last_login = Dt()
    user_roles = db.relationship('UserRole', foreign_keys='UserRole.user_id', backref='user',
                                 cascade='all, delete-orphan', lazy='selectin')

    @property
    def is_active(self):
        return self.active

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def role_codes(self):
        return [ur.role.code for ur in self.user_roles if ur.role]

    @property
    def role_names(self):
        return ', '.join(ur.role.name for ur in self.user_roles if ur.role)

    def has_role(self, *codes):
        return any(c in codes for c in self.role_codes)

    @property
    def perms(self):
        if not hasattr(self, '_perms'):
            rows = (db.session.query(Permission.code)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .join(UserRole, UserRole.role_id == RolePermission.role_id)
                    .filter(UserRole.user_id == self.id).all())
            self._perms = {r[0] for r in rows}
        return self._perms

    def can(self, slug, action='view'):
        return f'{slug}.{action}' in self.perms


class UserRole(Base):
    __tablename__ = 'user_roles'
    __label__ = 'user {user_id} / role {role_id}'
    __table_args__ = (db.UniqueConstraint('user_id', 'role_id'),)
    user_id = FK('users', False)
    role_id = FK('roles', False)
    assigned_by_id = FK('users')
    role = db.relationship('Role', backref='user_roles')


class Organization(Tracked):
    __tablename__ = 'organizations'
    name = Str(160, nullable=False)
    org_type = Ch(['ngo', 'government', 'international_ngo', 'private', 'community'], index=True)
    registration_no = Str(60)
    email = Str(150)
    phone = Str(30)
    website = Str(200)
    address = Str(255)
    district_id = FK('districts')
    is_verified = Bool(False)


class Department(Base):
    __tablename__ = 'departments'
    organization_id = FK('organizations', False)
    name = Str(120, nullable=False)
    head_name = Str(120)
    description = Str(255)


class OrganizationMember(Base):
    __tablename__ = 'organization_members'
    __label__ = 'org {organization_id} / user {user_id}'
    __table_args__ = (db.UniqueConstraint('organization_id', 'user_id'),)
    organization_id = FK('organizations', False)
    user_id = FK('users', False)
    department_id = FK('departments')
    position = Str(100)
    joined_on = Dat()
