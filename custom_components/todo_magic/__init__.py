"""
Custom integration to enhance all Todo lists in Home Assistant.
"""
from __future__ import annotations

import logging
from functools import partial
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN

from datetime import datetime, timedelta
import re

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.TODO]

# Simple lock to prevent concurrent processing of the same entity
PROCESSING_LOCKS = set()



def check_date_format(given_string: str) -> datetime | None:
    """Check if given string matches any supported date format, including natural language."""
    # First try natural language parsing
    natural_date = parse_natural_language_date(given_string)
    if natural_date:
        return natural_date
    
    # Then try traditional date formats
    date_formats = ['%m/%d/%y', '%m/%d/%Y', '%m-%d-%y', '%m-%d-%Y', '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y', '%m-%d-%Y', '%m/%d/%Y', '%m.%d.%Y', '%Y-%d-%m', '%Y/%d/%m', '%Y.%d.%m', '%d-%Y-%m', '%d/%Y/%m', '%d.%Y.%m', '%m-%Y-%d', '%m/%Y/%d', '%m.%Y.%d']
    return check_formats(given_string, date_formats)


def check_time_format(given_string: str) -> datetime | None:
    """Check if given string matches any supported time format."""
    time_formats = ['%H:%M', '%H %M', '%H%M']
    return check_formats(given_string, time_formats)


def check_formats(given_string: str, formats: list[str]) -> datetime | None:
    """Check if given string matches any of the provided formats."""
    for given_format in formats:
        try:
            return_time = datetime.strptime(given_string, given_format)
            return return_time
        except ValueError:
            continue
    return None


def parse_repeat_pattern(pattern_string: str) -> dict[str, Any] | None:
    """Parse repeat patterns like [d], [w], [m], [y], [w-mwf], etc.
    
    Returns:
        dict with pattern info or None if invalid pattern
        Format: {
            'type': 'simple' | 'advanced',
            'unit': 'd' | 'w' | 'm' | 'y',
            'interval': int (default 1),
            'days': list of day abbreviations for weekly patterns (optional)
        }
    """
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


def calculate_first_occurrence(today: datetime, repeat_info: dict[str, Any]) -> datetime | None:
    """Calculate the first occurrence date for a new recurring task.
    
    For initial task creation:
    - Daily tasks: due today
    - Weekly tasks: due today if it matches the pattern, otherwise next matching day
    - Advanced patterns: due today if today matches, otherwise next matching day
    
    Args:
        today: Today's date
        repeat_info: Repeat pattern info from parse_repeat_pattern()
    
    Returns:
        First occurrence date or None if calculation fails
    """
    if not repeat_info or repeat_info['type'] not in ('simple', 'advanced'):
        return None
    
    unit = repeat_info['unit']
    interval = repeat_info.get('interval', 1)
    
    if repeat_info['type'] == 'simple':
        if unit == 'd':
            # Daily tasks: due today
            return today
        elif unit == 'w':
            # Weekly tasks: due today (regardless of day of week)
            return today
        elif unit == 'm':
            # Monthly tasks: due today
            return today
        elif unit == 'y':
            # Yearly tasks: due today
            return today
    
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


def schedule_next_occurrence(current_date: datetime, repeat_info: dict[str, Any]) -> datetime | None:
    """Calculate the next occurrence date based on repeat pattern.
    
    Args:
        current_date: The current due date
        repeat_info: Repeat pattern info from parse_repeat_pattern()
    
    Returns:
        Next occurrence date or None if calculation fails
    """
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


def get_entity_settings(options: dict[str, Any], entity_id: str) -> dict[str, Any]:
    """Get settings for a specific entity from options."""
    entity_key = entity_id.replace(".", "_")
    return {
        "auto_due_parsing": options.get(f"{entity_key}_auto_due_parsing", True),
        "auto_sort": options.get(f"{entity_key}_auto_sort", False),
        "process_recurring": options.get(f"{entity_key}_process_recurring", False),
        "clear_days": options.get(f"{entity_key}_clear_days", -1),
    }


