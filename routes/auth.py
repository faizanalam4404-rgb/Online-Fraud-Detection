"""
FraudGuard – Authentication & Authorization Controller
======================================================
Handles secure customer & administrator registration, authentication,
session management, role-based access control, and security audit logging.
"""

from functools import wraps
from datetime import datetime, timezone
from flask import (
    Blueprint, render_template, redirect, url_for,
    request, flash, jsonify, current_app
)
from flask_login import login_user, logout_user, login_required, current_user
from database.models import db, User, AuditLog
from services.currency_service import CurrencyService

auth_bp = Blueprint("auth", __name__)

def admin_required(f):
    """Decorator requiring authenticated user to have the 'admin' role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or "/api/" in request.path:
                return jsonify({"status": "error", "message": "Authentication required"}), 401
            flash("Please log in to access this resource.", "warning")
            return redirect(url_for("auth.login_view", next=request.url))
        
        if not current_user.is_admin():
            if request.is_json or "/api/" in request.path:
                return jsonify({"status": "error", "message": "Administrator privileges required"}), 403
            flash("Access denied: You do not have administrator permissions.", "danger")
            return redirect(url_for("customer.dashboard_view"))
        
        return f(*args, **kwargs)
    return decorated_function

# =============================================================================
# WEB VIEW ROUTES
# =============================================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login_view():
    """Customer and administrator login page."""
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for("admin.dashboard_view"))
        return redirect(url_for("customer.dashboard_view"))

    if request.method == "POST":
        identifier = (request.form.get("identifier") or request.form.get("username") or "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember") or request.form.get("remember_me"))

        if not identifier or not password:
            flash("Please enter both username/email and password.", "danger")
            return render_template("login.html")

        # Find by username or email
        user = User.query.filter(
            (User.email.ilike(identifier)) | (User.username.ilike(identifier))
        ).first()

        if not user or not user.check_password(password):
            flash("Invalid credentials. Please verify your login details.", "danger")
            return render_template("login.html")

        if user.account_status != "active":
            flash("Your account has been deactivated. Please contact support.", "danger")
            return render_template("login.html")

        login_user(user, remember=remember)

        # Audit log
        ip = request.remote_addr
        audit = AuditLog(
            user_id=user.id,
            action="USER_LOGIN",
            resource_type="auth",
            resource_id=str(user.id),
            details=f"User {user.username} successfully logged in ({user.role})",
            ip_address=ip
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Welcome back, {user.full_name}!", "success")
        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)

        if user.is_admin():
            return redirect(url_for("admin.dashboard_view"))
        return redirect(url_for("customer.dashboard_view"))

    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register_view():
    """Customer self-registration page."""
    if current_user.is_authenticated:
        return redirect(url_for("customer.dashboard_view"))

    currencies = CurrencyService.get_supported_currencies()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        country = request.form.get("country", "United States").strip()
        preferred_currency = request.form.get("preferred_currency", "USD").strip().upper()

        # Validations
        if not all([full_name, username, email, password, confirm_password]):
            flash("All registration fields are required.", "danger")
            return render_template("register.html", currencies=currencies)

        if len(username) < 3:
            flash("Username must be at least 3 characters long.", "danger")
            return render_template("register.html", currencies=currencies)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("register.html", currencies=currencies)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", currencies=currencies)

        if User.query.filter_by(username=username).first():
            flash("This username is already taken. Please choose another.", "danger")
            return render_template("register.html", currencies=currencies)

        if User.query.filter_by(email=email).first():
            flash("An account with this email address already exists.", "danger")
            return render_template("register.html", currencies=currencies)

        if not CurrencyService.is_valid_currency(preferred_currency):
            preferred_currency = "USD"

        # Create new customer
        new_user = User(
            full_name=full_name,
            username=username,
            email=email,
            country=country,
            preferred_currency=preferred_currency,
            role="customer",
            account_status="active"
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        # Audit log
        audit = AuditLog(
            user_id=new_user.id,
            action="USER_REGISTERED",
            resource_type="user",
            resource_id=str(new_user.id),
            details=f"Customer registered: {username} ({email}) from {country}",
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()

        # Automatically log in the user
        login_user(new_user)
        flash("Registration successful! Welcome to FraudGuard.", "success")
        return redirect(url_for("customer.dashboard_view"))

    return render_template("register.html", currencies=currencies)


@auth_bp.route("/logout")
@login_required
def logout_view():
    """Logs out authenticated session."""
    user_id = current_user.id
    username = current_user.username
    logout_user()

    # Audit log
    audit = AuditLog(
        user_id=user_id,
        action="USER_LOGOUT",
        resource_type="auth",
        resource_id=str(user_id),
        details=f"User {username} logged out",
        ip_address=request.remote_addr
    )
    db.session.add(audit)
    db.session.commit()

    flash("You have been securely logged out.", "info")
    return redirect(url_for("api.landing_page"))

# =============================================================================
# REST API ENDPOINTS
# =============================================================================

@auth_bp.route("/api/auth/register", methods=["POST"])
@auth_bp.route("/auth/api/register", methods=["POST"])
@auth_bp.route("/api/register", methods=["POST"])
def api_register():
    payload = request.get_json(force=True, silent=True) or {}
    full_name = payload.get("full_name", "").strip()
    username = payload.get("username", "").strip()
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")
    country = payload.get("country", "United States").strip()
    preferred_currency = payload.get("preferred_currency", "USD").strip().upper()

    if not all([full_name, username, email, password]):
        return jsonify({"status": "error", "message": "Missing required fields"}), 422

    if len(password) < 6:
        return jsonify({"status": "error", "message": "Password must be at least 6 characters"}), 422

    if User.query.filter_by(username=username).first():
        return jsonify({"status": "error", "message": "Username already taken"}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({"status": "error", "message": "Email already registered"}), 409

    new_user = User(
        full_name=full_name,
        username=username,
        email=email,
        country=country,
        preferred_currency=preferred_currency,
        role="customer",
        account_status="active"
    )
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    login_user(new_user)
    return jsonify({
        "status": "success",
        "message": "User registered and logged in successfully",
        "user": new_user.to_dict()
    }), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
@auth_bp.route("/auth/api/login", methods=["POST"])
@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    payload = request.get_json(force=True, silent=True) or {}
    identifier = (payload.get("identifier") or payload.get("username") or "").strip()
    password = payload.get("password", "")

    if not identifier or not password:
        return jsonify({"status": "error", "message": "Identifier and password required"}), 422

    user = User.query.filter(
        (User.email.ilike(identifier)) | (User.username.ilike(identifier))
    ).first()

    if not user or not user.check_password(password):
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401

    if user.account_status != "active":
        return jsonify({"status": "error", "message": "Account deactivated. Contact administrator."}), 403

    login_user(user)
    return jsonify({
        "status": "success",
        "message": f"Welcome {user.full_name}",
        "user": user.to_dict()
    }), 200


@auth_bp.route("/api/auth/logout", methods=["POST"])
@auth_bp.route("/auth/api/logout", methods=["POST"])
@auth_bp.route("/api/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"status": "success", "message": "Logged out successfully"}), 200


@auth_bp.route("/api/auth/me", methods=["GET"])
@auth_bp.route("/auth/api/me", methods=["GET"])
@auth_bp.route("/api/me", methods=["GET"])
def api_me():
    if not current_user.is_authenticated:
        return jsonify({"status": "unauthenticated", "user": None}), 200
    return jsonify({
        "status": "authenticated",
        "user": current_user.to_dict(include_stats=True)
    }), 200

