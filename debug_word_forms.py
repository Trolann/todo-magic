#!/usr/bin/env python3
"""Debug script to test word form parsing."""

import re
from datetime import datetime, timedelta

def test_current_pattern():
    test_cases = [
        "5d",
        "5 d", 
        "5day",
        "5 day",
        "5 days",
        "5days",
        "2w",
        "2 weeks",
        "2weeks"
    ]
    
    # Fixed pattern - longer forms first
    current_pattern = r'(\d+)\s*(days?|weeks?|months?|years?|[dwmy])'
    
    print("Testing current regex pattern:")
    print(f"Pattern: {current_pattern}")
    print("=" * 60)
    
    for test_case in test_cases:
        match = re.search(current_pattern, test_case.lower())
        if match:
            print(f"'{test_case}' -> groups: {match.groups()}")
            amount = int(match.group(1))
            unit = match.group(2)
            print(f"  Amount: {amount}, Unit: '{unit}'")
            
            # Test the unit matching logic
            if unit in ('d', 'day', 'days'):
                print(f"  -> Would parse as {amount} days")
            elif unit in ('w', 'week', 'weeks'):
                print(f"  -> Would parse as {amount} weeks")
            elif unit in ('m', 'month', 'months'):
                print(f"  -> Would parse as {amount} months")
            elif unit in ('y', 'year', 'years'):
                print(f"  -> Would parse as {amount} years")
            else:
                print(f"  -> ERROR: Unit '{unit}' not recognized!")
        else:
            print(f"'{test_case}' -> NO MATCH")
        print()

if __name__ == "__main__":
    test_current_pattern()