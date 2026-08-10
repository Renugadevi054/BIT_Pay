from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
import random
import stripe
from werkzeug.security import check_password_hash
import os
# Initialize Flask App
app = Flask(__name__)
app.secret_key = "your_secret_key"

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fees_payment.db'  
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Avoids warning

# Initialize SQLAlchemy (Corrected)
db = SQLAlchemy()  
db.init_app(app)  # Bind db to Flask app

# Stripe Payment Configuration
stripe.api_key = "your_stripe_secret_key"

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Flask-Mail Configuration
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME='daminmain@gmail.com',
    MAIL_PASSWORD='kpqtxqskedcykwjz'
)
mail = Mail(app)

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    department = db.Column(db.String(100))
    dob = db.Column(db.String(20))
    location = db.Column(db.String(100))
    mobile = db.Column(db.String(15))
    email = db.Column(db.String(100), unique=True)
    image = db.Column(db.String(200))
    roll_number = db.Column(db.String(20), unique=True)
    course = db.Column(db.String(100))
    total_fees = db.Column(db.Float, default=200000, nullable=False)  # ✅ Set total fees to ₹200,000
    fees_paid = db.Column(db.Float, default=0.0, nullable=False)
    password = db.Column(db.String(200))
    otp = db.Column(db.String(10))


# Transaction Model
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(20), nullable=False)  # "credit_card", "debit_card", "upi"
    status = db.Column(db.String(20), default="Pending")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class ScheduledPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(20), nullable=False)  # credit_card, debit_card, upi
    schedule_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="Scheduled")

    user = db.relationship('User', backref=db.backref('scheduled_payments', lazy=True))


@login_manager.user_loader
def load_user(user_id):
    if user_id == 'admin':
        return AdminUser()
    return User.query.get(int(user_id))


# Routes

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):  # Secure password check
            login_user(user)
            flash("✅ Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("❌ Invalid credentials! Try again.", "danger")

    return render_template("login.html")

from werkzeug.security import generate_password_hash

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        name = request.form['name']
        department = request.form['department']
        dob = request.form['dob']
        location = request.form['location']
        mobile = request.form['mobile']
        email = request.form['email']
        password = request.form['password']  # Get password from form
        hashed_password = generate_password_hash(password)  # Hash password
        image = request.files['image']
        image_path = f"static/uploads/{image.filename}"
        image.save(image_path)
        otp = str(random.randint(100000, 999999))

        # Store user details
        new_user = User(name=name, department=department, dob=dob, location=location, 
                        mobile=mobile, email=email, password=hashed_password, image=image_path, otp=otp)
        db.session.add(new_user)
        db.session.commit()

        # Send OTP email
        msg = Message('Your OTP Code', sender='your_email@gmail.com', recipients=[email])
        msg.body = f"Your OTP is: {otp}"
        mail.send(msg)

        session['email'] = email
        flash("OTP sent! Please verify your email.", "info")
        return redirect(url_for('verify_otp'))

    return render_template("register.html")

from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

@app.route("/settings", methods=["GET", "POST"])
@login_required  # Ensures only logged-in users access settings
def settings():
    if request.method == "POST":
        current_user.name = request.form["name"]
        current_user.email = request.form["email"]
        current_user.mobile = request.form["mobile"]

        if "password" in request.form and request.form["password"]:
            hashed_password = generate_password_hash(request.form["password"])
            current_user.password = hashed_password

        db.session.commit()
        flash("✅ Profile updated successfully!", "success")
        return redirect(url_for("settings"))

    return render_template("settings.html", user=current_user)  # Pass current_user as 'user'


@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == "POST":
        email = session.get('email')
        user = User.query.filter_by(email=email).first()
        entered_otp = request.form['otp']

        if user and user.otp == entered_otp:
            flash("Email verified successfully! Please login.", "success")
            return redirect(url_for('home'))
        else:
            flash("Invalid OTP. Try again.", "danger")

    return render_template("verify_otp.html")

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(current_user.id)
    db.session.refresh(user)  # Force database refresh

    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    
    print(f"Updated fees_paid: {user.fees_paid}")  # Debugging Step

    return render_template("dashboard.html", user=user, transactions=transactions)

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from datetime import datetime
import stripe
import random
from flask_apscheduler import APScheduler
from datetime import datetime, timedelta
import pytz

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

@app.route("/payment", methods=["GET"])
@login_required
def payment_page():
    return render_template("payment.html")  # Show payment form


@app.route("/process_payment", methods=["POST"])
@login_required
def process_payment():
    amount = request.form.get("amount")
    method = request.form.get("method")  # credit_card, debit_card, or upi

    try:
        amount = float(amount)  # Ensure amount is a valid number
        if amount <= 0:
            flash("Invalid payment amount!", "danger")
            return redirect(url_for("payment_page"))
    except ValueError:
        flash("Amount must be a valid number!", "danger")
        return redirect(url_for("payment_page"))

    # Validate payment method
    if method == "upi":
        upi_id = request.form.get("upi_id")
        if not upi_id:
            flash("Please enter a valid UPI ID.", "danger")
            return redirect(url_for("payment_page"))

    elif method in ["credit_card", "debit_card"]:
        card_number = request.form.get("card_number")
        expiry_date = request.form.get("expiry_date")
        cvv = request.form.get("cvv")

        if not (card_number and expiry_date and cvv):
            flash("Please enter valid card details.", "danger")
            return redirect(url_for("payment_page"))

   
    user = db.session.get(User, current_user.id)  

    if not user:
        flash("User not found!", "danger")
        return redirect(url_for("dashboard"))

    if user.total_fees - amount < 0:
        flash("⚠️ Payment exceeds remaining fees!", "danger")
        return redirect(url_for("payment_page"))

    print(f"Before Payment: fees_paid = {user.fees_paid}, remaining fees = {user.total_fees}")  # Debugging Step

    user.fees_paid += amount  # ✅ Increase paid amount
    user.total_fees -= amount  # ✅ Reduce total fees

    db.session.commit()

    print(f"After Payment: fees_paid = {user.fees_paid}, remaining fees = {user.total_fees}")  # Debugging Step

    # Store transaction
    new_transaction = Transaction(user_id=current_user.id, amount=amount, method=method, status="Completed")
    db.session.add(new_transaction)
    db.session.commit()

    flash("✅ Payment Successful! Remaining Fees Updated.", "success")
    return redirect(url_for("dashboard"))

@app.route('/transactions')
@login_required
def transactions():
    user_transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.timestamp.desc()).all()
    return render_template('transactions.html', transactions=user_transactions)

