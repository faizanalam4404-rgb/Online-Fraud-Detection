"""
FraudGuard – Fraud Evaluation Service
=====================================
Orchestrates currency normalization, feature engineering,
model scoring, and persistent SQLite database recording.
"""

import json
import uuid
from datetime import datetime, timezone
from database.models import db, Transaction, AuditLog
from services.currency_service import CurrencyService
from ml.preprocessing import build_single_prediction_df
from ml.predict import predict_single, generate_risk_reasons

class FraudService:
    @staticmethod
    def evaluate_and_record(
        user,
        amount,
        currency_code,
        trans_type,
        old_org,
        new_orig,
        old_dest,
        new_dest,
        hour_of_day=12,
        sender_account=None,
        recipient_account=None,
        ip_address=None
    ):
        """
        Evaluates an online payment transaction:
        1. Validates currency and input bounds.
        2. Converts input amount from the transaction currency to USD base for the ML model.
        3. Runs Scikit-learn Random Forest pipeline on engineered feature row.
        4. Calculates fraud probability and assigns risk level.
        5. Persists the transaction under the authenticated user's ID.
        6. Logs audit record and returns result dictionary.
        """
        # Validate currency code
        currency_code = (currency_code or "USD").upper().strip()
        if not CurrencyService.is_valid_currency(currency_code):
            raise ValueError(f"Invalid or unsupported ISO 4217 currency code: {currency_code}")

        # Validate amounts and balances
        amt = float(amount)
        if amt <= 0:
            raise ValueError("Transaction amount must be strictly positive (> 0.00)")

        o_org = float(old_org)
        n_orig = float(new_orig)
        o_dest = float(old_dest)
        n_dest = float(new_dest)

        if any(b < 0 for b in [o_org, n_orig, o_dest, n_dest]):
            raise ValueError("Account balance values cannot be negative")

        t_type = str(trans_type).strip().upper()
        if t_type not in ["PAYMENT", "TRANSFER", "CASH_OUT", "CASH_IN", "DEBIT"]:
            raise ValueError(f"Unsupported transaction channel: {t_type}")

        hr = int(hour_of_day) if (0 <= int(hour_of_day) <= 23) else 12

        # Currency Conversion to USD Base for ML Model
        converted_usd, rate_used, provider, rate_time = CurrencyService.convert_to_usd(amt, from_curr=currency_code)
        old_org_usd, _, _, _ = CurrencyService.convert_to_usd(o_org, from_curr=currency_code)
        new_orig_usd, _, _, _ = CurrencyService.convert_to_usd(n_orig, from_curr=currency_code)
        old_dest_usd, _, _, _ = CurrencyService.convert_to_usd(o_dest, from_curr=currency_code)
        new_dest_usd, _, _, _ = CurrencyService.convert_to_usd(n_dest, from_curr=currency_code)

        # Build feature DataFrame with domain features
        df_row, engineered = build_single_prediction_df(
            amount_usd=converted_usd,
            trans_type=t_type,
            old_org=old_org_usd,
            new_orig=new_orig_usd,
            old_dest=old_dest_usd,
            new_dest=new_dest_usd,
            hour_of_day=hr
        )

        # Execute Scikit-learn Random Forest Prediction
        is_fraud, fraud_prob, prediction_label, risk_level = predict_single(df_row)

        # Generate transparent audit reasons
        reasons = generate_risk_reasons(
            amount_usd=converted_usd,
            trans_type=t_type,
            old_org=old_org_usd,
            new_orig=new_orig_usd,
            engineered=engineered,
            prob=fraud_prob
        )

        # Generate unique transaction reference ID
        trans_uuid = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        sender_id = (sender_account or "").strip() or f"ACC-{uuid.uuid4().hex[:6].upper()}"
        recipient_id = (recipient_account or "").strip() or f"REC-{uuid.uuid4().hex[:6].upper()}"

        feature_snapshot = {
            "amount_original": amt,
            "currency_code": currency_code,
            "amount_usd": round(converted_usd, 2),
            "exchange_rate": rate_used,
            "exchange_provider": provider,
            "engineered_features": engineered
        }

        # Persist transaction with strict user isolation
        txn = Transaction(
            user_id=user.id,
            trans_uuid=trans_uuid,
            transaction_amount=amt,
            currency_code=currency_code,
            amount_usd=converted_usd,
            exchange_rate_used=rate_used,
            transaction_type=t_type,
            transaction_timestamp=datetime.now(timezone.utc),
            oldbalance_org=o_org,
            newbalance_orig=n_orig,
            oldbalance_dest=o_dest,
            newbalance_dest=n_dest,
            hour_of_day=hr,
            sender_account=sender_id,
            recipient_account=recipient_id,
            prediction=prediction_label,
            is_fraud=is_fraud,
            fraud_probability=fraud_prob,
            risk_level=risk_level,
            risk_reasons=json.dumps(reasons),
            model_version="1.0.0",
            transaction_features=json.dumps(feature_snapshot)
        )
        db.session.add(txn)

        # Create security audit log
        audit = AuditLog(
            user_id=user.id,
            action="TRANSACTION_ANALYZED",
            resource_type="transaction",
            resource_id=trans_uuid,
            details=f"Analyzed {t_type} {amt} {currency_code} -> Result: {prediction_label} ({risk_level} Risk)",
            ip_address=ip_address
        )
        db.session.add(audit)
        db.session.commit()

        result_dict = txn.to_dict()
        result_dict["formatted_amount"] = CurrencyService.format_amount(amt, currency_code)
        result_dict["formatted_usd"] = CurrencyService.format_amount(converted_usd, "USD")
        result_dict["rate_info"] = {
            "rate": rate_used,
            "provider": provider,
            "timestamp": rate_time.strftime("%Y-%m-%d %H:%M:%S")
        }

        return result_dict

