"""
FraudGuard – Currency Controller & Exchange Rates API
=====================================================
Serves ISO 4217 currency metadata, live cached exchange rates,
and precision-safe conversions across all world currencies.
"""

from flask import Blueprint, request, jsonify
from services.currency_service import CurrencyService

currency_bp = Blueprint("currency", __name__, url_prefix="/api/currencies")

@currency_bp.route("", methods=["GET"])
def get_currencies():
    """Returns all supported ISO 4217 world currencies."""
    currencies = CurrencyService.get_supported_currencies()
    return jsonify({
        "status": "success",
        "total": len(currencies),
        "currencies": currencies
    })

@currency_bp.route("/rates", methods=["GET"])
def get_exchange_rates():
    """Returns current exchange rates, provider, and timestamp."""
    base = request.args.get("base", "USD").upper()
    rates, provider, timestamp = CurrencyService.fetch_live_rates(base)
    return jsonify({
        "status": "success",
        "base_currency": base,
        "provider": provider,
        "last_updated": timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if timestamp else None,
        "rates": rates
    })

@currency_bp.route("/convert", methods=["POST"])
def convert_currency():
    """Performs currency conversion calculation."""
    payload = request.get_json(force=True, silent=True) or {}
    try:
        amount = float(payload.get("amount", 0))
        from_curr = payload.get("from_currency", "USD").upper()
        to_curr = payload.get("to_currency", "USD").upper()

        if amount < 0:
            return jsonify({"status": "error", "message": "Amount must be non-negative"}), 422

        if not CurrencyService.is_valid_currency(from_curr):
            return jsonify({"status": "error", "message": f"Unsupported origin currency: {from_curr}"}), 422

        if not CurrencyService.is_valid_currency(to_curr):
            return jsonify({"status": "error", "message": f"Unsupported target currency: {to_curr}"}), 422

        converted, rate, provider, timestamp = CurrencyService.convert(amount, from_curr, to_curr)

        return jsonify({
            "status": "success",
            "original_amount": amount,
            "from_currency": from_curr,
            "converted_amount": converted,
            "to_currency": to_curr,
            "exchange_rate": rate,
            "provider": provider,
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if timestamp else None,
            "formatted_original": CurrencyService.format_amount(amount, from_curr),
            "formatted_converted": CurrencyService.format_amount(converted, to_curr)
        })

    except (ValueError, TypeError) as ve:
        return jsonify({"status": "error", "message": f"Invalid conversion parameters: {str(ve)}"}), 422

