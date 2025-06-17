#!/usr/bin/env python3
"""
Test script for completion scenario fixes.
This script tests the new early/late completion logic.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'custom_components', 'todo_magic'))

from datetime import datetime, timedelta
from __init__ import parse_repeat_pattern, schedule_next_occurrence

def test_completion_scenarios():
    """Test early, on-time, and late completion scenarios."""
    print("Todo Magic - Completion Scenario Tests")
    print("=" * 60)
    
    # Test scenarios for different pattern types
    scenarios = [
        {
            'name': 'Daily pattern [6d] - early completion',
            'pattern': '[6d]',
            'original_due': datetime(2025, 1, 15),  # Wednesday
            'completion_date': datetime(2025, 1, 14),  # Tuesday (early)
            'expected': datetime(2025, 1, 20),  # 6 days from completion
        },
        {
            'name': 'Daily pattern [6d] - late completion',
            'pattern': '[6d]',
            'original_due': datetime(2025, 1, 15),  # Wednesday
            'completion_date': datetime(2025, 1, 16),  # Thursday (late)
            'expected': datetime(2025, 1, 22),  # 6 days from completion
        },
        {
            'name': 'Weekly advanced [w-wf] - early completion (Tuesday before Wednesday due)',
            'pattern': '[w-wf]',
            'original_due': datetime(2025, 1, 15),  # Wednesday
            'completion_date': datetime(2025, 1, 14),  # Tuesday (early)
            'expected': datetime(2025, 1, 17),  # Friday (next in pattern after Wednesday)
        },
        {
            'name': 'Weekly advanced [w-wf] - late completion (Thursday after Wednesday due)',
            'pattern': '[w-wf]',
            'original_due': datetime(2025, 1, 15),  # Wednesday
            'completion_date': datetime(2025, 1, 16),  # Thursday (late)
            'expected': datetime(2025, 1, 17),  # Friday (next in pattern after Thursday)
        },
        {
            'name': 'Weekly advanced [w-wf] - complete on Friday, should go to next Monday',
            'pattern': '[w-wf]',
            'original_due': datetime(2025, 1, 17),  # Friday
            'completion_date': datetime(2025, 1, 17),  # Friday (on time)
            'expected': datetime(2025, 1, 22),  # Monday (next cycle)
        },
        {
            'name': 'Monthly pattern [m] - early completion (June for July due)',
            'pattern': '[m]',
            'original_due': datetime(2025, 7, 15),  # July 15
            'completion_date': datetime(2025, 6, 20),  # June 20 (early)
            'expected': datetime(2025, 8, 31, 23, 59),  # August 31 @ 23:59
        },
        {
            'name': 'Monthly pattern [m] - late completion (September for July due)',
            'pattern': '[m]',
            'original_due': datetime(2025, 7, 15),  # July 15
            'completion_date': datetime(2025, 9, 10),  # September 10 (late)
            'expected': datetime(2025, 10, 31, 23, 59),  # October 31 @ 23:59
        },
        {
            'name': 'Monthly pattern [2m] - late completion',
            'pattern': '[2m]',
            'original_due': datetime(2025, 7, 15),  # July 15
            'completion_date': datetime(2025, 10, 10),  # October 10 (late)
            'expected': datetime(2025, 12, 31, 23, 59),  # December 31 @ 23:59
        },
    ]
    
    for scenario in scenarios:
        print(f"\nTesting: {scenario['name']}")
        print(f"  Pattern: {scenario['pattern']}")
        print(f"  Original due: {scenario['original_due'].strftime('%A %Y-%m-%d')}")
        print(f"  Completed on: {scenario['completion_date'].strftime('%A %Y-%m-%d')}")
        print(f"  Expected next: {scenario['expected'].strftime('%A %Y-%m-%d %H:%M')}")
        
        # Parse the repeat pattern
        repeat_info = parse_repeat_pattern(scenario['pattern'])
        if not repeat_info:
            print(f"  ❌ Could not parse pattern {scenario['pattern']}")
            continue
        
        # Calculate next occurrence
        next_date = schedule_next_occurrence(
            scenario['completion_date'], 
            scenario['original_due'], 
            repeat_info
        )
        
        if next_date:
            print(f"  Calculated: {next_date.strftime('%A %Y-%m-%d %H:%M')}")
            if next_date.replace(microsecond=0) == scenario['expected'].replace(microsecond=0):
                print("  ✅ PASS")
            else:
                print("  ❌ FAIL")
                print(f"     Expected: {scenario['expected']}")
                print(f"     Got:      {next_date}")
        else:
            print("  ❌ Could not calculate next occurrence")
    
    print("\n" + "=" * 60)
    print("Completion scenario tests completed!")

def test_edge_cases():
    """Test edge cases for the completion logic."""
    print("\nEdge Case Tests")
    print("=" * 30)
    
    # Test cross-year monthly patterns
    print("\nTesting cross-year monthly pattern:")
    pattern = '[m]'
    repeat_info = parse_repeat_pattern(pattern)
    
    # December to January
    original_due = datetime(2025, 12, 15)
    completion_date = datetime(2025, 12, 15)  # On time
    next_date = schedule_next_occurrence(completion_date, original_due, repeat_info)
    print(f"  December due, completed on time -> {next_date.strftime('%Y-%m-%d %H:%M')}")
    
    # Test weekend handling for weekly patterns
    print("\nTesting weekend edge cases:")
    pattern = '[w-mwf]'
    repeat_info = parse_repeat_pattern(pattern)
    
    # Complete on Saturday, should go to Monday
    original_due = datetime(2025, 1, 17)  # Friday
    completion_date = datetime(2025, 1, 18)  # Saturday (late)
    next_date = schedule_next_occurrence(completion_date, original_due, repeat_info)
    print(f"  [w-mwf] Friday due, completed Saturday -> {next_date.strftime('%A %Y-%m-%d')}")
    
    # Complete on Sunday, should go to Monday
    completion_date = datetime(2025, 1, 19)  # Sunday (late)
    next_date = schedule_next_occurrence(completion_date, original_due, repeat_info)
    print(f"  [w-mwf] Friday due, completed Sunday -> {next_date.strftime('%A %Y-%m-%d')}")

if __name__ == "__main__":
    test_completion_scenarios()
    test_edge_cases()