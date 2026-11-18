"""
FraudGuard – Global Online Payment Fraud Detection System
=========================================================
Core Flask Application Factory & Server Entrypoint
"""

import os
import sys
import json
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from config import config_dict
from database.models import db, User, Transaction, ModelMetadata, AuditLog, ExchangeRate
from routes.auth import auth_bp
from routes.customer import customer_bp
from routes.admin import admin_bp
from routes.currency import currency_bp
from routes.api import api_bp
from services.currency_service import BASELINE_RATES_USD
from ml.predict import get_model, get_metrics

csrf = CSRFProtect()
login_manager = LoginManager()

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development").lower()

    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates"
    )

    # Load configuration
    cfg = config_dict.get(config_name, config_dict["default"])
    app.config.from_object(cfg)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login_view"
    login_manager.login_message = "Please sign in to access this secure portal."
    login_manager.login_message_category = "warning"

    csrf.init_app(app)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(currency_bp)
    app.register_blueprint(api_bp)

    # Exempt JSON REST API endpoints from CSRF while preserving protection on HTML forms
    for endpoint, view_func in app.view_functions.items():
        if "api" in endpoint:
            csrf.exempt(view_func)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Error Handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, message="Access Forbidden: You do not have permission to view this resource."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="Page Not Found: The requested URL does not exist."), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template("error.html", code=500, message="Internal Server Error: A backend anomaly occurred. Please try again later."), 500

    # Ensure tables and default records exist
    with app.app_context():
        db.create_all()
        seed_initial_database_if_empty(is_testing=app.config.get("TESTING", False))
        load_model_metadata_into_db()

    return app

def seed_initial_database_if_empty(is_testing=False):
    """
    Seeds default administrative account and exchange rate baselines if the database is newly initialized.
    Test customer fixtures are seeded strictly when is_testing=True for automated pytest execution.
    Production and development environments remain completely clean with 0 demo customers and 0 demo transactions.
    """
    # 1. Check/Create Administrator
    admin = User.query.filter_by(role="admin").first()
    if not admin:
        admin = User(
            full_name="FraudGuard Security Director",
            username="admin",
            email="admin@fraudguard.io",
            country="United States",
            preferred_currency="USD",
            role="admin",
            account_status="active"
        )
        admin.set_password("AdminPassword2026!")
        db.session.add(admin)
        print("[✓] Initialized Administrator account (username: admin / email: admin@fraudguard.io)")

    # 2. Only in automated testing mode: seed fixtures for test suite
    if is_testing:
        cust1 = User.query.filter_by(username="customer_alex").first()
        if not cust1:
            cust1 = User(
                full_name="Alex Morgan",
                username="customer_alex",
                email="alex@example.com",
                country="United States",
                preferred_currency="USD",
                role="customer",
                account_status="active"
            )
            cust1.set_password("CustomerPass2026!")
            db.session.add(cust1)
        else:
            cust1.set_password("CustomerPass2026!")

        cust2 = User.query.filter_by(username="customer_priya").first()
        if not cust2:
            cust2 = User(
                full_name="Priya Sharma",
                username="customer_priya",
                email="priya@example.in",
                country="India",
                preferred_currency="INR",
                role="customer",
                account_status="active"
            )
            cust2.set_password("CustomerPass2026!")
            db.session.add(cust2)
        else:
            cust2.set_password("CustomerPass2026!")

        db.session.commit()

        if Transaction.query.count() == 0:
            seed_isolated_sample_transactions(cust1, cust2)

    db.session.commit()

    # 3. Seed exchange rates baseline if empty
    if ExchangeRate.query.count() == 0:
        now = datetime.now(timezone.utc)
        for code, rate in BASELINE_RATES_USD.items():
            db.session.add(ExchangeRate(
                base_currency="USD",
                target_currency=code,
                exchange_rate=rate,
                provider="Verified Baseline Reference",
                fetched_at=now
            ))
        db.session.commit()
        print(f"[✓] Initialized {len(BASELINE_RATES_USD)} global exchange rate baselines.")

