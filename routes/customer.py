"""
FraudGuard – Customer Portal & Isolated Personal API
===================================================
Enforces strict customer data isolation:
Every query filters exclusively by current_user.id.
No customer can view, search, or access another customer's data.
"""

from datetime import datetime
from flask import (
    Blueprint, render_template, request, jsonify,
    send_file, flash, redirect, url_for, Response
)
from flask_login import login_required, current_user
from database.models import db, User, Transaction, AuditLog
from services.currency_service import CurrencyService
from services.fraud_service import FraudService
from services.transaction_service import TransactionService
from services.analytics_service import AnalyticsService

customer_bp = Blueprint("customer", __name__, url_prefix="/customer")

# =============================================================================
# WEB VIEW PAGES
# =============================================================================

@customer_bp.route("/dashboard")
@login_required
def dashboard_view():
    """Personalized customer dashboard."""
    currencies = CurrencyService.get_supported_currencies()
    return render_template("customer/dashboard.html", active_page="dashboard", currencies=currencies)


@customer_bp.route("/detection")
@login_required
def detection_view():
    """Customer transaction fraud analysis interface."""
    currencies = CurrencyService.get_supported_currencies()
    return render_template("customer/detection.html", active_page="detection", currencies=currencies)


@customer_bp.route("/history")
@login_required
def history_view():
    """Customer personal transaction audit log."""
    currencies = CurrencyService.get_supported_currencies()
    return render_template("customer/history.html", active_page="history", currencies=currencies)


@customer_bp.route("/analytics")
@login_required
def analytics_view():
    """Customer personal fraud analytics & radar charts."""
    return render_template("customer/analytics.html", active_page="analytics")


@customer_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile_view():
    """Customer profile view and editor."""
    currencies = CurrencyService.get_supported_currencies()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        country = request.form.get("country", "").strip()
        preferred_currency = request.form.get("preferred_currency", "USD").strip().upper()

        if full_name:
            current_user.full_name = full_name
        if country:
            current_user.country = country
        if CurrencyService.is_valid_currency(preferred_currency):
            current_user.preferred_currency = preferred_currency

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("customer.profile_view"))

    return render_template("customer/profile.html", active_page="profile", currencies=currencies)


@customer_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings_view():
    """Customer account security & password management."""
    if request.method == "POST":
        current_pwd = request.form.get("current_password", "")
        new_pwd = request.form.get("new_password", "")
        confirm_pwd = request.form.get("confirm_password", "")

        if not current_user.check_password(current_pwd):
            flash("Current password incorrect.", "danger")
            return render_template("customer/settings.html", active_page="settings")

        if len(new_pwd) < 6:
            flash("New password must be at least 6 characters long.", "danger")
            return render_template("customer/settings.html", active_page="settings")

        if new_pwd != confirm_pwd:
            flash("New passwords do not match.", "danger")
            return render_template("customer/settings.html", active_page="settings")

        current_user.set_password(new_pwd)
        db.session.commit()
        flash("Password updated successfully.", "success")
        return redirect(url_for("customer.settings_view"))

    return render_template("customer/settings.html", active_page="settings")


@customer_bp.route("/help")
@login_required
def help_view():
    """Customer help, support & fraud prevention guide."""
    return render_template("customer/help.html", active_page="help")

# =============================================================================
# CUSTOMER REST API ENDPOINTS (DATA-ISOLATED)
# =============================================================================

@customer_bp.route("/api/dashboard", methods=["GET"])
@login_required
def api_dashboard():
    """
    Returns personal KPIs and recent transactions.
    STRICT DATA ISOLATION: Only transactions where user_id == current_user.id.
    """
    analytics = AnalyticsService.get_customer_analytics(current_user.id)
    recents = Transaction.query.filter_by(user_id=current_user.id).order_by(
        Transaction.created_at.desc()
    ).limit(8).all()

    return jsonify({
        "status": "success",
        "user": current_user.to_dict(),
        "summary": analytics["summary"],
        "recent_transactions": [t.to_dict() for t in recents],
        "channel_stats": analytics["channel_stats"],
        "ratio_chart": analytics["ratio_chart"]
    })


