"""Tests for the heuristic € extraction (council.money)."""
from council.money import extract_amounts, largest_amount


def test_plain_amount():
    assert largest_amount("Kosten von 250.000 € werden bewilligt.") == 250_000


def test_decimal_with_thousands():
    # The grouped form must keep its decimals (regression: matched only "12.500").
    assert largest_amount("Betrag: 12.500,50 EUR") == 12_500.50


def test_plain_decimal():
    assert largest_amount("Zuschuss von 1500,00 Euro") == 1_500.0


def test_scaled_millions():
    assert largest_amount("Investition von 1,2 Mio. €") == 1_200_000
    assert largest_amount("rund 3 Millionen Euro") == 3_000_000


def test_scaled_billions():
    assert largest_amount("Haushaltsvolumen 1,5 Mrd. €") == 1_500_000_000


def test_largest_wins():
    assert largest_amount("200.000 € Förderung bei 500.000 € Gesamtkosten") == 500_000


def test_no_currency_token_ignored():
    # Bare numbers (years, counts) must not be picked up as money.
    assert extract_amounts("Im Jahr 2024 gab es 15 Stimmen dafür.") == []
    assert largest_amount("Beschluss ohne Betrag") is None


def test_sanity_ceiling():
    # Absurd values (parse artefacts) are dropped.
    assert largest_amount("99.999.999.999 €") is None


def test_empty():
    assert extract_amounts("") == []
    assert largest_amount(None) is None