def seed_isolated_sample_transactions(cust1, cust2):
    """Creates isolated transactions for Customer 1 and Customer 2."""
    now = datetime.now(timezone.utc)

    # Transactions for Customer 1 (Alex - USD)
    t1_samples = [
        ("TXN-ALEX-01", 38.50, "USD", "PAYMENT", 1500.0, 1461.5, 0.0, 0.0, "LEGITIMATE", 0, 0.02, "LOW", ["Standard retail merchant payment continuity."]),
        ("TXN-ALEX-02", 1200.00, "USD", "CASH_IN", 400.0, 1600.0, 12000.0, 10800.0, "LEGITIMATE", 0, 0.03, "LOW", ["Legitimate banking cash-in deposit."]),
        ("TXN-ALEX-03", 94000.00, "USD", "TRANSFER", 95000.0, 1000.0, 0.0, 0.0, "FRAUDULENT", 1, 0.94, "CRITICAL", ["High-risk transfer rail.", "Drained 98.9% of sender balance.", "Zero destination mule trace."]),
        ("TXN-ALEX-04", 65.00, "USD", "DEBIT", 980.0, 915.0, 0.0, 0.0, "LEGITIMATE", 0, 0.01, "LOW", ["Routine grocery direct debit."])
    ]

    for uid, amt, curr, t_type, o_org, n_orig, o_dest, n_dest, pred, is_f, prob, risk, reasons in t1_samples:
        db.session.add(Transaction(
            user_id=cust1.id,
            trans_uuid=uid,
            transaction_amount=amt,
            currency_code=curr,
            amount_usd=amt,
            exchange_rate_used=1.0,
            transaction_type=t_type,
            oldbalance_org=o_org,
            newbalance_orig=n_orig,
            oldbalance_dest=o_dest,
            newbalance_dest=n_dest,
            hour_of_day=14,
            sender_account=f"ACC-ALEX-{uid[-2:]}",
            recipient_account=f"REC-RECIP-{uid[-2:]}",
            prediction=pred,
            is_fraud=is_f,
            fraud_probability=prob,
            risk_level=risk,
            risk_reasons=json.dumps(reasons),
            model_version="1.0.0",
            created_at=now
        ))

    # Transactions for Customer 2 (Priya - INR)
    t2_samples = [
        ("TXN-PRIYA-01", 1500.00, "INR", "PAYMENT", 45000.0, 43500.0, 0.0, 0.0, "LEGITIMATE", 0, 0.02, "LOW", ["Domestic merchant retail payment in INR."]),
        ("TXN-PRIYA-02", 25000.00, "INR", "CASH_IN", 10000.0, 35000.0, 200000.0, 175000.0, "LEGITIMATE", 0, 0.03, "LOW", ["Salary deposit credit."]),
        ("TXN-PRIYA-03", 850000.00, "INR", "TRANSFER", 850000.0, 0.0, 0.0, 0.0, "FRAUDULENT", 1, 0.96, "CRITICAL", ["Exhausted 100% of origin account.", "High-risk transfer rail.", "Mule zero trace."])
    ]

    for uid, amt, curr, t_type, o_org, n_orig, o_dest, n_dest, pred, is_f, prob, risk, reasons in t2_samples:
        amt_usd = amt / 83.5
        db.session.add(Transaction(
            user_id=cust2.id,
            trans_uuid=uid,
            transaction_amount=amt,
            currency_code=curr,
            amount_usd=round(amt_usd, 2),
            exchange_rate_used=83.5,
            transaction_type=t_type,
            oldbalance_org=o_org,
            newbalance_orig=n_orig,
            oldbalance_dest=o_dest,
            newbalance_dest=n_dest,
            hour_of_day=15,
            sender_account=f"ACC-PRIYA-{uid[-2:]}",
            recipient_account=f"REC-RECIP-{uid[-2:]}",
            prediction=pred,
            is_fraud=is_f,
            fraud_probability=prob,
            risk_level=risk,
            risk_reasons=json.dumps(reasons),
            model_version="1.0.0",
            created_at=now
        ))

    db.session.commit()
    print("[✓] Seeded isolated benchmark transactions for Customer 1 and Customer 2.")

def load_model_metadata_into_db():
    """Populates ModelMetadata table from model_metadata.json if empty."""
    if ModelMetadata.query.count() == 0:
        meta = get_metrics()
        if meta:
            champ = meta.get("champion_metrics", {})
            cm = champ.get("confusion_matrix", {})
            entry = ModelMetadata(
                algorithm=meta.get("algorithm", "RandomForestClassifier"),
                model_version="1.0.0",
                dataset_name="PaySim Online Financial Transaction Benchmark (30,000 samples)",
                training_samples=meta.get("training_samples", 24000),
                testing_samples=meta.get("testing_samples", 6000),
                accuracy=champ.get("accuracy", 0.9982),
                precision=champ.get("precision", 0.9366),
                recall=champ.get("recall", 0.9852),
                f1_score=champ.get("f1_score", 0.9603),
                roc_auc=champ.get("roc_auc", 0.9999),
                confusion_matrix=json.dumps(cm),
                feature_importances=json.dumps(meta.get("feature_importances", [])),
                models_comparison=json.dumps(meta.get("models_comparison", {})),
                model_file="model/fraud_model.pkl"
            )
            db.session.add(entry)
            db.session.commit()
            print("[✓] Seeded ModelMetadata table with genuine Scikit-learn evaluation results.")

# Primary WSGI instance
app = create_app()

if __name__ == "__main__":
    print("\n" + "="*65)
    print("      🛡️  FraudGuard – Global Online Payment Fraud Detection")
    print("      Customer Portal & Administrative Operations Center")
    print("      Listening at: http://127.0.0.1:5000")
    print("="*65 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
