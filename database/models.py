"""
FraudGuard – Database Models
============================
SQLAlchemy ORM models with strict user ownership isolation,
auditing, currency exchange caching, and ML model metadata tracking.
Designed for SQLite development and seamless PostgreSQL production deployment.
"""

import json
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    country = db.Column(db.String(64), nullable=False, default="United States")
    preferred_currency = db.Column(db.String(3), nullable=False, default="USD")
    role = db.Column(db.String(20), nullable=False, default="customer")  # 'customer' or 'admin'
    account_status = db.Column(db.String(20), nullable=False, default="active")  # 'active' or 'deactivated'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    transactions = db.relationship(
        "Transaction",
        backref="customer",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="Transaction.created_at.desc()"
    )
    audit_logs = db.relationship("AuditLog", backref="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == "admin"

    @property
    def is_active(self):
        """Flask-Login active account check."""
        return self.account_status == "active"

    def to_dict(self, include_stats=False):
        data = {
            "id": self.id,
            "full_name": self.full_name,
            "username": self.username,
            "email": self.email,
            "country": self.country,
            "preferred_currency": self.preferred_currency,
            "role": self.role,
            "account_status": self.account_status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        if include_stats:
            total_txns = self.transactions.count()
            fraud_txns = self.transactions.filter_by(is_fraud=1).count()
            data["transaction_count"] = total_txns
            data["fraud_count"] = fraud_txns
            data["fraud_rate"] = round((fraud_txns / total_txns * 100), 2) if total_txns > 0 else 0.0
        return data


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trans_uuid = db.Column(db.String(36), unique=True, nullable=False, index=True)
    
    # Currency and Amounts
    transaction_amount = db.Column(db.Float, nullable=False)
    currency_code = db.Column(db.String(3), nullable=False, default="USD", index=True)
    amount_usd = db.Column(db.Float, nullable=False)
    exchange_rate_used = db.Column(db.Float, nullable=False, default=1.0)
    
    # Financial parameters
    transaction_type = db.Column(db.String(20), nullable=False, index=True)  # PAYMENT, TRANSFER, etc.
    transaction_timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    oldbalance_org = db.Column(db.Float, nullable=False)
    newbalance_orig = db.Column(db.Float, nullable=False)
    oldbalance_dest = db.Column(db.Float, nullable=False)
    newbalance_dest = db.Column(db.Float, nullable=False)
    hour_of_day = db.Column(db.Integer, nullable=False, default=12)
    
    sender_account = db.Column(db.String(64), nullable=True)
    recipient_account = db.Column(db.String(64), nullable=True)

    # Machine Learning Output
    prediction = db.Column(db.String(20), nullable=False, index=True)  # LEGITIMATE or FRAUDULENT
    is_fraud = db.Column(db.Integer, nullable=False, index=True)        # 0 or 1
    fraud_probability = db.Column(db.Float, nullable=False)             # 0.0 to 1.0
    risk_level = db.Column(db.String(20), nullable=False, index=True)   # LOW, MEDIUM, HIGH, CRITICAL
    risk_reasons = db.Column(db.Text, nullable=True)                    # JSON list of explanations
    model_version = db.Column(db.String(32), nullable=False, default="1.0.0")
    transaction_features = db.Column(db.Text, nullable=True)            # JSON snapshot of all features
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    @property
    def user(self):
        """Convenience alias for backref customer."""
        return self.customer

    def to_dict(self):
        reasons = []
        if self.risk_reasons:
            try:
                reasons = json.loads(self.risk_reasons)
            except Exception:
                reasons = [self.risk_reasons]

        features = {}
        if self.transaction_features:
            try:
                features = json.loads(self.transaction_features)
            except Exception:
                features = {}

        return {
            "id": self.id,
            "user_id": self.user_id,
            "customer_name": self.customer.full_name if self.customer else "Unknown",
            "customer_username": self.customer.username if self.customer else "Unknown",
            "trans_uuid": self.trans_uuid,
            "transaction_amount": round(self.transaction_amount, 2),
            "currency_code": self.currency_code,
            "amount_usd": round(self.amount_usd, 2),
            "exchange_rate_used": round(self.exchange_rate_used, 4),
            "transaction_type": self.transaction_type,
            "transaction_timestamp": self.transaction_timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.transaction_timestamp else "",
            "oldbalance_org": round(self.oldbalance_org, 2),
            "newbalance_orig": round(self.newbalance_orig, 2),
            "oldbalance_dest": round(self.oldbalance_dest, 2),
            "newbalance_dest": round(self.newbalance_dest, 2),
            "hour_of_day": self.hour_of_day,
            "sender_account": self.sender_account or f"ACC-{self.id:06d}",
            "recipient_account": self.recipient_account or f"REC-{self.id:06d}",
            "prediction": self.prediction,
            "is_fraud": self.is_fraud,
            "fraud_probability": round(self.fraud_probability, 4),
            "fraud_probability_pct": f"{round(self.fraud_probability * 100, 2)}%",
            "risk_level": self.risk_level,
            "risk_reasons": reasons,
            "model_version": self.model_version,
            "transaction_features": features,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
        }


class ModelMetadata(db.Model):
    __tablename__ = "model_metadata"

    id = db.Column(db.Integer, primary_key=True)
    algorithm = db.Column(db.String(64), nullable=False)
    model_version = db.Column(db.String(32), nullable=False, unique=True)
    dataset_name = db.Column(db.String(120), nullable=False)
    training_samples = db.Column(db.Integer, nullable=False)
    testing_samples = db.Column(db.Integer, nullable=False)
    accuracy = db.Column(db.Float, nullable=False)
    precision = db.Column(db.Float, nullable=False)
    recall = db.Column(db.Float, nullable=False)
    f1_score = db.Column(db.Float, nullable=False)
    roc_auc = db.Column(db.Float, nullable=False)
    confusion_matrix = db.Column(db.Text, nullable=False)      # JSON {tn, fp, fn, tp}
    feature_importances = db.Column(db.Text, nullable=True)   # JSON list
    models_comparison = db.Column(db.Text, nullable=True)     # JSON object
    trained_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    model_file = db.Column(db.String(256), nullable=False)

    def to_dict(self):
        cm = {}
        if self.confusion_matrix:
            try:
                cm = json.loads(self.confusion_matrix)
            except Exception:
                cm = {}

        fi = []
        if self.feature_importances:
            try:
                fi = json.loads(self.feature_importances)
            except Exception:
                fi = []

        comp = {}
        if self.models_comparison:
            try:
                comp = json.loads(self.models_comparison)
            except Exception:
                comp = {}

        return {
            "id": self.id,
            "algorithm": self.algorithm,
            "model_version": self.model_version,
            "dataset_name": self.dataset_name,
            "training_samples": self.training_samples,
            "testing_samples": self.testing_samples,
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "roc_auc": round(self.roc_auc, 4),
            "confusion_matrix": cm,
            "feature_importances": fi,
            "models_comparison": comp,
            "trained_at": self.trained_at.strftime("%Y-%m-%d %H:%M:%S") if self.trained_at else "",
            "model_file": self.model_file
        }


class ExchangeRate(db.Model):
    __tablename__ = "exchange_rates"

    id = db.Column(db.Integer, primary_key=True)
    base_currency = db.Column(db.String(3), nullable=False, default="USD")
    target_currency = db.Column(db.String(3), nullable=False, index=True)
    exchange_rate = db.Column(db.Float, nullable=False)
    provider = db.Column(db.String(64), nullable=False, default="OpenExchangeRates")
    fetched_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("base_currency", "target_currency", name="uq_base_target_rate"),
    )

    def to_dict(self):
        return {
            "base_currency": self.base_currency,
            "target_currency": self.target_currency,
            "rate": self.exchange_rate,
            "provider": self.provider,
            "fetched_at": self.fetched_at.strftime("%Y-%m-%d %H:%M:%S") if self.fetched_at else ""
        }


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = db.Column(db.String(64), nullable=False, index=True)
    resource_type = db.Column(db.String(64), nullable=False)
    resource_id = db.Column(db.String(64), nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_email": self.user.email if self.user else "System",
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else ""
        }