@customer_bp.route("/api/transactions", methods=["GET"])
@login_required
def api_transactions():
    """
    Paginated search, filter, and sort for customer's isolated history.
    """
    search = request.args.get("search", "")
    status = request.args.get("status", "all")
    currency = request.args.get("currency", "all")
    txn_type = request.args.get("type", "all")
    sort_by = request.args.get("sort", "date_desc")
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(max(int(request.args.get("per_page", 20)), 5), 100)

    result = TransactionService.get_customer_transactions(
        user_id=current_user.id,
        search=search,
        status=status,
        currency=currency,
        txn_type=txn_type,
        sort_by=sort_by,
        page=page,
        per_page=per_page
    )

    return jsonify({
        "status": "success",
        "data": result,
        "transactions": result.get("transactions", []),
        "pagination": result.get("pagination", {})
    })


@customer_bp.route("/api/transactions/<int:txn_id>", methods=["GET", "DELETE"])
@login_required
def api_transaction_detail(txn_id):
    """
    View or delete an individual customer transaction.
    STRICT ISOLATION CHECK: If record belongs to another user, returns 404.
    """
    txn = TransactionService.get_customer_transaction(current_user.id, txn_id)
    if not txn:
        return jsonify({"status": "error", "message": "Transaction record not found or access denied."}), 404

    if request.method == "DELETE":
        success, msg = TransactionService.delete_customer_transaction(current_user.id, txn_id)
        return jsonify({"status": "success" if success else "error", "message": msg})

    return jsonify({"status": "success", "data": txn.to_dict()})


@customer_bp.route("/api/transactions/predict", methods=["POST"])
@login_required
def api_predict_transaction():
    """
    Customer submits transaction parameters for ML fraud detection.
    Preprocesses with currency normalization and saves under current_user.id.
    """
    payload = request.get_json(force=True, silent=True) or {}

    try:
        amount = payload.get("amount")
        currency = payload.get("currency", current_user.preferred_currency)
        trans_type = payload.get("type", "PAYMENT")
        old_org = payload.get("oldbalanceOrg")
        new_orig = payload.get("newbalanceOrig")
        old_dest = payload.get("oldbalanceDest")
        new_dest = payload.get("newbalanceDest")
        hour = payload.get("hour_of_day", 12)
        sender = payload.get("sender_account")
        recipient = payload.get("recipient_account")

        result = FraudService.evaluate_and_record(
            user=current_user,
            amount=amount,
            currency_code=currency,
            trans_type=trans_type,
            old_org=old_org,
            new_orig=new_orig,
            old_dest=old_dest,
            new_dest=new_dest,
            hour_of_day=hour,
            sender_account=sender,
            recipient_account=recipient,
            ip_address=request.remote_addr
        )

        return jsonify({
            "status": "success",
            "message": f"Transaction evaluated: {result['prediction']}",
            "data": result
        }), 201

    except ValueError as ve:
        return jsonify({"status": "error", "message": str(ve)}), 422
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Prediction service error: {str(e)}"}), 500


@customer_bp.route("/api/transactions/export", methods=["GET"])
@login_required
def api_export_transactions():
    """
    Exports customer's isolated history to CSV or PDF.
    """
    fmt = request.args.get("format", "csv").lower()

    if fmt == "pdf":
        pdf_bytes = TransactionService.export_customer_pdf(current_user.id)
        filename = f"FraudGuard_Statement_{current_user.username}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    # CSV default
    csv_bytes = TransactionService.export_customer_csv(current_user.id)
    filename = f"FraudGuard_Transactions_{current_user.username}_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@customer_bp.route("/api/analytics", methods=["GET"])
@login_required
def api_analytics():
    """Returns isolated customer telemetry for graphs and charts."""
    data = AnalyticsService.get_customer_analytics(current_user.id)
    return jsonify({"status": "success", "data": data})


@customer_bp.route("/api/profile", methods=["GET", "PUT"])
@login_required
def api_profile():
    if request.method == "PUT":
        payload = request.get_json(force=True, silent=True) or {}
        full_name = payload.get("full_name", "").strip()
        country = payload.get("country", "").strip()
        preferred_currency = payload.get("preferred_currency", "").strip().upper()

        if full_name:
            current_user.full_name = full_name
        if country:
            current_user.country = country
        if CurrencyService.is_valid_currency(preferred_currency):
            current_user.preferred_currency = preferred_currency

        db.session.commit()
        return jsonify({"status": "success", "message": "Profile updated", "user": current_user.to_dict()})

    return jsonify({"status": "success", "user": current_user.to_dict(include_stats=True)})

