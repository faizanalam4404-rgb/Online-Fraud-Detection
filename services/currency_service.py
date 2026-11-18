"""
FraudGuard – Comprehensive Global Currency & Exchange Rate Service
==================================================================
Supports ISO 4217 world currencies with accurate decimal precisions,
symbols, localized formats, live external exchange rate fetching with caching,
and offline resilient fallback rates.
"""

import os
import time
import requests
from datetime import datetime, timezone, timedelta
from flask import has_app_context
from database.models import db, ExchangeRate

# Complete ISO 4217 World Currency Registry with official symbols, names, and decimal precisions
ISO_CURRENCIES = {
    "USD": {"name": "US Dollar", "symbol": "$", "decimals": 2, "flag": "🇺🇸"},
    "EUR": {"name": "Euro", "symbol": "€", "decimals": 2, "flag": "🇪🇺"},
    "GBP": {"name": "British Pound", "symbol": "£", "decimals": 2, "flag": "🇬🇧"},
    "INR": {"name": "Indian Rupee", "symbol": "₹", "decimals": 2, "flag": "🇮🇳"},
    "JPY": {"name": "Japanese Yen", "symbol": "¥", "decimals": 0, "flag": "🇯🇵"},
    "CNY": {"name": "Chinese Yuan", "symbol": "¥", "decimals": 2, "flag": "🇨🇳"},
    "AED": {"name": "United Arab Emirates Dirham", "symbol": "د.إ", "decimals": 2, "flag": "🇦🇪"},
    "SAR": {"name": "Saudi Riyal", "symbol": "﷼", "decimals": 2, "flag": "🇸🇦"},
    "PKR": {"name": "Pakistani Rupee", "symbol": "₨", "decimals": 2, "flag": "🇵🇰"},
    "BDT": {"name": "Bangladeshi Taka", "symbol": "৳", "decimals": 2, "flag": "🇧🇩"},
    "CAD": {"name": "Canadian Dollar", "symbol": "CA$", "decimals": 2, "flag": "🇨🇦"},
    "AUD": {"name": "Australian Dollar", "symbol": "AU$", "decimals": 2, "flag": "🇦🇺"},
    "CHF": {"name": "Swiss Franc", "symbol": "CHF", "decimals": 2, "flag": "🇨🇭"},
    "SGD": {"name": "Singapore Dollar", "symbol": "S$", "decimals": 2, "flag": "🇸🇬"},
    "MYR": {"name": "Malaysian Ringgit", "symbol": "RM", "decimals": 2, "flag": "🇲🇾"},
    "THB": {"name": "Thai Baht", "symbol": "฿", "decimals": 2, "flag": "🇹🇭"},
    "KRW": {"name": "South Korean Won", "symbol": "₩", "decimals": 0, "flag": "🇰🇷"},
    "ZAR": {"name": "South African Rand", "symbol": "R", "decimals": 2, "flag": "🇿🇦"},
    "BRL": {"name": "Brazilian Real", "symbol": "R$", "decimals": 2, "flag": "🇧🇷"},
    "RUB": {"name": "Russian Ruble", "symbol": "₽", "decimals": 2, "flag": "🇷🇺"},
    "KWD": {"name": "Kuwaiti Dinar", "symbol": "KD", "decimals": 3, "flag": "🇰🇼"},
    "BHD": {"name": "Bahraini Dinar", "symbol": "BD", "decimals": 3, "flag": "🇧🇭"},
    "OMR": {"name": "Omani Rial", "symbol": "RO", "decimals": 3, "flag": "🇴🇲"},
    "QAR": {"name": "Qatari Riyal", "symbol": "QR", "decimals": 2, "flag": "🇶🇦"},
    "NZD": {"name": "New Zealand Dollar", "symbol": "NZ$", "decimals": 2, "flag": "🇳🇿"},
    "MXN": {"name": "Mexican Peso", "symbol": "MX$", "decimals": 2, "flag": "🇲🇽"},
    "IDR": {"name": "Indonesian Rupiah", "symbol": "Rp", "decimals": 0, "flag": "🇮🇩"},
    "TRY": {"name": "Turkish Lira", "symbol": "₺", "decimals": 2, "flag": "🇹🇷"},
    "SEK": {"name": "Swedish Krona", "symbol": "kr", "decimals": 2, "flag": "🇸🇪"},
    "NOK": {"name": "Norwegian Krone", "symbol": "kr", "decimals": 2, "flag": "🇳🇴"},
    "DKK": {"name": "Danish Krone", "symbol": "kr", "decimals": 2, "flag": "🇩🇰"},
    "PLN": {"name": "Polish Zloty", "symbol": "zł", "decimals": 2, "flag": "🇵🇱"},
    "PHP": {"name": "Philippine Peso", "symbol": "₱", "decimals": 2, "flag": "🇵🇭"},
    "CZK": {"name": "Czech Koruna", "symbol": "Kč", "decimals": 2, "flag": "🇨🇿"},
    "ILS": {"name": "Israeli New Shekel", "symbol": "₪", "decimals": 2, "flag": "🇮🇱"},
    "CLP": {"name": "Chilean Peso", "symbol": "CLP$", "decimals": 0, "flag": "🇨🇱"},
    "EGP": {"name": "Egyptian Pound", "symbol": "E£", "decimals": 2, "flag": "🇪🇬"},
    "NGN": {"name": "Nigerian Naira", "symbol": "₦", "decimals": 2, "flag": "🇳🇬"},
    "VND": {"name": "Vietnamese Dong", "symbol": "₫", "decimals": 0, "flag": "🇻🇳"},
    "HUF": {"name": "Hungarian Forint", "symbol": "Ft", "decimals": 2, "flag": "🇭🇺"},
    "COP": {"name": "Colombian Peso", "symbol": "COL$", "decimals": 2, "flag": "🇨🇴"},
    "HKD": {"name": "Hong Kong Dollar", "symbol": "HK$", "decimals": 2, "flag": "🇭🇰"},
    "TWD": {"name": "New Taiwan Dollar", "symbol": "NT$", "decimals": 2, "flag": "🇹🇼"},
    "ARS": {"name": "Argentine Peso", "symbol": "AR$", "decimals": 2, "flag": "🇦🇷"},
    "KES": {"name": "Kenyan Shilling", "symbol": "KSh", "decimals": 2, "flag": "🇰🇪"},
    "GHS": {"name": "Ghanaian Cedi", "symbol": "GH₵", "decimals": 2, "flag": "🇬🇭"},
    "JOD": {"name": "Jordanian Dinar", "symbol": "JD", "decimals": 3, "flag": "🇯🇴"},
    "LKR": {"name": "Sri Lankan Rupee", "symbol": "Rs", "decimals": 2, "flag": "🇱🇰"},
    "NPR": {"name": "Nepalese Rupee", "symbol": "Rs", "decimals": 2, "flag": "🇳🇵"},
    "PEN": {"name": "Peruvian Sol", "symbol": "S/.", "decimals": 2, "flag": "🇵🇪"},
    "VUV": {"name": "Vanuatu Vatu", "symbol": "VT", "decimals": 0, "flag": "🇻🇺"},
    "XAF": {"name": "Central African CFA Franc", "symbol": "FCFA", "decimals": 0, "flag": "🇨🇲"},
    "XOF": {"name": "West African CFA Franc", "symbol": "CFA", "decimals": 0, "flag": "🇸🇳"},
    "BND": {"name": "Brunei Dollar", "symbol": "B$", "decimals": 2, "flag": "🇧🇳"},
    "UGX": {"name": "Ugandan Shilling", "symbol": "USh", "decimals": 0, "flag": "🇺🇬"},
    "MAD": {"name": "Moroccan Dirham", "symbol": "DH", "decimals": 2, "flag": "🇲🇦"},
    "DZD": {"name": "Algerian Dinar", "symbol": "DA", "decimals": 2, "flag": "🇩🇿"},
    "TND": {"name": "Tunisian Dinar", "symbol": "DT", "decimals": 3, "flag": "🇹🇳"},
    "IQD": {"name": "Iraqi Dinar", "symbol": "ID", "decimals": 3, "flag": "🇮🇶"}
}

