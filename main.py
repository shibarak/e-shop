from flask import Flask, render_template, url_for, redirect, flash, request, session, Markup, abort
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import relationship
import shortuuid
from flask_ckeditor import CKEditor
from flask_bootstrap import Bootstrap
from flask_login import UserMixin, login_user, logout_user, login_required, current_user, LoginManager
from werkzeug.utils import secure_filename
import logger
from forms import UserForm, LoginForm, ProductForm
import datetime
import os
import config
import stripe
import time
import random

stripe.api_key = config.STRIPE_API_KEY

# -------------- Set up Flask app ----------------------- #

app = Flask(__name__)
if not config.SECRET_KEY:
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
else:
    app.config['SECRET_KEY'] = config.SECRET_KEY

Bootstrap(app)
csrf = CSRFProtect(app)
ckeditor = CKEditor(app)
# ------------- Set up SQL Database ------------------------ #
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///eshop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)



## configure tables

class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    url_key = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    description = db.Column(db.Text, nullable=False)
    featured = db.Column(db.Boolean, nullable=True)
    price = db.Column(db.Integer, nullable=False)
    sale_price = db.Column(db.Integer, nullable=True)
    stock = db.Column(db.Integer, nullable=False)
    stripe_price_id = db.Column(db.String(250), nullable=False)


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(250), nullable=False)
    last_name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), nullable=False, unique=True)
    password = db.Column(db.String(250), nullable=False)
    stripe_user_id = db.Column(db.String(250))

    __hash__ = object.__hash__

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        try:
            return str(self.id)
        except AttributeError:
            raise NotImplementedError('No `id` attribute - override `get_id`')

    def __eq__(self, other):
        '''
        Checks the equality of two `UserMixin` objects using `get_id`.
        '''
        if isinstance(other, UserMixin):
            return self.get_id() == other.get_id()
        return NotImplemented

    def __ne__(self, other):
        '''
        Checks the inequality of two `UserMixin` objects using `get_id`.
        '''
        equal = self.__eq__(other)
        if equal is NotImplemented:
            return NotImplemented
        return not equal


db.create_all()


#  Makes the "current_year" variable available in every template#
@app.context_processor
def inject_now():
    return {'current_year': datetime.date.today().strftime("%Y"),
            'current_date': datetime.date.today().strftime("%Y-%m-%d")}


# loads the current_user
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route("/")
def home():
    if 'cart' not in session:
        session['cart'] = []
        session['cartitems'] = 0
    featured_list = Product.query.filter_by(featured=True)

    return render_template("index.html", featured_list=featured_list)


@app.route("/product/<url_key>", methods=["GET", "POST"])
@csrf.exempt
def load_product(url_key):
    add = False
    if request.method == "POST":
        add = True
        data = request.form
        incart = False
        for item in session['cart']:
            if item["url_key"] == url_key:
                session["cartitems"] -= item['amount']
                item['amount'] = int(data[url_key])
                session["cartitems"] += item['amount']
                incart = True
        if not incart:
            product = {"url_key": url_key, "amount": int(data[url_key])}
            session['cart'].append(product)
            session['cartitems'] += int(data[url_key])
    product = Product.query.filter_by(url_key=url_key).first()
    image_list = os.listdir(os.path.join(app.static_folder, "images", product.url_key))
    return render_template("product.html", product=product, image_list=image_list, add=add)


@app.route("/register", methods=['GET', 'POST'])
def create_account():
    form = UserForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        if User.query.filter_by(email=email).first():
            flash("An account is already registered with this email address.")
            return render_template("register.html", form=form)
        first_name = form.first_name.data
        last_name = form.last_name.data
        password = generate_password_hash(password=form.password.data,
                                          method="pbkdf2:sha256",
                                          salt_length=8)
        user = User(first_name=first_name,
                    last_name=last_name,
                    email=email,
                    password=password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("home"))

    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        password = form.password.data
        user = User.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('home'))
            else:
                flash("Password incorrect. Please check password and try again")
                return render_template("login.html", form=form)
        else:
            flash("Email not found.")
            return render_template("login.html", form=form)
    return render_template("login.html", form=form)




@app.route("/logout")
def logout():
    logout_user()
    session.pop(key="cart")
    session.pop(key="cartitems")
    return redirect(url_for("home"))


@app.route("/add_cart_quick/<url_key>")
def add_to_cart(url_key):
    if session["cart"]:
        for product in session["cart"]:
            if product["url_key"] == url_key:
                product["amount"] += 1
                session["cartitems"] += 1
                return redirect(url_for('home'))
        product = {"url_key": url_key, "amount": 1}
        session['cart'].append(product)
        session["cartitems"] += 1

    else:
        session['cart'] = [{"url_key": url_key, "amount": 1}]
        session["cartitems"] = 1
    return redirect(url_for('home'))


