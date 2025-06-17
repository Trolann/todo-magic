#!/usr/bin/env python3
"""
Test the calculate_first_occurrence function
"""

from datetime import datetime, timedelta
import re
from typing import Any

def parse_repeat_pattern(pattern_string: str) -> dict[str, Any] | None:
    """Parse repeat patterns like [d], [w], [m], [y], [w-mwf], etc."""
    if not pattern_string.startswith("[") or not pattern_string.endswith("]"):
        return None
    
    pattern = pattern_string[1:-1].lower().strip()
    if not pattern:
        return None
    
    # Simple patterns: [d], [w], [m], [y]
    if pattern in ('d', 'w', 'm', 'y'):
        return {'type': 'simple', 'unit': pattern, 'interval': 1}
    
    # Interval patterns: [2d], [3w], [2m], [1y]
    interval_match = re.match(r'^(\d+)([dwmy])$', pattern)
    if interval_match:
        interval = int(interval_match.group(1))
        unit = interval_match.group(2)
        return {'type': 'simple', 'unit': unit, 'interval': interval}
    
    # Advanced weekly patterns: [w-mwf], [2w-mtf], etc.
    weekly_match = re.match(r'^(?:(\d+)w|w)-([mtwrfsu]+)$', pattern)
    if weekly_match:
        interval = int(weekly_match.group(1)) if weekly_match.group(1) else 1
        day_string = weekly_match.group(2)
        
        day_mapping = {'m': 'mon', 't': 'tue', 'w': 'wed', 'r': 'thu', 'f': 'fri', 's': 'sat', 'u': 'sun'}
        days = [day_mapping[char] for char in day_string if char in day_mapping]
        
        if days:
            return {'type': 'advanced', 'unit': 'w', 'interval': interval, 'days': days}
    
    # Special case: direct day patterns like [mwf] without w-
    if re.match(r'^[mtwrfsu]+$', pattern):
        day_mapping = {'m': 'mon', 't': 'tue', 'w': 'wed', 'r': 'thu', 'f': 'fri', 's': 'sat', 'u': 'sun'}
        days = [day_mapping[char] for char in pattern if char in day_mapping]
        
        if days:
            return {'type': 'advanced', 'unit': 'w', 'interval': 1, 'days': days}
    
    return None

def calculate_first_occurrence(today: datetime, repeat_info: dict[str, Any]) -> datetime | None:
    """Calculate the first occurrence date for a new recurring task."""
    if not repeat_info or repeat_info['type'] not in ('simple', 'advanced'):
        return None
    
    unit = repeat_info['unit']
    interval = repeat_info.get('interval', 1)
    
    if repeat_info['type'] == 'simple':
        if unit == 'd':
            return today
        elif unit == 'w':
            return today
        elif unit == 'm':
            return today
        elif unit == 'y':
            return today
    
    elif repeat_info['type'] == 'advanced' and unit == 'w':
        days = repeat_info.get('days', [])
        if not days:
            return None
        
        day_to_num = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        target_weekdays = [day_to_num[day] for day in days if day in day_to_num]
        if not target_weekdays:
            return None
        
        target_weekdays.sort()
        current_weekday = today.weekday()
        
        # Check if today is one of the target days
        if current_weekday in target_weekdays:
            return today
        
        # Find next occurrence day in the current week
        next_weekday = None
        for weekday in target_weekdays:
            if weekday > current_weekday:
                next_weekday = weekday
                break
        
        if next_weekday is not None:
            # Next occurrence is later this week
            days_ahead = next_weekday - current_weekday
            return today + timedelta(days=days_ahead)
        else:
            # Next occurrence is next week (first day of pattern)
            days_to_next_week = 7 - current_weekday + target_weekdays[0]
            return today + timedelta(days=days_to_next_week)
    
    return None

if __name__ == "__main__":
    # Test with various days for [mwf] pattern
    pattern = '[mwf]'
    repeat_info = parse_repeat_pattern(pattern)
    print(f"Pattern: {pattern} -> {repeat_info}")
    
    # Test for each day of the week
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    base_date = datetime(2025, 6, 16)  # This is a Monday
    
    print(f"\nTesting first occurrence for {pattern} pattern:")
    for i, day_name in enumerate(days):
        test_date = base_date + timedelta(days=i)
        first_occurrence = calculate_first_occurrence(test_date, repeat_info)
        print(f"  Created on {day_name}: Due {first_occurrence.strftime('%A %Y-%m-%d')}")