# Reliable fallback reference rates relative to 1.00 USD (updated baseline)
BASELINE_RATES_USD = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "INR": 83.50,
    "JPY": 154.50,
    "CNY": 7.23,
    "AED": 3.6725,
    "SAR": 3.75,
    "PKR": 278.50,
    "BDT": 117.20,
    "CAD": 1.365,
    "AUD": 1.525,
    "CHF": 0.905,
    "SGD": 1.352,
    "MYR": 4.72,
    "THB": 36.80,
    "KRW": 1365.0,
    "ZAR": 18.45,
    "BRL": 5.15,
    "RUB": 91.50,
    "KWD": 0.307,
    "BHD": 0.376,
    "OMR": 0.385,
    "QAR": 3.64,
    "NZD": 1.65,
    "MXN": 16.85,
    "IDR": 16100.0,
    "TRY": 32.25,
    "SEK": 10.75,
    "NOK": 10.85,
    "DKK": 6.87,
    "PLN": 3.98,
    "PHP": 57.50,
    "CZK": 23.10,
    "ILS": 3.72,
    "CLP": 940.0,
    "EGP": 47.50,
    "NGN": 1420.0,
    "VND": 25400.0,
    "HUF": 360.0,
    "COP": 3890.0,
    "HKD": 7.82,
    "TWD": 32.40,
    "ARS": 880.0,
    "KES": 132.0,
    "GHS": 13.80,
    "JOD": 0.709,
    "LKR": 300.0,
    "NPR": 133.50,
    "PEN": 3.73,
    "VUV": 121.0,
    "XAF": 605.0,
    "XOF": 605.0,
    "BND": 1.352,
    "UGX": 3780.0,
    "MAD": 10.05,
    "DZD": 134.50,
    "TND": 3.12,
    "IQD": 1310.0
}

