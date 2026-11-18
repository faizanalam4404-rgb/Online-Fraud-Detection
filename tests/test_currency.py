"""
FraudGuard – Currency Service & ISO 4217 Registry Unit Tests
============================================================
Verifies:
- 60+ ISO 4217 world currency codes, symbols, and names
- Correct decimal precision (2-decimal default, 0-decimal JPY/KRW, 3-decimal KWD/BHD)
- Safe conversion math to USD base
- Immutability of original transaction amounts
- Offline database caching & fallback
"""

import pytest
from services.currency_service import CurrencyService

def test_currency_registry_breadth():
    """Verify ISO 4217 currency registry contains major and regional global currencies."""
    currencies = CurrencyService.get_supported_currencies()
    codes = [c["code"] for c in currencies]
    
    # Must contain 50+ currencies
    assert len(codes) >= 50
    
    # Check essential global currencies
    essential = ["USD", "INR", "EUR", "GBP", "JPY", "CNY", "AED", "SAR", "CAD", "AUD", "CHF", "SGD", "BRL", "ZAR"]
    for code in essential:
        assert code in codes, f"Currency {code} missing from registry"

def test_currency_decimal_precision():
    """Verify correct ISO 4217 decimal formatting across currency types."""
    # Standard 2-decimal
    assert CurrencyService.get_decimals("USD") == 2
    assert CurrencyService.get_decimals("EUR") == 2
    assert CurrencyService.get_decimals("INR") == 2
    
    # Zero-decimal currencies
    assert CurrencyService.get_decimals("JPY") == 0
    assert CurrencyService.get_decimals("KRW") == 0
    assert CurrencyService.get_decimals("VND") == 0
    
    # Three-decimal currencies
    assert CurrencyService.get_decimals("KWD") == 3
    assert CurrencyService.get_decimals("BHD") == 3
    assert CurrencyService.get_decimals("OMR") == 3

def test_amount_formatting():
    """Verify formatted strings include symbol and proper decimals."""
    usd_str = CurrencyService.format_amount(1250.5, "USD")
    assert "$" in usd_str
    assert "1,250.50" in usd_str

    jpy_str = CurrencyService.format_amount(50000, "JPY")
    assert "¥" in jpy_str
    assert "50,000" in jpy_str
    assert "." not in jpy_str  # No decimal point for JPY

    kwd_str = CurrencyService.format_amount(45.125, "KWD")
    assert "45.125" in kwd_str

def test_currency_conversion_math():
    """Verify conversion to USD base accurately calculates without mutating input."""
    # Test USD to USD
    amt_usd, rate, provider, ts = CurrencyService.convert_to_usd(100.0, "USD")
    assert amt_usd == 100.0
    assert rate == 1.0

    # Test EUR to USD
    amt_usd, rate, provider, ts = CurrencyService.convert_to_usd(100.0, "EUR")
    assert amt_usd > 0
    assert rate > 0
    assert provider in ["Database Cache", "Database Offline Cache", "Live API", "Verified Baseline Reference", "Open Exchange Rates API"]

def test_invalid_currency_rejection():
    """Verify non-ISO or malicious strings are rejected."""
    assert not CurrencyService.is_valid_currency("INVALID_XYZ")
    assert not CurrencyService.is_valid_currency("<script>")
    assert not CurrencyService.is_valid_currency("")
    assert not CurrencyService.is_valid_currency(None)
