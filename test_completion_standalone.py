#!/usr/bin/env python3
"""
Standalone test for completion scenario fixes.
Tests the new early/late completion logic without Home Assistant dependencies.
"""

from datetime import datetime, timedelta
import re
from typing import Any

def parse_repeat_pattern(pattern_string: str) -> dict[str, Any] | None:
    """Parse repeat patterns like [d], [w], [m], [y], [w-mwf], etc."""
    if not pattern_string.startswith("[") or not pattern_string.endswith("]"):
        return None
    
    # Remove brackets
    pattern = pattern_string[1:-1].lower().strip()
    
    if not pattern:
        return None
    
    # Simple patterns: [d], [w], [m], [y]
    if pattern in ('d', 'w', 'm', 'y'):
        return {
            'type': 'simple',
            'unit': pattern,
            'interval': 1
        }
    
    # Interval patterns: [2d], [3w], [2m], [1y]
    interval_match = re.match(r'^(\d+)([dwmy])$', pattern)
    if interval_match:
        interval = int(interval_match.group(1))
        unit = interval_match.group(2)
        return {
            'type': 'simple',
            'unit': unit,
            'interval': interval
        }
    
    # Advanced weekly patterns: [w-mwf], [2w-mtf], etc.
    weekly_match = re.match(r'^(?:(\d+)w|w)-([mtwrfsu]+)$', pattern)
    if weekly_match:
        interval = int(weekly_match.group(1)) if weekly_match.group(1) else 1
        day_string = weekly_match.group(2)
        
        # Convert day string to list of day abbreviations
        day_mapping = {
            'm': 'mon', 't': 'tue', 'w': 'wed', 'r': 'thu', 
            'f': 'fri', 's': 'sat', 'u': 'sun'
        }
        
        days = []
        for char in day_string:
            if char in day_mapping:
                days.append(day_mapping[char])
        
        if days:
            return {
                'type': 'advanced',
                'unit': 'w',
                'interval': interval,
                'days': days
            }
    
    # Special case: direct day patterns like [mwf] without w-
    if re.match(r'^[mtwrfsu]+$', pattern):
        day_mapping = {
            'm': 'mon', 't': 'tue', 'w': 'wed', 'r': 'thu', 
            'f': 'fri', 's': 'sat', 'u': 'sun'
        }
        
        days = []
        for char in pattern:
            if char in day_mapping:
                days.append(day_mapping[char])
        
        if days:
            return {
                'type': 'advanced',
                'unit': 'w',
                'interval': 1,
                'days': days
            }
    
    return None


