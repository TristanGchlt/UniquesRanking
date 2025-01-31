from flask_wtf import FlaskForm
from flask_babel import _
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, EqualTo

# Babel a l'air de ne prendre que l'anglais et ne pas se mettre a jour avec get_locale()

class RegistrationForm(FlaskForm):
    username_label = _('username')
    password_label = _('password')
    password2_label = _('repeatpassword')
    submit_label = _('register')

    username = StringField(username_label, validators=[DataRequired()])
    password = PasswordField(password_label, validators=[DataRequired()])
    password2 = PasswordField(password2_label, validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField(submit_label)

class LoginForm(FlaskForm):
    username_label = _('username')
    password_label = _('password')
    login_label = _('login')
    remember_me_label = _('rememberme')

    username = StringField(username_label, validators=[DataRequired()])
    password = PasswordField(password_label, validators=[DataRequired()])
    remember_me = BooleanField(remember_me_label)
    submit = SubmitField(login_label)