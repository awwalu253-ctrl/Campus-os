"""WTForms for the Campus Events feature."""

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    DateTimeLocalField,
    IntegerField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    Optional,
    NumberRange,
)

from app.events.categories import EVENT_CATEGORIES


class EventForm(FlaskForm):
    title = StringField(
        "Event title",
        validators=[
            DataRequired(message="Event title is required."),
            Length(max=160),
        ],
    )

    description = TextAreaField(
        "Description",
        validators=[
            DataRequired(message="Description is required."),
            Length(max=3000),
        ],
    )

    category = SelectField(
        "Category",
        choices=[
            (key, label)
            for key, label in EVENT_CATEGORIES.items()
        ],
        validators=[DataRequired(message="Choose an event category.")],
    )

    venue = StringField(
        "Venue",
        validators=[
            DataRequired(message="Venue is required."),
            Length(max=180),
        ],
    )

    starts_at = DateTimeLocalField(
        "Start date and time",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Start date and time are required.")],
    )

    ends_at = DateTimeLocalField(
        "End date and time",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="End date and time are required.")],
    )

    capacity = IntegerField(
        "Capacity",
        validators=[
            Optional(),
            NumberRange(
                min=1,
                message="Capacity must be at least 1.",
            ),
        ],
    )

    submit = SubmitField("Save event")