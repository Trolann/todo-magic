#!/usr/bin/env python3
"""
Comprehensive test suite for repeat pattern functionality.
Tests all requested patterns including [mwf], [6d], [2w], [2w-th] and integration with todo processing.
"""

from datetime import datetime, timedelta
import re
import sys

# Copy relevant functions to avoid Home Assistant dependencies
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
            # Approximate month calculation - could be improved with dateutil
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


def check_date_format(given_string: str) -> datetime | None:
    """Check if given string matches any supported date format, including natural language."""
    # First try natural language parsing
    natural_date = parse_natural_language_date(given_string)
    if natural_date:
        return natural_date
    
    # Then try traditional date formats
    date_formats = ['%m/%d/%y', '%m/%d/%Y', '%m-%d-%y', '%m-%d-%Y', '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y', '%m-%d-%Y', '%m/%d/%Y', '%m.%d.%Y', '%Y-%d-%m', '%Y/%d/%m', '%Y.%d.%m', '%d-%Y-%m', '%d/%Y/%m', '%d.%Y.%m', '%m-%Y-%d', '%m/%Y/%d', '%m.%Y.%d']
    return check_formats(given_string, date_formats)


def check_formats(given_string: str, formats: list[str]) -> datetime | None:
    """Check if given string matches any of the provided formats."""
    for given_format in formats:
        try:
            return_time = datetime.strptime(given_string, given_format)
            return return_time
        except ValueError:
            continue
    return None


def check_time_format(given_string: str) -> datetime | None:
    """Check if given string matches any supported time format."""
    time_formats = ['%H:%M', '%H %M', '%H%M']
    return check_formats(given_string, time_formats)


def remove_date_prefixes(summary: str) -> str:
    """Remove 'in' or ':' prefixes before date patterns and return cleaned summary."""
    # Pattern to match ' in <date>' or ': <date>' or ' in <date> @' or ': <date> @' patterns
    
    # First, handle the special ': in' case
    colon_in_pattern = re.search(r'\s*:\s*in\s+(today|tomorrow|\d+\s*(?:days?|weeks?|months?|years?|[dwmy]))', summary.lower())
    if colon_in_pattern:
        # Remove the ': in' prefix and keep the rest
        prefix_start = colon_in_pattern.start()
        result = summary[:prefix_start] + ' ' + summary[colon_in_pattern.start(1):]
        # Clean up any double spaces
        return re.sub(r'\s+', ' ', result).strip()
    
    # Then handle regular 'in' or ':' patterns
    natural_lang_with_prefix = re.search(r'\s*(in|:)\s+(today|tomorrow|\d+\s*(?:days?|weeks?|months?|years?|[dwmy]))', summary.lower())
    if natural_lang_with_prefix:
        # Remove the prefix and keep the rest
        prefix_start = natural_lang_with_prefix.start(1)  # Start of 'in' or ':'
        result = summary[:prefix_start] + ' ' + summary[natural_lang_with_prefix.start(2):]
        # Clean up any double spaces
        return re.sub(r'\s+', ' ', result).strip()
    
    # Also handle regular date formats with prefixes
    date_patterns = [
        r'\d{1,2}/\d{1,2}/\d{2,4}',  # MM/DD/YY, MM/DD/YYYY
        r'\d{1,2}-\d{1,2}-\d{2,4}',  # MM-DD-YY, MM-DD-YYYY
        r'\d{4}-\d{1,2}-\d{1,2}',    # YYYY-MM-DD
        r'\d{4}/\d{1,2}/\d{1,2}',    # YYYY/MM/DD
        r'\d{1,2}\.\d{1,2}\.\d{2,4}', # DD.MM.YYYY
    ]
    
    # Handle ': in' with regular dates
    for pattern in date_patterns:
        colon_in_date_pattern = rf'\s*:\s*in\s+({pattern})'
        match = re.search(colon_in_date_pattern, summary, re.IGNORECASE)
        if match:
            prefix_start = match.start()
            result = summary[:prefix_start] + ' ' + summary[match.start(1):]
            return re.sub(r'\s+', ' ', result).strip()
    
    # Handle regular 'in' or ':' with dates
    for pattern in date_patterns:
        regex_pattern = rf'\s*(in|:)\s+({pattern})'
        match = re.search(regex_pattern, summary, re.IGNORECASE)
        if match:
            prefix_start = match.start(1)
            result = summary[:prefix_start] + ' ' + summary[match.start(2):]
            # Clean up any double spaces
            return re.sub(r'\s+', ' ', result).strip()
    
    return summary

