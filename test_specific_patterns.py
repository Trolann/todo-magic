#!/usr/bin/env python3
"""Test specific patterns mentioned by user."""

from datetime import datetime, timedelta
import re

def parse_natural_language_date(given_string: str) -> datetime | None:
    """Parse natural language date patterns like 'today', 'tomorrow', '5d', '2w', etc."""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Handle 'today' and 'tomorrow'
    if given_string.lower() == 'today':
        return today
    elif given_string.lower() == 'tomorrow':
        return today + timedelta(days=1)
    
    # Handle duration patterns with flexible spacing and word forms
    # Patterns: '5d', '5 d', '5day', '5 day', '5 days', '5days', etc.
    # Order matters: match longer forms first to avoid greedy matching of single letters
    duration_pattern = re.search(r'(\d+)\s*(days?|weeks?|months?|years?|[dwmy])', given_string.lower())
    if duration_pattern:
        amount = int(duration_pattern.group(1))
        unit = duration_pattern.group(2)
        
        if unit in ('d', 'day', 'days'):
            return today + timedelta(days=amount)
        elif unit in ('w', 'week', 'weeks'):
            return today + timedelta(weeks=amount)
        elif unit in ('m', 'month', 'months'):
            # Approximate month as 30 days
            return today + timedelta(days=amount * 30)
        elif unit in ('y', 'year', 'years'):
            # Approximate year as 365 days
            return today + timedelta(days=amount * 365)
    
    return None

def test_specific_patterns():
    """Test the specific patterns mentioned by the user."""
    print("Testing specific word form patterns:")
    print("=" * 50)
    
    specific_tests = [
        # User mentioned these should work
        "day",
        "days", 
        "week",
        "weeks",
        "month",
        "months",
        "year",
        "years",
        # With numbers
        "5 day",
        "5 days",
        "2 week", 
        "2 weeks",
        "1 month",
        "1 months", 
        "1 year",
        "3 years",
        # Compact forms (should still work)
        "5d",
        "2w", 
        "3m",
        "1y"
    ]
    
    for test in specific_tests:
        result = parse_natural_language_date(test)
        if result:
            print(f"✅ '{test}' -> {result.strftime('%Y-%m-%d')}")
        else:
            print(f"❌ '{test}' -> None")

if __name__ == "__main__":
    test_specific_patterns()