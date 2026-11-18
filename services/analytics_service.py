"""
FraudGuard – Analytics & Telemetry Service
==========================================
Computes isolated customer analytics and platform-wide administrative statistics.
Clearly distinguishes offline training benchmarks from live production telemetry.
"""

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from database.models import db, User, Transaction, AuditLog
from ml.predict import get_metrics
from services.currency_service import CurrencyService

class AnalyticsService:
    @staticmethod
    def get_customer_analytics(user_id):
        """
        Computes personalized telemetry strictly for the authenticated customer.
        CUSTOMER DATA ISOLATION: Exclusively filters by user_id.
        """
        user = db.session.get(User, user_id)
        txns = Transaction.query.filter_by(user_id=user_id).all()

        total = len(txns)
        fraud_count = sum(1 for t in txns if t.is_fraud == 1)
        legit_count = total - fraud_count
        fraud_rate = round((fraud_count / total * 100), 2) if total > 0 else 0.0

        total_volume_usd = sum(t.amount_usd for t in txns)
        avg_amount_usd = round(total_volume_usd / total, 2) if total > 0 else 0.0

        # Channel breakdown
        channels = ["PAYMENT", "TRANSFER", "CASH_OUT", "CASH_IN", "DEBIT"]
        channel_data = {c: {"total": 0, "fraud": 0, "legit": 0} for c in channels}
        for t in txns:
            c = t.transaction_type
            if c not in channel_data:
                channel_data[c] = {"total": 0, "fraud": 0, "legit": 0}
            channel_data[c]["total"] += 1
            if t.is_fraud == 1:
                channel_data[c]["fraud"] += 1
            else:
                channel_data[c]["legit"] += 1

        # Currency breakdown
        currency_counts = defaultdict(int)
        for t in txns:
            currency_counts[t.currency_code] += 1

        # Risk tier breakdown
        risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        for t in txns:
            r = t.risk_level or "LOW"
            risk_counts[r] = risk_counts.get(r, 0) + 1

        # Recent timeline (last 7 days)
        now = datetime.now(timezone.utc)
        timeline = {}
        for i in range(6, -1, -1):
            d_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            timeline[d_str] = {"total": 0, "fraud": 0}

        for t in txns:
            if t.created_at:
                d_str = t.created_at.strftime("%Y-%m-%d")
                if d_str in timeline:
                    timeline[d_str]["total"] += 1
                    if t.is_fraud == 1:
                        timeline[d_str]["fraud"] += 1

        pref_currency = user.preferred_currency if user else "USD"

        return {
            "summary": {
                "total_transactions": total,
                "legitimate_transactions": legit_count,
                "fraudulent_transactions": fraud_count,
                "fraud_rate": fraud_rate,
                "total_volume_usd": round(total_volume_usd, 2),
                "avg_amount_usd": avg_amount_usd,
                "formatted_volume": CurrencyService.format_amount(total_volume_usd, "USD"),
                "preferred_currency": pref_currency
            },
            "ratio_chart": {
                "labels": ["Legitimate", "Fraudulent"],
                "data": [legit_count, fraud_count]
            },
            "channel_stats": [
                {"channel": k, "total": v["total"], "fraud": v["fraud"], "legit": v["legit"]}
                for k, v in channel_data.items()
            ],
            "currency_distribution": dict(currency_counts),
            "risk_distribution": risk_counts,
            "timeline": [
                {"date": k, "total": v["total"], "fraud": v["fraud"]}
                for k, v in timeline.items()
            ]
        }

    @staticmethod
    def get_admin_analytics():
        """
        Computes platform-wide global metrics for authorized administrators.
        Includes customer counts, global fraud rates, and offline ML evaluation benchmarks.
        """
        total_customers = User.query.filter_by(role="customer").count()
        active_customers = User.query.filter_by(role="customer", account_status="active").count()
        deactivated_customers = total_customers - active_customers

        all_txns = Transaction.query.all()
        total_txns = len(all_txns)
        fraud_txns = sum(1 for t in all_txns if t.is_fraud == 1)
        legit_txns = total_txns - fraud_txns
        fraud_rate = round((fraud_txns / total_txns * 100), 2) if total_txns > 0 else 0.0

        total_volume_usd = sum(t.amount_usd for t in all_txns)
        avg_fraud_volume = (
            sum(t.amount_usd for t in all_txns if t.is_fraud == 1) / fraud_txns
        ) if fraud_txns > 0 else 0.0
        avg_legit_volume = (
            sum(t.amount_usd for t in all_txns if t.is_fraud == 0) / legit_txns
        ) if legit_txns > 0 else 0.0

        # Global channel breakdown
        channels = ["PAYMENT", "TRANSFER", "CASH_OUT", "CASH_IN", "DEBIT"]
        channel_stats = []
        for c in channels:
            c_txns = [t for t in all_txns if t.transaction_type == c]
            c_fraud = sum(1 for t in c_txns if t.is_fraud == 1)
            channel_stats.append({
                "channel": c,
                "total": len(c_txns),
                "fraud": c_fraud,
                "legitimate": len(c_txns) - c_fraud
            })

        # Global currency breakdown
        currency_dist = defaultdict(int)
        for t in all_txns:
            currency_dist[t.currency_code] += 1

        # Global risk distribution
        risk_dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        for t in all_txns:
            r = t.risk_level or "LOW"
            risk_dist[r] = risk_dist.get(r, 0) + 1

        # User signups over the last 14 days
        now = datetime.now(timezone.utc)
        signup_timeline = {}
        for i in range(13, -1, -1):
            d_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            signup_timeline[d_str] = 0

        customers = User.query.filter_by(role="customer").all()
        for u in customers:
            if u.created_at:
                d_str = u.created_at.strftime("%Y-%m-%d")
                if d_str in signup_timeline:
                    signup_timeline[d_str] += 1

        # Offline ML Evaluation Benchmark Data
        offline_metadata = get_metrics()

        return {
            "platform_stats": {
                "total_customers": total_customers,
                "active_customers": active_customers,
                "deactivated_customers": deactivated_customers,
                "total_transactions": total_txns,
                "legitimate_transactions": legit_txns,
                "fraudulent_transactions": fraud_txns,
                "fraud_rate": fraud_rate,
                "total_volume_usd": round(total_volume_usd, 2),
                "formatted_volume": CurrencyService.format_amount(total_volume_usd, "USD"),
                "avg_fraud_volume": CurrencyService.format_amount(avg_fraud_volume, "USD"),
                "avg_legit_volume": CurrencyService.format_amount(avg_legit_volume, "USD")
            },
            "channel_stats": channel_stats,
            "currency_distribution": dict(currency_dist),
            "risk_distribution": risk_dist,
            "signup_trends": [
                {"date": k, "signups": v} for k, v in signup_timeline.items()
            ],
            "offline_evaluation": offline_metadata
        }

