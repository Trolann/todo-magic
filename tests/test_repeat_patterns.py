#!/usr/bin/env python3
"""
Test script for repeat pattern parsing and recurring task logic.
This tests the new repeat pattern functionality without requiring Home Assistant.
"""

from datetime import datetime, timedelta
import re

def parse_repeat_pattern(pattern_string: str) -> dict | None:
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
        # m=mon, t=tue, w=wed, r=thu, f=fri, s=sat, u=sun
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
    
    return None


def schedule_next_occurrence(current_date: datetime, repeat_info: dict) -> datetime | None:
    """Calculate the next occurrence date based on repeat pattern."""
    if not repeat_info or repeat_info['type'] not in ('simple', 'advanced'):
        return None
    
    unit = repeat_info['unit']
    interval = repeat_info.get('interval', 1)
    
    if repeat_info['type'] == 'simple':
        if unit == 'd':
            return current_date + timedelta(days=interval)
        elif unit == 'w':
            return current_date + timedelta(weeks=interval)
        elif unit == 'm':
            # Approximate month calculation
            return current_date + timedelta(days=interval * 30)
        elif unit == 'y':
            # Approximate year calculation
            return current_date + timedelta(days=interval * 365)
    
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
        current_weekday = current_date.weekday()
        
        # Find next occurrence day in the current week
        next_weekday = None
        for weekday in target_weekdays:
            if weekday > current_weekday:
                next_weekday = weekday
                break
        
        if next_weekday is not None:
            # Next occurrence is later this week
            days_ahead = next_weekday - current_weekday
            return current_date + timedelta(days=days_ahead)
        else:
            # Next occurrence is in the next cycle
            # Go to the first day of next interval
            days_to_next_week = 7 - current_weekday + target_weekdays[0]
            weeks_to_add = interval - 1  # We already moved to next week
            return current_date + timedelta(days=days_to_next_week + (weeks_to_add * 7))
    
    return None


def test_repeat_pattern_parsing():
    """Test repeat pattern parsing."""
    print("Testing repeat pattern parsing:")
    print("=" * 50)
    
    test_cases = [
        # Simple patterns
        "[d]",      # Daily
        "[w]",      # Weekly  
        "[m]",      # Monthly
        "[y]",      # Yearly
        
        # Interval patterns
        "[2d]",     # Every 2 days
        "[3w]",     # Every 3 weeks
        "[2m]",     # Every 2 months
        "[1y]",     # Every year
        "[10d]",    # Every 10 days
        
        # Advanced weekly patterns
        "[w-mwf]",    # Weekly on Mon, Wed, Fri
        "[w-tr]",     # Weekly on Tue, Thu
        "[2w-mf]",    # Every 2 weeks on Mon, Fri
        "[w-s]",      # Weekly on Saturday
        "[3w-mtwr]",  # Every 3 weeks on Mon-Thu
        
        # Invalid patterns
        "[]",         # Empty
        "[x]",        # Invalid unit
        "[w-xyz]",    # Invalid days
        "[0d]",       # Zero interval
        "d",          # No brackets
        "[w-]",       # No days specified
    ]
    
    for pattern in test_cases:
        result = parse_repeat_pattern(pattern)
        if result:
            print(f"✅ '{pattern}' -> {result}")
        else:
            print(f"❌ '{pattern}' -> None")
    print()


def test_next_occurrence_calculation():
    """Test next occurrence calculation."""
    print("Testing next occurrence calculation:")
    print("=" * 50)
    
    # Use a fixed date for predictable testing (Monday, 2025-01-13)
    base_date = datetime(2025, 1, 13)  # Monday
    print(f"Base date: {base_date.strftime('%Y-%m-%d %A')}")
    print()
    
    test_cases = [
        # Simple patterns
        ("[d]", "Next day"),
        ("[2d]", "2 days later"),
        ("[w]", "1 week later"),
        ("[2w]", "2 weeks later"),
        ("[m]", "~1 month later"),
        ("[y]", "~1 year later"),
        
        # Advanced weekly patterns
        ("[w-t]", "Next Tuesday"),         # Tuesday (tomorrow)
        ("[w-f]", "Next Friday"),         # Friday (this week)
        ("[w-s]", "Next Saturday"),       # Saturday (this week)
        ("[w-u]", "Next Sunday"),         # Sunday (this week)
        ("[w-m]", "Next Monday"),         # Monday (next week)
        ("[w-mwf]", "Next Mon/Wed/Fri"),  # Wednesday (this week)
        ("[2w-t]", "Every 2 weeks on Tuesday"),
    ]
    
    for pattern, description in test_cases:
        repeat_info = parse_repeat_pattern(pattern)
        if repeat_info:
            next_date = schedule_next_occurrence(base_date, repeat_info)
            if next_date:
                days_diff = (next_date - base_date).days
                print(f"✅ {pattern} ({description}): {next_date.strftime('%Y-%m-%d %A')} (+{days_diff} days)")
            else:
                print(f"❌ {pattern}: Could not calculate next occurrence")
        else:
            print(f"❌ {pattern}: Invalid pattern")
    print()


