"""
FraudGuard – Administrator Portal & Management API
==================================================
Role-based authorization: Accessible only to users with role="admin".
Provides platform-wide customer management, transaction oversight,
audit log inspection, and ML model monitoring.
"""

from flask import (
    Blueprint, render_template, request, jsonify, flash, redirect, url_for
)
from flask_login import login_required, current_user
from database.models import db, User, Transaction, AuditLog, ModelMetadata
from routes.auth import admin_required
from services.currency_service import CurrencyService
from services.transaction_service import TransactionService
from services.analytics_service import AnalyticsService
from ml.predict import get_metrics

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# =============================================================================
# ADMIN WEB VIEW PAGES
# =============================================================================

@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard_view():
    """Administrator platform-wide control dashboard."""
    return render_template("admin/dashboard.html", active_page="dashboard")


@admin_bp.route("/customers")
@login_required
@admin_required
def customers_view():
    """Customer management page."""
    return render_template("admin/customers.html", active_page="customers")


@admin_bp.route("/transactions")
@login_required
@admin_required
def transactions_view():
    """Platform-wide transaction management page."""
    currencies = CurrencyService.get_supported_currencies()
    return render_template("admin/transactions.html", active_page="transactions", currencies=currencies)


@admin_bp.route("/analytics")
@login_required
@admin_required
def analytics_view():
    """Platform-wide analytics, trends & confusion matrix."""
    return render_template("admin/analytics.html", active_page="analytics")


@admin_bp.route("/model-info")
@login_required
@admin_required
def model_info_view():
    """ML Model performance, algorithm comparison, and feature weights."""
    return render_template("admin/model_info.html", active_page="model_info")


@admin_bp.route("/audit-logs")
@login_required
@admin_required
def audit_logs_view():
    """System-wide security and operations audit log viewer."""
    return render_template("admin/audit_logs.html", active_page="audit_logs")


@admin_bp.route("/settings")
@login_required
@admin_required
def settings_view():
    """Administrative security settings and cache management."""
    return render_template("admin/settings.html", active_page="settings")

# =============================================================================
# ADMIN REST API ENDPOINTS
# =============================================================================

@admin_bp.route("/api/dashboard", methods=["GET"])
@login_required
@admin_required
def api_dashboard():
    """Returns platform-wide administrative KPI metrics."""
    analytics = AnalyticsService.get_admin_analytics()
    recents = Transaction.query.order_by(Transaction.created_at.desc()).limit(10).all()

    return jsonify({
        "status": "success",
        "platform_stats": analytics["platform_stats"],
        "channel_stats": analytics["channel_stats"],
        "recent_transactions": [t.to_dict() for t in recents],
        "signup_trends": analytics["signup_trends"]
    })


@admin_bp.route("/api/customers", methods=["GET"])
@login_required
@admin_required
def api_customers():
    """Paginated customer management table with search."""
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "all").strip().lower()
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(max(int(request.args.get("per_page", 20)), 5), 100)

    query = User.query.filter_by(role="customer")

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.full_name.ilike(search_term)) |
            (User.username.ilike(search_term)) |
            (User.email.ilike(search_term)) |
            (User.country.ilike(search_term))
        )

    if status in ["active", "deactivated"]:
        query = query.filter_by(account_status=status)

    query = query.order_by(User.created_at.desc())
    total = query.count()
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "status": "success",
        "data": {
            "customers": [u.to_dict(include_stats=True) for u in pagination.items],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev
        }
    })


@admin_bp.route("/api/customers/<int:user_id>", methods=["GET"])
@login_required
@admin_required
def api_customer_detail(user_id):
    """View customer profile and isolated stats. Passwords never exposed."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "Customer not found"}), 404

    customer_dict = user.to_dict(include_stats=True)
    recent_txns = user.transactions.limit(5).all()
    customer_dict["recent_transactions"] = [t.to_dict() for t in recent_txns]

    return jsonify({"status": "success", "data": customer_dict})


@admin_bp.route("/api/customers/<int:user_id>/status", methods=["PATCH"])
@login_required
@admin_required
def api_toggle_customer_status(user_id):
    """Activates or deactivates a customer account."""
    if user_id == current_user.id:
        return jsonify({"status": "error", "message": "Administrators cannot deactivate their own account"}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "Customer not found"}), 404

    payload = request.get_json(force=True, silent=True) or {}
    new_status = payload.get("status", "").lower()

    if new_status not in ["active", "deactivated"]:
        new_status = "deactivated" if user.account_status == "active" else "active"

    user.account_status = new_status

    # Security audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="CUSTOMER_STATUS_CHANGED",
        resource_type="user",
        resource_id=str(user.id),
        details=f"Admin {current_user.username} set status of customer {user.username} to {new_status}",
        ip_address=request.remote_addr
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"Customer account {user.username} is now {new_status}",
        "account_status": new_status
    })


@admin_bp.route("/api/transactions", methods=["GET"])
@login_required
@admin_required
def api_transactions():
    """Platform-wide transactions with admin filtering."""
    search = request.args.get("search", "")
    status = request.args.get("status", "all")
    customer_id = request.args.get("customer_id")
    currency = request.args.get("currency")
    sort_by = request.args.get("sort", "date_desc")
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(max(int(request.args.get("per_page", 25)), 5), 100)

    result = TransactionService.get_admin_transactions(
        search=search,
        status=status,
        customer_id=customer_id,
        currency=currency,
        sort_by=sort_by,
        page=page,
        per_page=per_page
    )

    return jsonify({"status": "success", "data": result})


@admin_bp.route("/api/analytics", methods=["GET"])
@login_required
@admin_required
def api_analytics():
    """Global administrative telemetry."""
    data = AnalyticsService.get_admin_analytics()
    return jsonify({"status": "success", "data": data})


@admin_bp.route("/api/model-info", methods=["GET"])
@login_required
@admin_required
def api_model_info():
    """Offline ML evaluation metrics & model parameters."""
    metadata = get_metrics()
    return jsonify({"status": "success", "data": metadata})


@admin_bp.route("/api/audit-logs", methods=["GET"])
@login_required
@admin_required
def api_audit_logs():
    """System-wide security audit logs."""
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(max(int(request.args.get("per_page", 30)), 5), 100)

    query = AuditLog.query.order_by(AuditLog.timestamp.desc())
    total = query.count()
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "status": "success",
        "data": {
            "logs": [log.to_dict() for log in pagination.items],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages
        }
    })

