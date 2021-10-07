from wtforms import StringField, SubmitField, SelectField, PasswordField, IntegerField, MultipleFileField, BooleanField
from flask_wtf import FlaskForm

from wtforms.validators import *
from flask_ckeditor import CKEditorField
import email_validator

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class UserForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired()], render_kw={"class": "form-control"})
    last_name = StringField("Last name", validators=[DataRequired()], render_kw={"class": "form-control"})
    email = StringField("Email address", validators=[DataRequired(), Email()], render_kw={"class": "form-control"})
    password = PasswordField("Choose a password",
                             validators=[DataRequired(),
                                         EqualTo('confirm', message="Passwords must match."),
                                         Length(min=8)],
                                         render_kw={"class": "form-control"})
    confirm = PasswordField("Confirm password", validators=[DataRequired()], render_kw={"class": "form-control"})
    submit = SubmitField('Register')


class ProductForm(FlaskForm):
    name = StringField("Product Name", validators=[DataRequired()])
    description = CKEditorField("Description", validators=[DataRequired()])
    featured_item = BooleanField("Featured item")
    price = IntegerField("Price", validators=[DataRequired()])
    sale_price = IntegerField("Sale Price", validators=[Optional()])
    inventory = IntegerField("Current Inventory", validators=[DataRequired()])
    stripe_id = StringField("Stripe ID", validators=[DataRequired()])
    images = MultipleFileField("Upload Images", validators=[DataRequired()])
    submit = SubmitField("Submit")