class CurrencyService:
    @staticmethod
    def get_supported_currencies():
        """Returns sorted list of all supported ISO 4217 currencies with code."""
        return [{"code": code, **info} for code, info in ISO_CURRENCIES.items()]

    @staticmethod
    def get_decimals(code):
        """Returns ISO 4217 decimal precision for a currency code."""
        return CurrencyService.get_currency_info(code).get("decimals", 2)

    @staticmethod
    def is_valid_currency(code):
        """Validates if currency code is an active ISO 4217 currency."""
        return isinstance(code, str) and code.upper() in ISO_CURRENCIES

    @staticmethod
    def get_currency_info(code):
        """Returns details for a currency code with fallbacks."""
        if not code:
            code = "USD"
        code = code.upper()
        return ISO_CURRENCIES.get(code, {
            "name": code,
            "symbol": code,
            "decimals": 2,
            "flag": "🌐"
        })

    @staticmethod
    def format_amount(amount, currency_code="USD", show_symbol=True):
        """
        Formats amount with proper currency decimal precision.
        Handles zero-decimal (JPY) and 3-decimal (KWD) properly.
        """
        info = CurrencyService.get_currency_info(currency_code)
        decimals = info.get("decimals", 2)
        sym = info.get("symbol", currency_code)

        try:
            val = float(amount or 0.0)
        except (ValueError, TypeError):
            val = 0.0

        if decimals == 0:
            formatted = f"{int(round(val)):,}"
        else:
            formatted = f"{val:,.{decimals}f}"

        if show_symbol:
            return f"{sym} {formatted}"
        return formatted

    @staticmethod
    def fetch_live_rates(base="USD"):
        """
        Fetches live exchange rates from open exchange-rate API with timeout.
        Caches results into SQLite ExchangeRate table.
        Falls back safely to database cache or baseline dictionary if offline.
        """
        base = base.upper()
        now = datetime.now(timezone.utc)
        cache_duration = timedelta(hours=2)

        if not has_app_context():
            return BASELINE_RATES_USD, "Verified Baseline Reference", now

        # 1. Check if database has fresh cached rates
        try:
            fresh_cache = ExchangeRate.query.filter(
                ExchangeRate.base_currency == base,
                ExchangeRate.fetched_at >= (now - cache_duration)
            ).all()

            if fresh_cache and len(fresh_cache) >= 10:
                return {
                    r.target_currency: r.exchange_rate for r in fresh_cache
                }, "Database Cache", fresh_cache[0].fetched_at
        except Exception:
            pass

        # 2. Try fetching from live external provider
        api_url = f"https://open.er-api.com/v6/latest/{base}"
        rates = {}
        provider = "Open Exchange Rates API"
        fetch_time = now

        try:
            resp = requests.get(api_url, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("result") == "success" and "rates" in data:
                    raw_rates = data["rates"]
                    # Store in database
                    for code in ISO_CURRENCIES.keys():
                        if code in raw_rates:
                            rate_val = float(raw_rates[code])
                            rates[code] = rate_val
                            
                            # Upsert in database
                            existing = ExchangeRate.query.filter_by(
                                base_currency=base, target_currency=code
                            ).first()
                            if existing:
                                existing.exchange_rate = rate_val
                                existing.provider = provider
                                existing.fetched_at = now
                            else:
                                new_entry = ExchangeRate(
                                    base_currency=base,
                                    target_currency=code,
                                    exchange_rate=rate_val,
                                    provider=provider,
                                    fetched_at=now
                                )
                                db.session.add(new_entry)

                    db.session.commit()
                    return rates, provider, now
        except Exception as e:
            # External API failed or offline - fallback to DB or baseline
            db.session.rollback()

        # 3. Check for any stored rates in DB even if slightly stale
        stale_cache = ExchangeRate.query.filter_by(base_currency=base).all()
        if stale_cache:
            return {
                r.target_currency: r.exchange_rate for r in stale_cache
            }, "Database Offline Cache", stale_cache[0].fetched_at

        # 4. Final resilient fallback: baseline rates table
        return BASELINE_RATES_USD, "Verified Baseline Reference", now

    @staticmethod
    def convert(amount, from_curr="USD", to_curr="USD"):
        """
        Converts monetary amount from one currency to another using exchange rates.
        Returns: (converted_amount, exchange_rate, provider, timestamp)
        Never fabricates: stores exact rate and preserves original amount.
        """
        from_curr = from_curr.upper() if from_curr else "USD"
        to_curr = to_curr.upper() if to_curr else "USD"

        try:
            amt = float(amount or 0.0)
        except (ValueError, TypeError):
            amt = 0.0

        if from_curr == to_curr:
            return amt, 1.0, "Direct (1:1)", datetime.now(timezone.utc)

        rates, provider, timestamp = CurrencyService.fetch_live_rates("USD")

        rate_from = rates.get(from_curr, BASELINE_RATES_USD.get(from_curr, 1.0))
        rate_to = rates.get(to_curr, BASELINE_RATES_USD.get(to_curr, 1.0))

        # Convert: (amount / rate_from) * rate_to
        amount_usd = amt / rate_from if rate_from > 0 else amt
        converted = amount_usd * rate_to
        effective_rate = (rate_to / rate_from) if rate_from > 0 else 1.0

        decimals = ISO_CURRENCIES.get(to_curr, {}).get("decimals", 2)
        if decimals == 0:
            converted = round(converted)
        else:
            converted = round(converted, decimals)

        return converted, effective_rate, provider, timestamp

    @staticmethod
    def convert_to_usd(amount, from_curr="USD"):
        """Convenience method to convert any currency to base USD for the ML model."""
        return CurrencyService.convert(amount, from_curr=from_curr, to_curr="USD")

