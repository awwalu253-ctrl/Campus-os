from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField,
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, Regexp, Optional,
)


class RegisterForm(FlaskForm):
    display_name = StringField(
        "Full name",
        validators=[DataRequired(), Length(min=2, max=80)],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=255)],
    )
    phone = StringField(
        "Phone (optional)",
        validators=[
            Optional(),
            Length(max=32),
            Regexp(
                r"^\+?[0-9\s\-()]{7,20}$",
                message="Enter a valid phone number.",
            ),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    accept_terms = BooleanField(
        "I accept the Terms and Privacy Policy",
        validators=[DataRequired(message="You must accept the terms to continue.")],
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Keep me signed in")
    submit = SubmitField("Sign in")


class ForgotForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send reset link")


class ResetForm(FlaskForm):
    password = PasswordField(
        "New password",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Update password")