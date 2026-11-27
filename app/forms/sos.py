import re
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, BooleanField, SelectField, TextAreaField, FloatField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError


def phone_ok(form, field):
    if not re.match(r'^[0-9+\-\s()]{7,20}$', field.data or ''):
        raise ValidationError('Enter a valid phone number (digits, +, -, spaces).')


class SOSForm(FlaskForm):
    requester_name = StringField('Your name', validators=[DataRequired(), Length(max=120)])
    phone = StringField('Phone number', validators=[DataRequired(), phone_ok])
    people_count = IntegerField('People needing help', default=1, validators=[DataRequired(), NumberRange(1, 5000)])
    category_id = SelectField('Type of help needed', coerce=int, validators=[Optional()])
    district_id = SelectField('District', coerce=int, validators=[Optional()])
    address = StringField('Nearest landmark / village', validators=[Optional(), Length(max=255)])
    latitude = FloatField('Latitude', validators=[Optional(), NumberRange(23.0, 38.0, 'Outside Pakistan region')])
    longitude = FloatField('Longitude', validators=[Optional(), NumberRange(60.0, 78.0, 'Outside Pakistan region')])
    has_injured = BooleanField('Someone is injured')
    needs_medical = BooleanField('Medical help needed')
    description = TextAreaField('Describe the situation', validators=[Optional(), Length(max=2000)])
    website = StringField('Leave empty')     # honeypot
