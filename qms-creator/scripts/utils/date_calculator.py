#!/usr/bin/env python3
"""
Date Calculator Utility for Cannabis EU GMP QMS Creator
Handles date arithmetic and formatting for placeholder replacement
"""

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import re
from typing import Optional


class DateCalculator:
    """Utility class for date calculations and formatting."""

    @staticmethod
    def today() -> str:
        """Return today's date in YYYY-MM-DD format."""
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def format_date(date_obj: datetime, format_str: str = "%Y-%m-%d") -> str:
        """Format a datetime object to string."""
        return date_obj.strftime(format_str)

    @staticmethod
    def parse_date(date_str: str) -> Optional[datetime]:
        """
        Parse a date string to datetime object.
        Supports formats: YYYY-MM-DD, DD/MM/YYYY, DD.MM.YYYY
        """
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%Y/%m/%d",
            "%d-%m-%Y"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    @staticmethod
    def add_days(date_str: str, days: int) -> str:
        """Add days to a date string."""
        date_obj = DateCalculator.parse_date(date_str)
        if date_obj:
            new_date = date_obj + timedelta(days=days)
            return DateCalculator.format_date(new_date)
        return date_str

    @staticmethod
    def add_months(date_str: str, months: int) -> str:
        """Add months to a date string."""
        date_obj = DateCalculator.parse_date(date_str)
        if date_obj:
            new_date = date_obj + relativedelta(months=months)
            return DateCalculator.format_date(new_date)
        return date_str

    @staticmethod
    def add_years(date_str: str, years: int) -> str:
        """Add years to a date string."""
        date_obj = DateCalculator.parse_date(date_str)
        if date_obj:
            new_date = date_obj + relativedelta(years=years)
            return DateCalculator.format_date(new_date)
        return date_str

    @staticmethod
    def calculate_date_expression(expression: str, base_date: Optional[str] = None) -> str:
        """
        Calculate date from expression like:
        - "today"
        - "today + 12 months"
        - "today + 1 year"
        - "2026-01-13 + 30 days"
        - "today + 2 years"

        Args:
            expression: Date expression string
            base_date: Optional base date (YYYY-MM-DD), defaults to today

        Returns:
            Calculated date in YYYY-MM-DD format
        """
        expression = expression.strip().lower()

        # Get base date
        if "today" in expression:
            base = datetime.now()
        elif base_date:
            base = DateCalculator.parse_date(base_date)
            if not base:
                return expression
        else:
            base = datetime.now()

        # Parse arithmetic operations
        # Pattern: (base_date) + NUMBER (days|months|years)
        pattern = r'[\+\-]\s*(\d+)\s*(day|days|month|months|year|years|week|weeks)'
        matches = re.findall(pattern, expression)

        result_date = base
        for match in matches:
            number = int(match[0])
            unit = match[1]

            # Determine if addition or subtraction
            if '-' in expression:
                number = -number

            if 'day' in unit:
                result_date += timedelta(days=number)
            elif 'week' in unit:
                result_date += timedelta(weeks=number)
            elif 'month' in unit:
                result_date += relativedelta(months=number)
            elif 'year' in unit:
                result_date += relativedelta(years=number)

        return DateCalculator.format_date(result_date)

    @staticmethod
    def is_date_expired(date_str: str) -> bool:
        """Check if a date has expired (is in the past)."""
        date_obj = DateCalculator.parse_date(date_str)
        if date_obj:
            return date_obj.date() < datetime.now().date()
        return False

    @staticmethod
    def days_until(date_str: str) -> Optional[int]:
        """Calculate days until a future date."""
        date_obj = DateCalculator.parse_date(date_str)
        if date_obj:
            delta = date_obj.date() - datetime.now().date()
            return delta.days
        return None

    @staticmethod
    def format_for_document(date_str: str, format_type: str = "standard") -> str:
        """
        Format date for document display.

        Args:
            date_str: Date string to format
            format_type: 'standard' (YYYY-MM-DD), 'long' (January 13, 2026),
                        'short' (13/01/2026), 'iso' (2026-01-13)

        Returns:
            Formatted date string
        """
        date_obj = DateCalculator.parse_date(date_str)
        if not date_obj:
            return date_str

        formats = {
            "standard": "%Y-%m-%d",
            "long": "%B %d, %Y",
            "short": "%d/%m/%Y",
            "iso": "%Y-%m-%d",
            "dot": "%d.%m.%Y",
            "us": "%m/%d/%Y"
        }

        format_str = formats.get(format_type, "%Y-%m-%d")
        return date_obj.strftime(format_str)


# Convenience functions
def today() -> str:
    """Get today's date in YYYY-MM-DD format."""
    return DateCalculator.today()


def add_months(date_str: str, months: int) -> str:
    """Add months to a date."""
    return DateCalculator.add_months(date_str, months)


def add_years(date_str: str, years: int) -> str:
    """Add years to a date."""
    return DateCalculator.add_years(date_str, years)


def calculate_date(expression: str, base_date: Optional[str] = None) -> str:
    """Calculate date from expression."""
    return DateCalculator.calculate_date_expression(expression, base_date)


if __name__ == "__main__":
    # Test date calculator
    print("Date Calculator Test")
    print("=" * 60)

    print(f"Today: {today()}")
    print(f"Today + 12 months: {calculate_date('today + 12 months')}")
    print(f"Today + 1 year: {calculate_date('today + 1 year')}")
    print(f"Today + 90 days: {calculate_date('today + 90 days')}")
    print(f"Today + 2 years: {calculate_date('today + 2 years')}")

    test_date = "2026-01-13"
    print(f"\nBase date: {test_date}")
    print(f"  + 6 months: {add_months(test_date, 6)}")
    print(f"  + 1 year: {add_years(test_date, 1)}")
    print(f"  + 30 days: {DateCalculator.add_days(test_date, 30)}")

    print(f"\nDays until 2026-12-31: {DateCalculator.days_until('2026-12-31')}")
    print(f"Is 2025-01-01 expired? {DateCalculator.is_date_expired('2025-01-01')}")