@app.route("/cart", methods=["GET", "POST"])
@csrf.exempt
def load_cart():
    if 'cartitems' not in session:
        return render_template("cart.html")
    cart_list = []
    if request.method == "POST":
        session['cartitems'] = 0
        data = request.form
        for item in session["cart"]:
            item['amount'] = int(data[item['url_key']])
            session["cartitems"] += int(data[item['url_key']])
            print(session["cartitems"])
        print(session['cart'])

    cart_list = []
    for item in session['cart']:
        product = Product.query.filter_by(url_key=item['url_key']).first()
        cart_list.append(product)
    session['subtotal'] = 0
    for product in cart_list:
        for item in session['cart']:
            if product.url_key == item["url_key"]:
                if product.sale_price:
                    session['subtotal'] += (product.sale_price * item["amount"])
                else:
                    session['subtotal'] += (product.price * item["amount"])

    return render_template("cart.html", cart=cart_list)


@app.route("/checkout-session", methods=["POST", "GET"])
@csrf.exempt
def checkout_session():
    line_items = []
    success = url_for('success')
    print(success)
    cancel = url_for('load_cart')
    print(cancel)
    for item in session['cart']:
        product = Product.query.filter_by(url_key=item['url_key']).first()
        stripe_product = {'price': product.stripe_price_id, 'quantity': item["amount"]}
        line_items.append(stripe_product)
    stripe_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        shipping_rates=['shr_1Jhox4JKegpJsiDVwC7tjTVi'],
        shipping_address_collection={
            'allowed_countries': ['JP', 'US'],
        },
        line_items=line_items,
        mode='payment',
        success_url="http://192.168.1.135:5000/success",
        cancel_url="http://192.168.1.135:5000/cart",
    )
    stripe_url = stripe_session.to_dict()['url']
    return redirect(stripe_session.url)

@app.route('/success', methods=["GET"])
def success():
    session.pop(key="cart")
    session.pop(key="cartitems")
    return render_template("success.html")



@app.route("/addproduct", methods=["GET", "POST"])
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        url_key = shortuuid.ShortUUID().random(length=10)
        os.mkdir(path=f"static/images/{url_key}")
        for index in range(len(form.images.data)):
            file = form.images.data[index]
            file.save(os.path.join(f"static/images/{url_key}", f"img-{index}.JPG"))
        name = form.name.data
        description = form.description.data
        featured = form.featured_item.data
        price = form.price.data
        inventory = form.inventory.data
        stripe_id = form.stripe_id.data
        if form.sale_price:
            sale_price = form.sale_price.data
        else:
            sale_price = None
        product = Product(name=name,
                          url_key=url_key,
                          stock=inventory,
                          description=description,
                          price=price,
                          sale_price=sale_price,
                          stripe_price_id=stripe_id,
                          featured=featured
                          )
        db.session.add(product)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("newproduct.html", form=form)


@app.route("/editproduct/<url_key>", methods=["GET", "POST"])
def edit_product(url_key):
    product = Product.query.filter_by(url_key=url_key).first()
    edit_form = ProductForm(name=product.name,
                            description=product.description,
                            featured_item=product.featured,
                            price=product.price,
                            sale_price=product.sale_price,
                            inventory=product.stock,
                            stripe_id=product.stripe_price_id,
                            )
    if edit_form.validate_on_submit():
        product.name = edit_form.name.data
        product.url_key = product.url_key
        product.description = edit_form.description.data
        product.featured = edit_form.featured_item.data
        product.price = edit_form.price.data
        product.sale_price = edit_form.sale_price.data
        product.stock = edit_form.inventory.data
        product.stripe_price_id = edit_form.stripe_id.data
        db.session.commit()
        start = len(os.listdir(os.path.join(app.static_folder, "images", product.url_key)))
        for index in range(len(edit_form.images.data)):
            file = edit_form.images.data[index]
            if file.filename != "":
                file.save(os.path.join(f"static/images/{url_key}", f"img-{index + start}.JPG"))
        return redirect(url_for("load_product", url_key=product.url_key))
    return render_template("newproduct.html", form=edit_form, url_key=product.url_key)


@app.route('/clearsession', methods=["GET"])
def clear_session():
    session.pop(key="cart")
    session.pop(key="cartitems")
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(host="0.0.0.0",
            port=5000,
            debug=True)
    # ssl_context="adhoc")