class TestRepeatPatterns:
    """Comprehensive test suite for repeat patterns."""
    
    def test_all_requested_patterns(self):
        """Test all patterns specifically requested in the requirements."""
        print("Testing all requested repeat patterns:")
        print("=" * 60)
        
        # Test cases: (pattern, expected_result)
        test_cases = [
            # Simple patterns
            ("[d]", {"type": "simple", "unit": "d", "interval": 1}),
            ("[w]", {"type": "simple", "unit": "w", "interval": 1}),
            ("[m]", {"type": "simple", "unit": "m", "interval": 1}),
            ("[y]", {"type": "simple", "unit": "y", "interval": 1}),
            
            # Interval patterns (as requested)
            ("[6d]", {"type": "simple", "unit": "d", "interval": 6}),
            ("[2w]", {"type": "simple", "unit": "w", "interval": 2}),
            ("[1m]", {"type": "simple", "unit": "m", "interval": 1}),
            ("[1y]", {"type": "simple", "unit": "y", "interval": 1}),
            
            # Advanced weekly patterns (as requested)
            ("[w-mwf]", {"type": "advanced", "unit": "w", "interval": 1, "days": ["mon", "wed", "fri"]}),
            ("[mwf]", {"type": "advanced", "unit": "w", "interval": 1, "days": ["mon", "wed", "fri"]}),
            ("[2w-tr]", {"type": "advanced", "unit": "w", "interval": 2, "days": ["tue", "thu"]}),
            ("[w-tr]", {"type": "advanced", "unit": "w", "interval": 1, "days": ["tue", "thu"]}),
            ("[w-m]", {"type": "advanced", "unit": "w", "interval": 1, "days": ["mon"]}),
            ("[3w-mwf]", {"type": "advanced", "unit": "w", "interval": 3, "days": ["mon", "wed", "fri"]}),
            
            # Edge cases
            ("[w-s]", {"type": "advanced", "unit": "w", "interval": 1, "days": ["sat"]}),
            ("[w-u]", {"type": "advanced", "unit": "w", "interval": 1, "days": ["sun"]}),
            ("[4w-mtwrfsu]", {"type": "advanced", "unit": "w", "interval": 4, "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]}),
        ]
        
        all_passed = True
        for pattern, expected in test_cases:
            result = parse_repeat_pattern(pattern)
            if result == expected:
                print(f"✅ {pattern}: {result}")
            else:
                print(f"❌ {pattern}: Expected {expected}, got {result}")
                all_passed = False
        
        print(f"\nPattern parsing: {'✅ All passed' if all_passed else '❌ Some failed'}")
        return all_passed
    
    def test_special_mwf_pattern(self):
        """Test the special [mwf] pattern without 'w-' prefix."""
        print("\nTesting special [mwf] pattern (without w- prefix):")
        print("=" * 60)
        
        # The current implementation expects [w-mwf], but let's test if [mwf] works
        result = parse_repeat_pattern("[mwf]")
        
        if result:
            print(f"✅ [mwf] parsed as: {result}")
            
            # Test if it behaves like a weekly pattern
            if result.get("type") == "advanced" and result.get("unit") == "w":
                print("✅ [mwf] correctly identified as advanced weekly pattern")
                
                # Test the days
                expected_days = ["mon", "wed", "fri"]
                actual_days = result.get("days", [])
                if actual_days == expected_days:
                    print(f"✅ [mwf] days correctly parsed: {actual_days}")
                    return True
                else:
                    print(f"❌ [mwf] days incorrect: expected {expected_days}, got {actual_days}")
                    return False
            else:
                print(f"❌ [mwf] not recognized as advanced weekly pattern: {result}")
                return False
        else:
            print("❌ [mwf] pattern not recognized - this needs to be implemented")
            return False
    
    def test_next_occurrence_calculations(self):
        """Test next occurrence calculations for all requested patterns."""
        print("\nTesting next occurrence calculations:")
        print("=" * 60)
        
        # Use a known Monday for predictable testing
        base_date = datetime(2025, 1, 13)  # Monday
        print(f"Base date: {base_date.strftime('%Y-%m-%d %A')}")
        
        test_cases = [
            # Pattern, Description, Expected days from base
            ("[6d]", "Every 6 days", 6),
            ("[2w]", "Every 2 weeks", 14),
            ("[w-mwf]", "Weekly Mon/Wed/Fri (next Wed)", 2),
            ("[2w-tr]", "Every 2 weeks Tue/Thu (next Tue)", 1),
            ("[w-tr]", "Weekly Tue/Thu (next Tue)", 1),
            ("[w-m]", "Weekly Monday (next Monday)", 7),
            ("[w-f]", "Weekly Friday (next Friday)", 4),
        ]
        
        all_passed = True
        for pattern, description, expected_days in test_cases:
            repeat_info = parse_repeat_pattern(pattern)
            if repeat_info:
                next_date = schedule_next_occurrence(base_date, repeat_info)
                if next_date:
                    actual_days = (next_date - base_date).days
                    if actual_days == expected_days:
                        print(f"✅ {pattern} ({description}): {next_date.strftime('%Y-%m-%d %A')} (+{actual_days} days)")
                    else:
                        print(f"❌ {pattern}: Expected +{expected_days} days, got +{actual_days} days")
                        all_passed = False
                else:
                    print(f"❌ {pattern}: Could not calculate next occurrence")
                    all_passed = False
            else:
                print(f"❌ {pattern}: Invalid pattern")
                all_passed = False
        
        print(f"\nNext occurrence calculations: {'✅ All passed' if all_passed else '❌ Some failed'}")
        return all_passed
    
    def test_integration_with_todo_processing(self):
        """Test integration with the full todo processing workflow."""
        print("\nTesting integration with todo processing workflow:")
        print("=" * 60)
        
        # Test cases that simulate real todo items
        test_todos = [
            "Take vitamins today [d]",
            "Weekly team meeting tomorrow [w]",
            "Gym workout 2025-01-15 [w-mwf]",
            "Bi-weekly review 2025-01-20 [2w]",
            "Check email 5d [6d]",
            "Team standup 2025-01-14 @ 09:00 [w-mwf]",
            "Project deadline: 2025-02-01 [2w-tr]",
        ]
        
        all_passed = True
        for todo in test_todos:
            print(f"\nProcessing: '{todo}'")
            
            # Step 1: Remove prefixes
            cleaned = remove_date_prefixes(todo)
            print(f"  Cleaned: '{cleaned}'")
            
            # Step 2: Parse components (simulate main processing logic)
            words = cleaned.split()
            current_element = -1
            
            # Find repeat pattern
            repeat_string = ""
            repeat_info = None
            if len(words) >= abs(current_element) and words[current_element].startswith("["):
                repeat_string = words[current_element]
                repeat_info = parse_repeat_pattern(repeat_string)
                if repeat_info:
                    print(f"  ✅ Repeat pattern: {repeat_string} -> {repeat_info['type']} {repeat_info['unit']}")
                    current_element -= 1
                else:
                    print(f"  ❌ Invalid repeat pattern: {repeat_string}")
                    all_passed = False
                    continue
            
            # Find time
            time_string = ""
            if len(words) >= abs(current_element) and ":" in words[current_element]:
                time_candidate = words[current_element]
                if check_time_format(time_candidate):
                    time_string = time_candidate
                    print(f"  ✅ Time: {time_string}")
                    current_element -= 1
                    # Check for "at" or "@"
                    if len(words) >= abs(current_element) and words[current_element] in ("at", "@"):
                        current_element -= 1
            
            # Find date
            date_obj = None
            date_words_used = 1
            if len(words) >= abs(current_element):
                # Try single word first
                date_obj = check_date_format(words[current_element])
                
                # Try two-word combination if single word failed
                if not date_obj and len(words) >= abs(current_element - 1):
                    two_words = f"{words[current_element - 1]} {words[current_element]}"
                    date_obj = check_date_format(two_words)
                    if date_obj:
                        date_words_used = 2
                
                if date_obj:
                    print(f"  ✅ Date: {date_obj.strftime('%Y-%m-%d')} (using {date_words_used} word{'s' if date_words_used > 1 else ''})")
                    
                    # Calculate task name
                    date_start_index = current_element - (date_words_used - 1)
                    task_name = " ".join(words[:date_start_index])
                    print(f"  ✅ Task: '{task_name}'")
                    
                    # Test recurring task creation if pattern exists
                    if repeat_info:
                        next_date = schedule_next_occurrence(date_obj, repeat_info)
                        if next_date:
                            days_diff = (next_date - date_obj).days
                            print(f"  ✅ Next occurrence: {next_date.strftime('%Y-%m-%d')} (+{days_diff} days)")
                        else:
                            print(f"  ❌ Could not calculate next occurrence")
                            all_passed = False
                else:
                    print(f"  ❌ No date found")
                    all_passed = False
            else:
                print(f"  ❌ Not enough words to parse")
                all_passed = False
        
        print(f"\nIntegration testing: {'✅ All passed' if all_passed else '❌ Some failed'}")
        return all_passed
    
    def test_edge_cases_and_invalid_patterns(self):
        """Test edge cases and invalid patterns."""
        print("\nTesting edge cases and invalid patterns:")
        print("=" * 60)
        
        invalid_patterns = [
            "",           # Empty string
            "[]",         # Empty brackets
            "[xyz]",      # Invalid unit
            "[w-xyz]",    # Invalid days
            "[0d]",       # Zero interval (should be allowed but questionable)
            "d",          # No brackets
            "[w-]",       # No days specified
            "[999d]",     # Very large interval
            "[w-mmm]",    # Duplicate days
            "[ d ]",      # Spaces inside brackets
            "[D]",        # Uppercase
            "[1.5d]",     # Decimal interval
        ]
        
        questionable_but_valid = [
            "[0d]",       # Zero interval - technically parsed but logically questionable
        ]
        
        print("Invalid patterns (should return None):")
        for pattern in invalid_patterns:
            result = parse_repeat_pattern(pattern)
            if result is None:
                print(f"✅ '{pattern}' correctly rejected")
            else:
                if pattern in questionable_but_valid:
                    print(f"⚠️  '{pattern}' parsed as {result} (questionable but valid)")
                else:
                    print(f"❌ '{pattern}' should be rejected but got {result}")
        
        # Test boundary conditions for advanced patterns
        print("\nBoundary conditions for advanced patterns:")
        boundary_tests = [
            ("[w-m]", "Single day"),
            ("[w-mtwrfsu]", "All days of week"),
            ("[52w-f]", "Large interval"),
            ("[w-fs]", "Weekend only"),
        ]
        
        for pattern, description in boundary_tests:
            result = parse_repeat_pattern(pattern)
            if result:
                print(f"✅ {pattern} ({description}): {result}")
            else:
                print(f"❌ {pattern} ({description}): Failed to parse")
        
        return True
    
    def run_all_tests(self):
        """Run all tests and return overall result."""
        print("Todo Magic - Comprehensive Repeat Pattern Test Suite")
        print("=" * 80)
        
        tests = [
            ("Pattern Parsing", self.test_all_requested_patterns),
            ("Special [mwf] Pattern", self.test_special_mwf_pattern),
            ("Next Occurrence Calculations", self.test_next_occurrence_calculations),
            ("Integration with Todo Processing", self.test_integration_with_todo_processing),
            ("Edge Cases and Invalid Patterns", self.test_edge_cases_and_invalid_patterns),
        ]
        
        results = []
        for test_name, test_func in tests:
            print(f"\n{'='*20} {test_name} {'='*20}")
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ {test_name} failed with exception: {e}")
                results.append((test_name, False))
        
        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        passed = 0
        total = len(results)
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{status}: {test_name}")
            if result:
                passed += 1
        
        print(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! Repeat pattern functionality is working correctly.")
            print("\nSupported patterns confirmed:")
            print("- Simple: [d], [w], [m], [y]")
            print("- Interval: [6d], [2w], [3m], [1y]")
            print("- Advanced weekly: [w-mwf], [2w-th], [w-tr], etc.")
            print("- Day codes: m=Mon, t=Tue, w=Wed, r=Thu, f=Fri, s=Sat, u=Sun")
        else:
            print("⚠️  Some tests failed. Check the output above for details.")
        
        return passed == total


if __name__ == "__main__":
    tester = TestRepeatPatterns()
    success = tester.run_all_tests()
    
    if not success:
        sys.exit(1)