def test_weekly_pattern_edge_cases():
    """Test edge cases for weekly patterns with specific days."""
    print("Testing weekly pattern edge cases:")
    print("=" * 50)
    
    # Test different starting days for [w-mwf] pattern
    pattern = "[w-mwf]"  # Monday, Wednesday, Friday
    repeat_info = parse_repeat_pattern(pattern)
    
    # Test from each day of the week
    days_of_week = [
        ("Monday", datetime(2025, 1, 13)),    # Monday
        ("Tuesday", datetime(2025, 1, 14)),   # Tuesday  
        ("Wednesday", datetime(2025, 1, 15)), # Wednesday
        ("Thursday", datetime(2025, 1, 16)),  # Thursday
        ("Friday", datetime(2025, 1, 17)),    # Friday
        ("Saturday", datetime(2025, 1, 18)),  # Saturday
        ("Sunday", datetime(2025, 1, 19)),    # Sunday
    ]
    
    print(f"Pattern: {pattern} (Mon, Wed, Fri)")
    for day_name, test_date in days_of_week:
        next_date = schedule_next_occurrence(test_date, repeat_info)
        if next_date:
            days_diff = (next_date - test_date).days
            print(f"  From {day_name}: {next_date.strftime('%A')} (+{days_diff} days)")
        else:
            print(f"  From {day_name}: Error calculating next occurrence")
    print()


def test_task_summary_reconstruction():
    """Test reconstructing task summaries with repeat patterns."""
    print("Testing task summary reconstruction:")
    print("=" * 50)
    
    test_cases = [
        # (original_summary, repeat_pattern, expected_reconstructed)
        ("Take vitamins", "[d]", "Take vitamins [d]"),
        ("Weekly team meeting", "[w]", "Weekly team meeting [w]"),
        ("Gym workout", "[w-mwf]", "Gym workout [w-mwf]"),
        ("Monthly report", "[m]", "Monthly report [m]"),
        ("Quarterly review", "[3m]", "Quarterly review [3m]"),
        ("Annual checkup", "[y]", "Annual checkup [y]"),
    ]
    
    for original, pattern, expected in test_cases:
        # Test the reconstruction logic
        repeat_info = parse_repeat_pattern(pattern)
        if repeat_info:
            # Simulate the reconstruction that would happen in create_recurring_task
            unit = repeat_info['unit']
            interval = repeat_info.get('interval', 1)
            
            if repeat_info['type'] == 'simple':
                if interval == 1:
                    reconstructed_pattern = f"[{unit}]"
                else:
                    reconstructed_pattern = f"[{interval}{unit}]"
            elif repeat_info['type'] == 'advanced' and unit == 'w':
                days = repeat_info.get('days', [])
                day_chars = {
                    'mon': 'm', 'tue': 't', 'wed': 'w', 'thu': 'r',
                    'fri': 'f', 'sat': 's', 'sun': 'u'
                }
                day_string = ''.join(day_chars.get(day, '') for day in days)
                if interval == 1:
                    reconstructed_pattern = f"[w-{day_string}]"
                else:
                    reconstructed_pattern = f"[{interval}w-{day_string}]"
            else:
                reconstructed_pattern = f"[{unit}]"  # Fallback
            
            result = f"{original} {reconstructed_pattern}".strip()
            status = "✅" if result == expected else "❌"
            print(f"{status} '{original}' + '{pattern}' -> '{result}'")
            if result != expected:
                print(f"    Expected: '{expected}'")
        else:
            print(f"❌ '{pattern}': Invalid pattern")
    print()


def test_integration_workflow():
    """Test the complete integration workflow."""
    print("Testing complete integration workflow:")
    print("=" * 50)
    
    # Simulate processing a task with repeat pattern
    task_examples = [
        "Take vitamins today [d]",
        "Team meeting tomorrow [w]", 
        "Gym workout 2025-01-15 [w-mwf]",
        "Monthly report 2025-02-01 [m]",
        "Code review friday @ 14:00 [w]"
    ]
    
    for task in task_examples:
        print(f"Processing: '{task}'")
        
        # Step 1: Split and find components
        words = task.split()
        
        # Find repeat pattern
        repeat_pattern = None
        for word in words:
            if word.startswith("[") and word.endswith("]"):
                repeat_pattern = word
                break
        
        if repeat_pattern:
            # Step 2: Parse repeat pattern
            repeat_info = parse_repeat_pattern(repeat_pattern)
            if repeat_info:
                print(f"  ✅ Repeat pattern: {repeat_pattern} -> {repeat_info}")
                
                # Step 3: Extract original summary (remove pattern)
                original_summary = task.replace(repeat_pattern, "").strip()
                print(f"  📝 Original task: '{original_summary}'")
                
                # Step 4: Simulate task completion and next occurrence
                # Use a dummy due date for calculation
                current_due = datetime(2025, 1, 15)  # Wednesday
                next_date = schedule_next_occurrence(current_due, repeat_info)
                
                if next_date:
                    days_diff = (next_date - current_due).days
                    print(f"  📅 Next occurrence: {next_date.strftime('%Y-%m-%d %A')} (+{days_diff} days)")
                    
                    # Step 5: Reconstruct new task
                    new_task = f"{original_summary} {repeat_pattern}".strip()
                    print(f"  🔄 New task: '{new_task}'")
                else:
                    print(f"  ❌ Could not calculate next occurrence")
            else:
                print(f"  ❌ Invalid repeat pattern: {repeat_pattern}")
        else:
            print(f"  ➖ No repeat pattern found")
        
        print()


if __name__ == "__main__":
    print("Todo Magic - Repeat Pattern Tests")
    print("=" * 60)
    
    test_repeat_pattern_parsing()
    test_next_occurrence_calculation()
    test_weekly_pattern_edge_cases()
    test_task_summary_reconstruction()
    test_integration_workflow()
    
    print("=" * 60)
    print("Repeat pattern tests completed! ✓")
    print("\nSupported patterns:")
    print("- Simple: [d], [w], [m], [y]")
    print("- Interval: [2d], [3w], [2m], [1y]")
    print("- Advanced weekly: [w-mwf], [2w-tr], etc.")
    print("  Day codes: m=Mon, t=Tue, w=Wed, r=Thu, f=Fri, s=Sat, u=Sun")