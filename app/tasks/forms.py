"""WTForms for the Tasks feature."""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DateField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from app.tasks.models import TASK_PRIORITIES


class TaskForm(FlaskForm):
    title = StringField(
        "Title",
        validators=[
            DataRequired(message="Title is required."),
            Length(max=160, message="Title must be 160 characters or fewer."),
        ],
    )
    description = TextAreaField(
        "Description",
        validators=[
            Optional(),
            Length(max=1000, message="Description must be 1000 characters or fewer."),
        ],
    )
    due_at = DateField(
        "Due date",
        validators=[Optional()],
        format="%Y-%m-%d",
    )
    priority = SelectField(
        "Priority",
        choices=[(p, p.capitalize()) for p in TASK_PRIORITIES],
        default="medium",
        validators=[DataRequired()],
    )
    submit = SubmitField("Save")