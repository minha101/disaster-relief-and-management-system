import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError

PW_RE = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,128}$')


def strong(form, field):
    if not PW_RE.match(field.data or ''):
        raise ValidationError('Use 8+ characters with upper-case, lower-case and a digit.')


class LoginForm(FlaskForm):
    email = StringField('E-mail', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired(), Length(max=128)])
    remember = BooleanField('Keep me signed in')


class SetupForm(FlaskForm):
    full_name = StringField('Full name', validators=[DataRequired(), Length(max=120)])
    email = StringField('E-mail', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired(), strong])
    confirm = PasswordField('Confirm password', validators=[DataRequired(), EqualTo('password', 'Passwords do not match.')])


class RegisterForm(SetupForm):
    phone = StringField('Phone', validators=[DataRequired(), Length(min=7, max=20)])
    role_code = SelectField('I am registering as', choices=[('affected', 'Affected person / family'),
                                                            ('volunteer', 'Volunteer'), ('donor', 'Donor')])


class ChangePasswordForm(FlaskForm):
    current = PasswordField('Current password', validators=[DataRequired()])
    password = PasswordField('New password', validators=[DataRequired(), strong])
    confirm = PasswordField('Confirm new password', validators=[DataRequired(), EqualTo('password', 'Passwords do not match.')])