class AdminUser:
    def __init__(self):
        self.email = 'admin@bit.edu'
        self.is_authenticated = True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return 'admin'

@app.route('/payment_graph')
@login_required
def payment_graph():
    transactions = db.session.query(User.name, db.func.sum(Transaction.amount))\
        .join(Transaction, User.id == Transaction.user_id)\
        .group_by(User.name).all()

    user_names = [row[0] for row in transactions]
    amounts = [row[1] for row in transactions]

    return render_template('payment_graph.html', user_names=user_names, amounts=amounts)
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == 'admin' and password == 'admin123':
            login_user(AdminUser())
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials', 'danger')
    return render_template('admin_login.html')


@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.get_id() != 'admin' and current_user.email != "admin@bit.edu":
        flash("Access Denied!", "danger")
        return redirect(url_for('dashboard'))

    students = User.query.all()
    transactions = Transaction.query.all()
    return render_template("admin.html", students=students, transactions=transactions)


@app.route("/schedule_payment", methods=["GET", "POST"])
@login_required
def schedule_payment():
    if request.method == "GET":
        return render_template("schedule_payment.html")  # Show the scheduling page

    # Handle POST request (form submission)
    amount = request.form.get("amount")
    method = request.form.get("method")
    schedule_time_str = request.form.get("schedule_time")
    user_email = current_user.email

    try:
        amount = float(amount)
        if amount <= 0:
            flash("Invalid amount!", "danger")
            return redirect(url_for("schedule_payment"))

        schedule_time = datetime.strptime(schedule_time_str, "%Y-%m-%d %H:%M")
        schedule_time = pytz.timezone("Asia/Kolkata").localize(schedule_time)

    except ValueError:
        flash("Invalid schedule time!", "danger")
        return redirect(url_for("schedule_payment"))

    new_schedule = ScheduledPayment(user_id=current_user.id, amount=amount, method=method, schedule_time=schedule_time)
    db.session.add(new_schedule)
    db.session.commit()

    scheduler.add_job(
        func=send_scheduled_payment_email,
        trigger="date",
        run_date=schedule_time,
        args=[current_user.id, amount, method],
        id=f"payment_{current_user.id}_{schedule_time}"
    )

    flash("✅ Payment Scheduled! You will receive a reminder email.", "success")
    return redirect(url_for("dashboard"))


def send_scheduled_payment_email(user_id, amount, method):
    user = User.query.get(user_id)
    if not user:
        return

    msg = Message("Payment Reminder", sender="your_email@gmail.com", recipients=[user.email])
    msg.body = f"Hello {user.name},\n\nYour scheduled payment of ₹{amount} via {method} is due.\n\nPlease complete the payment soon.\n\nThank you!"
    
    try:
        mail.send(msg)
        print(f"✅ Payment Reminder Email Sent to {user.email}")
    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully!", "info")
    return redirect(url_for('home'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