def schedule_next_occurrence(completion_date: datetime, original_due_date: datetime, repeat_info: dict[str, Any]) -> datetime | None:
    """Calculate the next occurrence date based on repeat pattern and completion timing."""
    if not repeat_info or repeat_info['type'] not in ('simple', 'advanced'):
        return None
    
    unit = repeat_info['unit']
    interval = repeat_info.get('interval', 1)
    
    # Determine if completed early, on-time, or late
    completion_date_only = completion_date.replace(hour=0, minute=0, second=0, microsecond=0)
    original_due_date_only = original_due_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if repeat_info['type'] == 'simple':
        if unit == 'd':
            # Daily patterns: always calculate from completion date
            return completion_date_only + timedelta(days=interval)
        elif unit == 'w':
            # Weekly patterns: calculate from completion date
            return completion_date_only + timedelta(weeks=interval)
        elif unit == 'm':
            # Monthly patterns: calculate based on completion timing
            if completion_date_only <= original_due_date_only:
                # Early or on-time: next month from original due date
                target_month = original_due_date_only.month + interval
                target_year = original_due_date_only.year
                while target_month > 12:
                    target_month -= 12
                    target_year += 1
            else:
                # Late: next month from completion date
                target_month = completion_date_only.month + interval
                target_year = completion_date_only.year
                while target_month > 12:
                    target_month -= 12
                    target_year += 1
            
            # Set to end of target month at 23:59
            if target_month == 12:
                next_month_start = datetime(target_year + 1, 1, 1)
            else:
                next_month_start = datetime(target_year, target_month + 1, 1)
            end_of_month = next_month_start - timedelta(days=1)
            return end_of_month.replace(hour=23, minute=59, second=0, microsecond=0)
        elif unit == 'y':
            # Yearly patterns: calculate from original due date if early/on-time, completion if late
            if completion_date_only <= original_due_date_only:
                # Early or on-time
                return original_due_date_only.replace(year=original_due_date_only.year + interval)
            else:
                # Late
                return completion_date_only.replace(year=completion_date_only.year + interval)
    
    elif repeat_info['type'] == 'advanced' and unit == 'w':
        # Advanced weekly patterns with specific days
        days = repeat_info.get('days', [])
        if not days:
            return None
        
        # Map day names to weekday numbers (Monday=0, Sunday=6)
        day_to_num = {
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3,
            'fri': 4, 'sat': 5, 'sun': 6
        }
        
        target_weekdays = [day_to_num[day] for day in days if day in day_to_num]
        if not target_weekdays:
            return None
        
        target_weekdays.sort()
        completion_weekday = completion_date_only.weekday()
        original_due_weekday = original_due_date_only.weekday()
        
        if completion_date_only <= original_due_date_only:
            # Early or on-time completion
            # Find next day in the pattern sequence after the original due day
            next_weekday = None
            for weekday in target_weekdays:
                if weekday > original_due_weekday:
                    next_weekday = weekday
                    break
            
            if next_weekday is not None:
                # Next occurrence is later this week
                days_ahead = next_weekday - completion_weekday
                if days_ahead <= 0:
                    # If that day has already passed this week, go to next cycle
                    days_ahead += 7 + (interval - 1) * 7
                return completion_date_only + timedelta(days=days_ahead)
            else:
                # Next occurrence is first day of next cycle
                days_to_next_cycle = 7 - completion_weekday + target_weekdays[0] + (interval - 1) * 7
                return completion_date_only + timedelta(days=days_to_next_cycle)
        else:
            # Late completion
            # Find next day in the pattern sequence after completion day
            next_weekday = None
            for weekday in target_weekdays:
                if weekday > completion_weekday:
                    next_weekday = weekday
                    break
            
            if next_weekday is not None:
                # Next occurrence is later this week
                days_ahead = next_weekday - completion_weekday
                return completion_date_only + timedelta(days=days_ahead)
            else:
                # Next occurrence is first day of next cycle
                days_to_next_cycle = 7 - completion_weekday + target_weekdays[0] + (interval - 1) * 7
                return completion_date_only + timedelta(days=days_to_next_cycle)
    
    return None


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
            'name': 'Weekly advanced [mwf] - complete on Monday, should go to Wednesday',
            'pattern': '[mwf]',
            'original_due': datetime(2025, 1, 13),  # Monday
            'completion_date': datetime(2025, 1, 13),  # Monday (on time)
            'expected': datetime(2025, 1, 15),  # Wednesday (next in pattern)
        },
        {
            'name': 'Weekly advanced [mwf] - complete on Wednesday, should go to Friday',
            'pattern': '[mwf]',
            'original_due': datetime(2025, 1, 15),  # Wednesday
            'completion_date': datetime(2025, 1, 15),  # Wednesday (on time)
            'expected': datetime(2025, 1, 17),  # Friday (next in pattern)
        },
        {
            'name': 'Weekly advanced [mwf] - complete on Friday, should go to next Monday',
            'pattern': '[mwf]',
            'original_due': datetime(2025, 1, 17),  # Friday
            'completion_date': datetime(2025, 1, 17),  # Friday (on time)
            'expected': datetime(2025, 1, 20),  # Monday (next cycle)
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
    
    passed = 0
    total = len(scenarios)
    
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
                passed += 1
            else:
                print("  ❌ FAIL")
                print(f"     Expected: {scenario['expected']}")
                print(f"     Got:      {next_date}")
        else:
            print("  ❌ Could not calculate next occurrence")
    
    print(f"\n" + "=" * 60)
    print(f"Completion scenario tests completed! {passed}/{total} passed")
    return passed == total

if __name__ == "__main__":
    test_completion_scenarios()