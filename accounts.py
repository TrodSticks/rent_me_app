"""Accounts: sign-up, sign-in, email verification and password recovery."""
import re
from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from app import db
from mailer import external_url, mail_enabled, read_outbox, send_email
from models import Property, User, utcnow
from routes import bp, get_conversations, is_safe_redirect
from security import (clear_hits, client_ip, is_limited, make_reset_token, make_verify_token,
                      password_error, read_reset_token, read_verify_token, record_hit)

MAX_USERNAME_LENGTH = 20
EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
ROLES = ('Renter', 'Landlord')   # the only roles a person can choose; admin is never one of them

RESET_SENT = ("If an account exists for that address, we've sent it a link to choose a new password. "
              "The link works for 1 hour.")


def find_user_by_email(email):
    return User.query.filter(func.lower(User.email) == email.lower()).first()


# ---------- Emails ----------

def send_verification_email(user):
    link = external_url('main.verify_email', token=make_verify_token(user))
    return send_email(user.email, "Confirm your email address for Rent Me", (
        f"Hi {user.username},\n\n"
        "Please confirm that this is your email address by opening this link:\n\n"
        f"{link}\n\n"
        "The link works for 24 hours. Until you confirm, you can browse and manage your account, "
        "but you can't publish listings or start new conversations.\n\n"
        "If you didn't create a Rent Me account, you can ignore this email.\n"
    ))


def send_reset_email(user):
    link = external_url('main.reset_password', token=make_reset_token(user))
    return send_email(user.email, "Choose a new Rent Me password", (
        f"Hi {user.username},\n\n"
        "Someone asked to reset the password for this Rent Me account. To choose a new password, open:\n\n"
        f"{link}\n\n"
        "The link works for 1 hour and can be used once.\n\n"
        "If this wasn't you, ignore this email and your password will stay the same.\n"
    ))


def _verification_sent_message(user, sent):
    if sent:
        return f"We've sent a link to {user.email}. Open it to confirm your email address.", "success"
    return ("Email isn't set up on this server yet, so we couldn't send a confirmation link. "
            "Please try again later."), "warning"


# ---------- Sign-up and sign-in ----------

@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role")

        error = None
        if not username or len(username) > MAX_USERNAME_LENGTH:
            error = f"Please choose a username of 1 to {MAX_USERNAME_LENGTH} characters."
        elif not EMAIL_PATTERN.match(email) or len(email) > 120:
            error = "Please enter a valid email address."
        elif password_error(password):
            error = password_error(password)
        elif role not in ROLES:
            error = "Please choose whether you are a renter or a landlord."
        elif find_user_by_email(email):
            error = "Email already registered. Please choose a different one."
        elif User.query.filter_by(username=username).first():
            error = "Username already taken. Please choose a different one."
        if error:
            flash(error, "danger")
            return render_template("register.html", title="Register", form=request.form)

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Your account has been created! You are now able to log in", "success")
        flash(*_verification_sent_message(user, send_verification_email(user)))
        return redirect(url_for("main.login"))
    return render_template("register.html", title="Register", form={})

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if is_limited('login_email', email) or is_limited('login_ip', client_ip()):
            flash("Too many login attempts. Please wait a few minutes and try again.", "danger")
            return render_template("login.html", title="Login"), 429

        user = find_user_by_email(email)
        if user and user.check_password(password):
            clear_hits('login_email', email)
            db.session.commit()
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page if is_safe_redirect(next_page) else url_for("main.home"))
        record_hit('login_email', email)
        record_hit('login_ip', client_ip())
        db.session.commit()
        flash("Login Unsuccessful. Please check email and password", "danger")
    return render_template("login.html", title="Login")

@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.home"))


# ---------- Account ----------

@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        if not username or not email:
            flash("Username and email can't be empty.", "danger")
        elif len(username) > MAX_USERNAME_LENGTH:
            flash("Username must be 20 characters or fewer.", "danger")
        elif not EMAIL_PATTERN.match(email) or len(email) > 120:
            flash("Please enter a valid email address.", "danger")
        elif User.query.filter(User.username == username, User.id != current_user.id).first():
            flash("That username is already taken.", "danger")
        elif User.query.filter(func.lower(User.email) == email, User.id != current_user.id).first():
            flash("That email is already registered to another account.", "danger")
        else:
            email_changed = email != current_user.email
            current_user.username = username
            current_user.email = email
            if email_changed:
                # A new address has to be confirmed again
                current_user.email_verified_at = None
            db.session.commit()
            flash("Your profile has been updated.", "success")
            if email_changed:
                flash(*_verification_sent_message(current_user, send_verification_email(current_user)))
        return redirect(url_for("main.account"))

    conversations = get_conversations(current_user)
    if current_user.role == "Landlord":
        stats = {'properties': Property.query.filter_by(landlord_id=current_user.id).count()}
    else:
        stats = {'favorites': current_user.favorites.count()}
    stats['conversations'] = len(conversations)
    return render_template("account.html", title="My Account", stats=stats,
                           conversations=conversations[:5], mail_enabled=mail_enabled())