@callback
def state_changed_listener(hass: HomeAssistant, entry: ConfigEntry, evt: Event) -> None:
    """Handle state changed events for todo entities - only process newly added items."""
    entity_id = evt.data.get("entity_id", "")
    if not entity_id.startswith("todo."):
        return

    old_state = evt.data.get("old_state")
    new_state = evt.data.get("new_state")
    
    if not new_state or new_state.state == "unavailable":
        return

    # Get settings for this entity
    settings = get_entity_settings(entry.options, entity_id)
    
    # Skip processing if auto_due_parsing is disabled for this entity
    if not settings["auto_due_parsing"]:
        return

    # Debug: Log the state change details
    LOGGER.debug("State change for %s:", entity_id)
    if old_state:
        LOGGER.debug("  Old state: %s, attributes: %s", old_state.state, getattr(old_state, 'attributes', {}))
    if new_state:
        LOGGER.debug("  New state: %s, attributes: %s", new_state.state, getattr(new_state, 'attributes', {}))

    # Try multiple methods to detect new items
    should_process = False
    
    # Method 1: Check for count attribute
    old_count = 0
    new_count = 0
    
    if old_state and hasattr(old_state, 'attributes') and 'count' in old_state.attributes:
        old_count = old_state.attributes.get('count', 0)
    
    if hasattr(new_state, 'attributes') and 'count' in new_state.attributes:
        new_count = new_state.attributes.get('count', 0)
    
    if new_count > old_count:
        LOGGER.debug("Item count increased: %d -> %d", old_count, new_count)
        should_process = True
    
    # Method 2: If no count attribute, check for any state change (fallback)
    elif not (old_state and hasattr(old_state, 'attributes') and 'count' in old_state.attributes):
        LOGGER.debug("No count attribute found, using fallback detection")
        # Process any state change as potential new item (more permissive)
        should_process = True
    
    if not should_process:
        LOGGER.debug("No new items detected, skipping processing")
        return
    
    # Check if already processing this entity
    if entity_id in PROCESSING_LOCKS:
        LOGGER.debug("Already processing %s, skipping", entity_id)
        return
    
    LOGGER.debug("New item detected for %s (count: %d -> %d)", entity_id, old_count, new_count)

    # Create background task to process the new item
    hass.async_create_background_task(
        process_new_todo_item(hass, entity_id, settings),
        name=f"todo_magic_new_item_{entity_id}"
    )
    
    # Also check for completed recurring tasks if recurring processing is enabled
    if settings.get("process_recurring", False):
        hass.async_create_background_task(
            check_for_completed_recurring_tasks(hass, entity_id, settings),
            name=f"todo_magic_recurring_{entity_id}"
        )


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    LOGGER.debug("Options updated for Todo Magic integration")
    # No need to reload the entire integration - the listeners will pick up the new settings automatically





