#!/usr/bin/env python3
"""Debug script to test the problematic patterns."""

import re

def test_patterns():
    test_cases = [
        "wash dog: 5d",
        "wash dog in 5d", 
        "wash dog: in 5d",  # This should work but doesn't
        "wash dog in 5 days",  # This should work but doesn't
        "wash dog: 5 days",  # This should work but doesn't
        "wash dog in 5 day",  # This should work but doesn't
    ]
    
    # Current pattern
    current_pattern = r'\s*(in|:)\s+(today|tomorrow|\d+\s*(?:[dwmy]|days?|weeks?|months?|years?))'
    
    print("Testing current pattern:")
    print(f"Pattern: {current_pattern}")
    print("=" * 60)
    
    for test_case in test_cases:
        match = re.search(current_pattern, test_case.lower())
        if match:
            print(f"✅ '{test_case}' -> matched: {match.groups()}")
        else:
            print(f"❌ '{test_case}' -> no match")
    
    print("\n" + "=" * 60)
    print("Let's try a better pattern...")
    
    # Better pattern - handle ': in' separately
    better_pattern1 = r'\s*:\s*in\s+(today|tomorrow|\d+\s*(?:[dwmy]|days?|weeks?|months?|years?))'
    better_pattern2 = r'\s*(in|:)\s+(today|tomorrow|\d+\s*(?:[dwmy]|days?|weeks?|months?|years?))'
    
    print(f"Pattern 1 (for ': in'): {better_pattern1}")
    print(f"Pattern 2 (for 'in' or ':'): {better_pattern2}")
    print("-" * 60)
    
    for test_case in test_cases:
        # Try pattern 1 first (': in')
        match1 = re.search(better_pattern1, test_case.lower())
        match2 = re.search(better_pattern2, test_case.lower())
        
        if match1:
            print(f"✅ '{test_case}' -> Pattern 1 matched: {match1.groups()}")
        elif match2:
            print(f"✅ '{test_case}' -> Pattern 2 matched: {match2.groups()}")
        else:
            print(f"❌ '{test_case}' -> no match")

if __name__ == "__main__":
    test_patterns()