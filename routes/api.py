"""
FraudGuard – Public Routes & General API Controller
===================================================
Renders public-facing marketing pages (Landing, About, Features,
How-it-works) and exposes general health and demo preset endpoints.
"""

from datetime import datetime, timezone
from flask import Blueprint, render_template, jsonify
from ml.predict import get_model, get_metrics
from services.currency_service import CurrencyService

api_bp = Blueprint("api", __name__)

# =============================================================================
# PUBLIC WEB PAGES
# =============================================================================

@api_bp.route("/")
def landing_page():
    """Main public cybersecurity landing page."""
    currencies = CurrencyService.get_supported_currencies()
    return render_template("index.html", currencies=currencies)


@api_bp.route("/about")
def about_page():
    """About FraudGuard mission, architecture, and technology."""
    return render_template("about.html", active_page="about")


@api_bp.route("/features")
def features_page():
    """Platform features, multi-currency, and data isolation specs."""
    return render_template("features.html", active_page="features")


@api_bp.route("/how-it-works")
def how_it_works_page():
    """Mathematical explainability & ML pipeline overview."""
    return render_template("how_it_works.html", active_page="how_it_works")

# =============================================================================
# GENERAL PUBLIC REST APIs
# =============================================================================

@api_bp.route("/api/health", methods=["GET"])
def health_check():
    """System health status."""
    model = get_model()
    return jsonify({
        "status": "healthy",
        "service": "FraudGuard Enterprise Fraud Detection",
        "model_loaded": model is not None,
        "database": "sqlite_connected",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@api_bp.route("/api/sample-transactions", methods=["GET"])
def sample_presets():
    """Provides curated test scenario templates for 1-click simulation."""
    presets = [
        {
            "name": "Standard Coffee / Retail Payment",
            "type": "PAYMENT",
            "amount": 14.50,
            "currency": "USD",
            "oldbalanceOrg": 1250.00,
            "newbalanceOrig": 1235.50,
            "oldbalanceDest": 0.00,
            "newbalanceDest": 0.00,
            "hour_of_day": 9,
            "expected": "LEGITIMATE",
            "description": "Routine everyday micro-payment with natural balance subtraction."
        },
        {
            "name": "Legitimate Monthly Salary Deposit",
            "type": "CASH_IN",
            "amount": 3500.00,
            "currency": "USD",
            "oldbalanceOrg": 850.00,
            "newbalanceOrig": 4350.00,
            "oldbalanceDest": 24000.00,
            "newbalanceDest": 20500.00,
            "hour_of_day": 14,
            "expected": "LEGITIMATE",
            "description": "Corporate payroll deposit with proper inflow balance increment."
        },
        {
            "name": "High-Risk Account Takeover Drain",
            "type": "TRANSFER",
            "amount": 185000.00,
            "currency": "USD",
            "oldbalanceOrg": 185000.00,
            "newbalanceOrig": 0.00,
            "oldbalanceDest": 0.00,
            "newbalanceDest": 0.00,
            "hour_of_day": 3,
            "expected": "FRAUDULENT",
            "description": "Entire account drained at 3 AM to an empty mule destination."
        },
        {
            "name": "Midnight Cash-Out Outflow",
            "type": "CASH_OUT",
            "amount": 92000.00,
            "currency": "USD",
            "oldbalanceOrg": 95000.00,
            "newbalanceOrig": 3000.00,
            "oldbalanceDest": 0.00,
            "newbalanceDest": 0.00,
            "hour_of_day": 1,
            "expected": "FRAUDULENT",
            "description": "Sudden 96.8% balance liquidation at 1 AM with zero recipient trace."
        }
    ]
    return jsonify({"status": "success", "samples": presets})