async def process_new_todo_item(hass: HomeAssistant, entity_id: str, settings: dict[str, Any]) -> None:
    """Process the newest todo item for the given entity."""
    # Add processing lock
    if entity_id in PROCESSING_LOCKS:
        LOGGER.debug("Already processing %s, aborting", entity_id)
        return
    
    PROCESSING_LOCKS.add(entity_id)
    
    try:
        result = await hass.services.async_call(
            TODO_DOMAIN,
            "get_items",
            {"entity_id": entity_id},
            blocking=True,
            return_response=True
        )

        LOGGER.debug("get_items result for new item processing: %s", result)

        # Check if result has the correct structure
        if not result or entity_id not in result or "items" not in result[entity_id]:
            LOGGER.debug("No items found for %s", entity_id)
            return

        # Access items correctly through the entity_id key
        items = result[entity_id]["items"]
        
        if not items:
            LOGGER.debug("No items to process for %s", entity_id)
            return
        
        # Find items that might need processing
        # Look for items without due dates that contain date patterns
        candidates = []
        for item in items:
            if "uid" not in item:
                continue
                
            summary = item.get("summary", "")
            due = item.get("due", "")
            
            # Skip items that already have due dates
            if due:
                continue
                
            # Check if summary contains potential date patterns
            cleaned_summary = remove_date_prefixes(summary)
            words = cleaned_summary.split()
            
            # Look for any recognizable date patterns
            has_date_pattern = False
            
            # Check individual words first
            for word in words:
                if (parse_natural_language_date(word) or 
                    re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', word) or
                    re.match(r'\d{4}-\d{1,2}-\d{1,2}', word)):
                    has_date_pattern = True
                    break
            
            # If no pattern found in individual words, check adjacent word combinations
            if not has_date_pattern:
                for i in range(len(words) - 1):
                    two_words = f"{words[i]} {words[i+1]}"
                    if parse_natural_language_date(two_words):
                        has_date_pattern = True
                        break
            
            if has_date_pattern:
                candidates.append(item)
        
        LOGGER.debug("Found %d candidate items for processing: %s", len(candidates), [item.get("summary") for item in candidates])
        
        if not candidates:
            LOGGER.debug("No items with date patterns found for %s", entity_id)
            return
            
        # Process the first candidate (could be improved to find "newest" based on other criteria)
        new_item = candidates[0]
            
        LOGGER.debug("Processing new item: %s", new_item)
        
        summary = new_item.get("summary", "")
        
        # Remove date prefixes like 'in' and ':' before processing
        cleaned_summary = remove_date_prefixes(summary)
        
        # Check if there is a date as one of the last words in the summary
        summary_split = cleaned_summary.split()

        # Skip if summary is empty or too short
        if len(summary_split) == 0:
            return

        current_element = -1
        repeat_string = ""
        repeat_info = None
        time_string = ""
        calculated_due_date = None
        
        # Check bounds before accessing elements - Parse repeat pattern FIRST
        if len(summary_split) >= abs(current_element) and summary_split[current_element].startswith("[") and summary_split[current_element].endswith("]"):
            repeat_string = summary_split[current_element]
            repeat_info = parse_repeat_pattern(repeat_string)
            if repeat_info:
                LOGGER.debug("Found valid repeat pattern: %s -> %s", repeat_string, repeat_info)
                # Calculate due date from TODAY, not from any text in the task
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                calculated_due_date = calculate_first_occurrence(today, repeat_info)
                if calculated_due_date:
                    LOGGER.debug("Calculated due date from repeat pattern: %s", calculated_due_date.strftime('%Y-%m-%d'))
                else:
                    LOGGER.error("Could not calculate due date for repeat pattern: %s", repeat_string)
            else:
                LOGGER.debug("Invalid repeat pattern: %s", repeat_string)
            current_element -= 1
        
        # Check for time component (this is still relevant even with repeat patterns)
        if len(summary_split) >= abs(current_element):
            due_time = check_time_format(summary_split[current_element])
            if due_time:
                time_string = summary_split[current_element]
                if len(summary_split) >= abs(current_element - 1) and summary_split[current_element - 1] in ("at", "@"):
                    current_element -= 1
                current_element -= 1

        # If we have a repeat pattern, ignore any manual dates and use calculated date
        if repeat_info and calculated_due_date:
            LOGGER.debug("Using calculated date from repeat pattern, ignoring any manual dates")
            date_string = f'{calculated_due_date.year}-{calculated_due_date.month:02d}-{calculated_due_date.day:02d}'
            if not time_string:
                # default to 23:59 for repeat pattern tasks
                time_string = "23:59"
            
            # Remove all date/time text from summary, keep only task name and repeat pattern
            task_words = []
            for word in summary_split:
                # Skip words that look like dates, times, or prefixes, but keep repeat pattern
                if word == repeat_string:
                    continue  # We'll add this back at the end
                elif word in ("at", "@", "in", ":"):
                    continue
                elif check_date_format(word) or check_time_format(word):
                    continue
                elif re.match(r'^\d+\s*(days?|weeks?|months?|years?|[dwmy])$', word.lower()):
                    continue
                else:
                    task_words.append(word)
            
            # Check for multi-word date patterns and remove them
            i = 0
            while i < len(task_words) - 1:
                two_words = f"{task_words[i]} {task_words[i+1]}"
                if check_date_format(two_words):
                    # Remove both words
                    task_words.pop(i)
                    task_words.pop(i)  # pop again since list shifted
                else:
                    i += 1
            
            new_summary = f'{" ".join(task_words)} {repeat_string}'.strip()
            
        else:
            # Original logic for non-repeat tasks: try to parse dates from text
            date_string = None
            date_words_used = 1
            
            if len(summary_split) >= abs(current_element):
                # First try single word
                date_obj = check_date_format(summary_split[current_element])
                if date_obj:
                    date_string = f'{date_obj.year}-{date_obj.month:02d}-{date_obj.day:02d}'
                
                # If single word didn't work, try two-word combinations
                if not date_string and len(summary_split) >= abs(current_element - 1):
                    two_words = f"{summary_split[current_element - 1]} {summary_split[current_element]}"
                    date_obj = check_date_format(two_words)
                    if date_obj:
                        date_string = f'{date_obj.year}-{date_obj.month:02d}-{date_obj.day:02d}'
                        date_words_used = 2
            
            if date_string:
                LOGGER.debug("Found date in new item: %s", date_string)
                if not time_string:
                    time_string = "23:59"
                date_index = current_element - (date_words_used - 1)
                new_summary = f'{" ".join(summary_split[:date_index])} {repeat_string}'.strip()
            else:
                LOGGER.debug("No date pattern found in new item: %s", summary)
                return

        # At this point, we should have a date_string and new_summary
        if date_string:
            # Assemble due datetime
            update_item_dict = {
                "entity_id": entity_id,
                "item": summary,
                "rename": new_summary,
                "status": new_item.get("status", "needs_action"),
            }
            if time_string:
                update_item_dict["due_datetime"] = f"{date_string} {time_string}"
            else:
                update_item_dict["due_date"] = date_string

            LOGGER.debug("Updating item with: %s", update_item_dict)
            
            # Using the correct parameters according to service docs
            await hass.services.async_call(
                TODO_DOMAIN,
                "update_item",
                update_item_dict,
                blocking=True
            )
            
            # Log repeat info for debugging
            if repeat_info and settings.get("process_recurring", False):
                LOGGER.debug("Task with repeat pattern processed: %s with pattern %s", new_summary, repeat_info)
        else:
            LOGGER.debug("No date could be determined for item: %s", summary)

    except Exception as err:
        LOGGER.error("Error processing new todo item: %s", err)
    finally:
        # Always remove the processing lock
        PROCESSING_LOCKS.discard(entity_id)