@bp.route("/account/password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    if not current_user.check_password(current_password):
        flash("Your current password is incorrect.", "danger")
    elif password_error(new_password):
        flash(password_error(new_password), "danger")
    elif new_password != confirm_password:
        flash("The new passwords don't match.", "danger")
    else:
        user = current_user._get_current_object()
        user.set_password(new_password)
        db.session.commit()
        # Changing the password signs out every session; sign this one back in
        login_user(user)
        flash("Your password has been changed.", "success")
    return redirect(url_for("main.account"))


# ---------- Email verification ----------

@bp.route("/verify-email/<token>")
def verify_email(token):
    user = read_verify_token(token)
    after = url_for("main.account") if current_user.is_authenticated else url_for("main.login")
    if user is None:
        flash("That confirmation link is invalid or has expired. You can send a new one from your account page.",
              "danger")
        return redirect(after)
    if not user.email_verified:
        user.email_verified_at = utcnow()
        db.session.commit()
    flash("Your email address is confirmed. You can now publish listings and start conversations.", "success")
    return redirect(after)

@bp.route("/verify-email/resend", methods=["POST"])
@login_required
def resend_verification():
    if current_user.email_verified:
        flash("Your email address is already confirmed.", "info")
    elif is_limited('verify_resend', current_user.id):
        flash("We've sent several confirmation emails recently. Please check your inbox, or try again in an hour.",
              "warning")
    else:
        record_hit('verify_resend', current_user.id)
        db.session.commit()
        flash(*_verification_sent_message(current_user, send_verification_email(current_user)))
    return redirect(request.referrer if is_safe_redirect(request.referrer) else url_for("main.account"))


# ---------- Password recovery ----------

@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        limited = is_limited('reset_email', email) or is_limited('reset_ip', client_ip())
        if not limited:
            record_hit('reset_email', email)
            record_hit('reset_ip', client_ip())
            db.session.commit()
            user = find_user_by_email(email) if EMAIL_PATTERN.match(email) else None
            if user:
                send_reset_email(user)
        # The same answer whether or not the address has an account, and whether or not a limit was hit
        flash(RESET_SENT, "info")
        return redirect(url_for("main.login"))
    return render_template("forgot_password.html", title="Forgot password", mail_enabled=mail_enabled())

@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = read_reset_token(token)
    if user is None:
        flash("That reset link is invalid, has expired or has already been used. You can ask for a new one.",
              "danger")
        return redirect(url_for("main.forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        if password_error(new_password):
            flash(password_error(new_password), "danger")
        elif new_password != request.form.get("confirm_password", ""):
            flash("The passwords don't match.", "danger")
        else:
            # A new password changes the fingerprint in the link, so the link can't be used again
            user.set_password(new_password)
            if not user.email_verified:
                # Opening a link sent to this address shows the address is theirs
                user.email_verified_at = utcnow()
            clear_hits('login_email', user.email)
            db.session.commit()
            logout_user()
            flash("Your password has been changed. You can now log in with it.", "success")
            return redirect(url_for("main.login"))
    return render_template("reset_password.html", title="Choose a new password", token=token)


# ---------- Development mailbox ----------

@bp.route("/dev/mailbox")
def dev_mailbox():
    """Emails "sent" while developing. Never available on a live site, and only from this computer."""
    config = current_app.config
    local = request.remote_addr in ('127.0.0.1', '::1')
    if config['MAIL_BACKEND'] != 'file' or not config['IS_DEVELOPMENT'] or not local:
        abort(404)
    emails = read_outbox()
    for email in emails:
        match = re.search(r'https?://\S+', email['body'])
        email['link'] = match.group(0) if match else None
    return render_template("dev_mailbox.html", title="Development mailbox", emails=emails)
