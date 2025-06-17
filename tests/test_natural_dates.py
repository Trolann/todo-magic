#!/usr/bin/env python3
"""
Test script for natural language date parsing functionality.
This script tests the new date parsing features without requiring Home Assistant.
"""

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


def remove_date_prefixes(summary: str) -> str:
    """Remove 'in' or ':' prefixes before date patterns and return cleaned summary."""
    # Pattern to match ' in <date>' or ': <date>' or ' in <date> @' or ': <date> @' patterns
    # This handles cases like "wash clothes in 5d" or "brush the dog: 1d [1w]"
    
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
    # Pattern for various date formats after 'in' or ':'
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


def test_natural_language_parsing():
    """Test natural language date parsing."""
    print("Testing natural language date parsing:")
    print("=" * 50)
    
    test_cases = [
        "today",
        "tomorrow", 
        "5d",
        "2w",
        "1m",
        "1y",
        "3d",
        "10d",
        # New flexible patterns
        "5 d",
        "5day",
        "5 day", 
        "5 days",
        "5days",
        "2 weeks",
        "2weeks",
        "1 month",
        "1months",
        "1 year",
        "3years",
        "invalid"
    ]
    
    for test_case in test_cases:
        result = parse_natural_language_date(test_case)
        if result:
            print(f"'{test_case}' -> {result.strftime('%Y-%m-%d')}")
        else:
            print(f"'{test_case}' -> None")
    print()


def test_prefix_removal():
    """Test prefix removal functionality."""
    print("Testing prefix removal:")
    print("=" * 50)
    
    test_cases = [
        "wash clothes in 5d",
        "brush the dog: 1d [1w]",
        "buy groceries in tomorrow",
        "call mom: today @ 17:00",
        "submit report in 2w",
        "take out trash: 3d",
        "meeting in 2025-03-15",
        "deadline: 12/25/25",
        # New flexible patterns
        "wash dog: in 5d",
        "feed cat in 5 d",
        "clean house: 5day",
        "water plants in 5 day",
        "grocery shopping: in 5 days",
        "doctor appointment in 5days",
        "meeting: in 2 weeks",
        "project due in 2weeks",
        "vacation: 1 month",
        "review in 1months",
        "normal task without prefix",
        "task with in the middle",
        "another: normal task"
    ]
    
    for test_case in test_cases:
        result = remove_date_prefixes(test_case)
        if result != test_case:
            print(f"'{test_case}' -> '{result}'")
        else:
            print(f"'{test_case}' -> (no change)")
    print()


def test_multi_word_patterns():
    """Test multi-word pattern detection - the key fix for spaced patterns."""
    print("Testing multi-word pattern detection:")
    print("=" * 50)
    
    test_cases = [
        # These should work with the fix
        "buy food: 1 week",
        "call mom: 2 days", 
        "dentist: 3 months",
        "vacation: 1 year",
        # These should still work (single word)
        "task: 5d",
        "meeting: tomorrow",
        "buy food: 1week",  # compact form
        # Edge cases
        "do something: 10 days",
        "finish project: 6 months"
    ]
    
    for test_case in test_cases:
        print(f"Testing: '{test_case}'")
        
        # Simulate the detection logic
        cleaned_summary = remove_date_prefixes(test_case)
        words = cleaned_summary.split()
        
        # Check individual words first (current logic)
        has_pattern_single = False
        for word in words:
            if parse_natural_language_date(word):
                has_pattern_single = True
                print(f"  ✅ Found single-word pattern: '{word}'")
                break
        
        # Check adjacent word combinations (new logic) 
        has_pattern_multi = False
        if not has_pattern_single:
            for i in range(len(words) - 1):
                two_words = f"{words[i]} {words[i+1]}"
                if parse_natural_language_date(two_words):
                    has_pattern_multi = True
                    print(f"  ✅ Found multi-word pattern: '{two_words}'")
                    break
        
        if not has_pattern_single and not has_pattern_multi:
            print(f"  ❌ No pattern found")
        
        print()


def test_complete_workflow():
    """Test the complete workflow with realistic examples."""
    print("Testing complete workflow:")
    print("=" * 50)
    
    test_cases = [
        "wash clothes in 5d",
        "brush the dog: 1d [1w]",
        "buy groceries tomorrow @ 18:00",
        "call mom: today at 17:00",
        "submit report in 2w",
        "meeting 2025-03-15 @ 14:30",
        # Add multi-word pattern examples
        "buy food: 1 week",
        "call mom: 2 days",
        "dentist: 3 months",
        # Add repeat pattern examples
        "take vitamins today [d]",
        "team meeting tomorrow [w]",
        "gym workout 5d [w-mwf]"
    ]
    
    for test_case in test_cases:
        print(f"Original: '{test_case}'")
        
        # Step 1: Remove prefixes
        cleaned = remove_date_prefixes(test_case)
        print(f"Cleaned:  '{cleaned}'")
        
        # Step 2: Split and try to parse date from end
        words = cleaned.split()
        current_element = -1
        
        # Check for repeat pattern
        repeat_string = ""
        if words[current_element].startswith("[") and words[current_element].endswith("]"):
            repeat_string = words[current_element]
            current_element -= 1
        
        # Check for time
        time_string = ""
        if len(words) > abs(current_element):
            # Try to parse as time (simplified check)
            time_candidate = words[current_element]
            if ":" in time_candidate and len(time_candidate.split(":")) == 2:
                try:
                    hours, mins = time_candidate.split(":")
                    if 0 <= int(hours) <= 23 and 0 <= int(mins) <= 59:
                        time_string = time_candidate
                        current_element -= 1
                        # Check if there's an "at" or "@" before the time
                        if len(words) > abs(current_element) and words[current_element] in ("at", "@"):
                            current_element -= 1
                except ValueError:
                    pass
        
        # Check for date - handle both single word and multi-word patterns
        parsed_date = None
        date_words_used = 1
        
        if len(words) > abs(current_element):
            # First try single word
            date_candidate = words[current_element]
            parsed_date = parse_natural_language_date(date_candidate)
            
            # If single word didn't work, try two-word combination
            if not parsed_date and len(words) > abs(current_element - 1):
                two_words = f"{words[current_element - 1]} {words[current_element]}"
                parsed_date = parse_natural_language_date(two_words)
                if parsed_date:
                    date_words_used = 2
            
            if parsed_date:
                print(f"Date:     {parsed_date.strftime('%Y-%m-%d')} (using {date_words_used} word{'s' if date_words_used > 1 else ''})")
                if time_string:
                    print(f"Time:     {time_string}")
                if repeat_string:
                    print(f"Repeat:   {repeat_string}")
                
                # Reconstruct task name - account for multi-word dates
                date_start_index = current_element - (date_words_used - 1)
                task_name = " ".join(words[:date_start_index])
                print(f"Task:     '{task_name}'")
            else:
                print("No date found")
        else:
            print("No words to parse")
        
        print("-" * 30)


if __name__ == "__main__":
    test_natural_language_parsing()
    test_prefix_removal()  
    test_multi_word_patterns()
    test_complete_workflow()