async def create_recurring_task(hass: HomeAssistant, entity_id: str, original_summary: str, 
                               repeat_info: dict[str, Any], original_due_date: datetime, 
                               time_string: str = "") -> None:
    """Create a new instance of a recurring task.
    
    Args:
        hass: Home Assistant instance
        entity_id: Todo entity ID
        original_summary: Original task summary (without repeat pattern)
        repeat_info: Repeat pattern information
        original_due_date: Original due date
        time_string: Time component if present
    """
    try:
        # Calculate next occurrence from TODAY (completion date), not original due date
        # This ensures that if someone completes a task late, the next occurrence is calculated from now
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        next_date = schedule_next_occurrence(today, repeat_info)
        if not next_date:
            LOGGER.error("Could not calculate next occurrence for recurring task: %s", original_summary)
            return
        
        LOGGER.debug("Calculated next occurrence from completion date (%s): %s", 
                    today.strftime('%Y-%m-%d'), next_date.strftime('%Y-%m-%d'))
        
        # Reconstruct the repeat pattern string
        unit = repeat_info['unit']
        interval = repeat_info.get('interval', 1)
        
        if repeat_info['type'] == 'simple':
            if interval == 1:
                repeat_pattern = f"[{unit}]"
            else:
                repeat_pattern = f"[{interval}{unit}]"
        elif repeat_info['type'] == 'advanced' and unit == 'w':
            days = repeat_info.get('days', [])
            day_chars = {
                'mon': 'm', 'tue': 't', 'wed': 'w', 'thu': 'r',
                'fri': 'f', 'sat': 's', 'sun': 'u'
            }
            day_string = ''.join(day_chars.get(day, '') for day in days)
            if interval == 1:
                # Check if this could be a direct pattern like [mwf] (no w- prefix needed)
                # Use the shorter form for single intervals
                repeat_pattern = f"[{day_string}]"
            else:
                repeat_pattern = f"[{interval}w-{day_string}]"
        else:
            repeat_pattern = f"[{unit}]"  # Fallback
        
        # Create new task summary with repeat pattern
        new_summary = f"{original_summary} {repeat_pattern}".strip()
        
        # Format next due date
        next_date_str = f'{next_date.year}-{next_date.month:02d}-{next_date.day:02d}'
        
        # Create the new task
        add_item_dict = {
            "entity_id": entity_id,
            "item": new_summary,
        }
        
        if time_string:
            add_item_dict["due_datetime"] = f"{next_date_str} {time_string}"
        else:
            add_item_dict["due_date"] = next_date_str
        
        LOGGER.debug("Creating recurring task: %s with due date %s", new_summary, next_date_str)
        
        await hass.services.async_call(
            TODO_DOMAIN,
            "add_item",
            add_item_dict,
            blocking=True
        )
        
        LOGGER.info("Created recurring task: %s", new_summary)
        
    except Exception as err:
        LOGGER.error("Error creating recurring task: %s", err)


