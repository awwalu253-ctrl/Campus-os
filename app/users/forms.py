from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp


class ProfileForm(FlaskForm):
    display_name = StringField("Full name", validators=[DataRequired(), Length(2, 80)])
    phone = StringField("Phone", validators=[
        Length(max=32),
        Regexp(r"^$|^\+?[0-9\s\-()]{7,20}$", message="Enter a valid phone number."),
    ])
    submit = SubmitField("Save")