async def check_for_completed_recurring_tasks(hass: HomeAssistant, entity_id: str, settings: dict[str, Any]) -> None:
    """Check for completed tasks with repeat patterns and create new instances."""
    if not settings.get("process_recurring", False):
        return
    
    try:
        # Get all items including completed ones
        result = await hass.services.async_call(
            TODO_DOMAIN,
            "get_items",
            {"entity_id": entity_id},
            blocking=True,
            return_response=True
        )
        
        if not result or entity_id not in result or "items" not in result[entity_id]:
            return
        
        items = result[entity_id]["items"]
        
        for item in items:
            # Look for completed items with repeat patterns
            if item.get("status") != "completed":
                continue
            
            summary = item.get("summary", "")
            if not summary:
                continue
            
            # Check if this item has a repeat pattern
            words = summary.split()
            if not words:
                continue
            
            # Look for repeat pattern in the summary
            repeat_pattern = None
            for word in words:
                if word.startswith("[") and word.endswith("]"):
                    repeat_pattern = word
                    break
            
            if not repeat_pattern:
                continue
            
            # Parse the repeat pattern
            repeat_info = parse_repeat_pattern(repeat_pattern)
            if not repeat_info:
                continue
            
            # Get the original due date
            due_date_str = item.get("due")
            if not due_date_str:
                continue
            
            # Parse due date/time
            original_due_date = None
            time_string = ""
            
            try:
                if "T" in due_date_str:
                    # Due datetime format
                    original_due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
                    time_string = original_due_date.strftime("%H:%M")
                else:
                    # Due date only format
                    original_due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
            except ValueError as date_err:
                LOGGER.error("Could not parse due date %s: %s", due_date_str, date_err)
                continue
            
            # Extract original summary (without repeat pattern)
            original_summary = summary.replace(repeat_pattern, "").strip()
            
            # Create new recurring instance
            await create_recurring_task(
                hass, entity_id, original_summary, repeat_info, 
                original_due_date, time_string
            )
            
            # Remove the repeat pattern from the completed task to prevent re-processing
            try:
                await hass.services.async_call(
                    TODO_DOMAIN,
                    "update_item",
                    {
                        "entity_id": entity_id,
                        "item": summary,
                        "rename": original_summary,
                        "status": "completed"
                    },
                    blocking=True
                )
                LOGGER.debug("Cleaned up completed recurring task: %s", original_summary)
            except Exception as cleanup_err:
                LOGGER.error("Error cleaning up completed recurring task: %s", cleanup_err)
    
    except Exception as err:
        LOGGER.error("Error checking for completed recurring tasks: %s", err)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up Todo Magic from a config entry."""
    LOGGER.debug("Setting up Todo Magic integration")

    hass.data.setdefault(DOMAIN, {})

    # Listen for state changes to catch todo items
    LOGGER.debug("Registering state change listener")
    remove_listener = hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        partial(state_changed_listener, hass, entry)
    )

    # Make sure to clean up the listener when unloading
    entry.async_on_unload(remove_listener)

    # Register update listener for options changes
    entry.add_update_listener(options_update_listener)

    # Set up platforms (keeping this empty since we don't need an actual platform)
    LOGGER.debug("Todo Magic setup complete")
    return True


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    return await async_setup_entry(hass, entry)


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    # Unloading is handled by entry.async_on_unload
    return True
