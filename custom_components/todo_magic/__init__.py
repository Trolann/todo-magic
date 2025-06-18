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
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN, TodoListEntity, TodoListEntityFeature, TodoItem

from datetime import datetime, timedelta
import re

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.TODO]

# Simple lock to prevent concurrent processing of the same entity
PROCESSING_LOCKS = set()

# Track completed tasks that have already been processed to prevent duplicates
PROCESSED_COMPLETED_ITEMS = set()

# Track newly created recurring tasks to prevent reprocessing
NEWLY_CREATED_RECURRING_TASKS = set()



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


def schedule_next_occurrence(completion_date: datetime, original_due_date: datetime, repeat_info: dict[str, Any]) -> datetime | None:
    """Calculate the next occurrence date based on repeat pattern and completion timing.
    
    Args:
        completion_date: When the task was completed (today)
        original_due_date: When the task was originally due
        repeat_info: Repeat pattern info from parse_repeat_pattern()
    
    Returns:
        Next occurrence date or None if calculation fails
    """
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
            # Find next day in the pattern sequence after the original due day
            next_weekday = None
            for weekday in target_weekdays:
                if weekday > original_due_weekday:
                    next_weekday = weekday
                    break
            
            if next_weekday is not None:
                # Next occurrence is later in the same week as original due date
                # But calculate from completion date to that day
                days_to_next = next_weekday - completion_weekday
                if days_to_next <= 0:
                    # If that day has already passed this week, go to next cycle
                    days_to_next += 7 + (interval - 1) * 7
                return completion_date_only + timedelta(days=days_to_next)
            else:
                # Next occurrence is first day of next cycle
                days_to_next_cycle = 7 - completion_weekday + target_weekdays[0] + (interval - 1) * 7
                return completion_date_only + timedelta(days=days_to_next_cycle)
    
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


def sort_todo_items_by_due_date(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort todo items by due date with earliest due dates first.
    
    Items without due dates are placed at the end.
    Items with the same due date maintain their relative order.
    
    Args:
        items: List of todo item dictionaries
    
    Returns:
        Sorted list of todo items
    """
    def get_sort_key(item: dict[str, Any]) -> tuple:
        """Generate sort key for todo item."""
        due_str = item.get("due", "")
        
        if not due_str:
            # Items without due dates go to the end
            return (1, "")
        
        try:
            # Parse due date/time
            if "T" in due_str:
                # Due datetime format
                due_date = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                # Convert to naive datetime for comparison
                due_date = due_date.replace(tzinfo=None)
            else:
                # Due date only format
                due_date = datetime.strptime(due_str, "%Y-%m-%d")
            
            # Items with due dates go first, sorted by date
            return (0, due_date)
            
        except (ValueError, TypeError):
            # Invalid due date format, treat as no due date
            LOGGER.warning("Invalid due date format for item: %s", due_str)
            return (1, "")
    
    # Sort items using the sort key
    sorted_items = sorted(items, key=get_sort_key)
    
    LOGGER.debug("Sorted %d items by due date", len(sorted_items))
    return sorted_items


async def apply_auto_sort_if_enabled(hass: HomeAssistant, entity_id: str, settings: dict[str, Any]) -> None:
    """Apply auto-sort to a todo entity if enabled in settings.
    
    Args:
        hass: Home Assistant instance
        entity_id: Todo entity ID to sort
        settings: Entity settings dictionary
    """
    if not settings.get("auto_sort", False):
        LOGGER.debug("Auto-sort disabled for %s, skipping", entity_id)
        return
    
    # Check if already processing this entity to prevent race conditions
    if entity_id in PROCESSING_LOCKS:
        LOGGER.debug("Already processing %s, skipping auto-sort", entity_id)
        return
    
    try:
        # Get current items
        result = await hass.services.async_call(
            TODO_DOMAIN,
            "get_items",
            {"entity_id": entity_id},
            blocking=True,
            return_response=True
        )
        
        if not result or entity_id not in result or "items" not in result[entity_id]:
            LOGGER.debug("No items found for auto-sort: %s", entity_id)
            return
        
        items = result[entity_id]["items"]
        
        if len(items) <= 1:
            LOGGER.debug("Not enough items to sort for %s", entity_id)
            return
        
        # Sort items by due date
        sorted_items = sort_todo_items_by_due_date(items)
        
        # Check if reordering is needed by comparing current vs sorted order
        current_order = [item.get("summary", "") for item in items]
        sorted_order = [item.get("summary", "") for item in sorted_items]
        
        if current_order == sorted_order:
            LOGGER.debug("Items already in correct order for %s", entity_id)
            return
        
        LOGGER.debug("Reordering items for %s: %s -> %s", entity_id, current_order, sorted_order)
        
        # TODO: Manual move detection placeholder
        # Future enhancement: detect if user manually moved items and add "pin" functionality
        # to prevent auto-sorting of manually positioned items
        
        # Use Home Assistant's move_item service for smooth reordering (no UI flicker)
        LOGGER.info("Auto-sort will reorder %s from %s to %s", 
                   entity_id, current_order, sorted_order)
        
        try:
            # Build a mapping of current items by UID for efficient lookups
            current_items_by_uid = {item.get("uid"): item for item in items if item.get("uid")}
            sorted_uids = [item.get("uid") for item in sorted_items if item.get("uid")]
            current_uids = [item.get("uid") for item in items if item.get("uid")]
            
            LOGGER.debug("Current UIDs: %s", current_uids)
            LOGGER.debug("Sorted UIDs: %s", sorted_uids)
            
            # Check if we have UIDs for all items
            if len(sorted_uids) != len(sorted_items):
                LOGGER.warning("Some items missing UIDs, falling back to summary-based reordering")
                # Fallback: use item summary to identify items for move_item service
                # Note: This is less reliable than UIDs but may still work
                
            # Reorder items using move_item service
            moves_made = 0
            previous_uid = None  # First item goes to position 1 (previous_uid=None)
            
            for i, target_item in enumerate(sorted_items):
                target_uid = target_item.get("uid")
                target_summary = target_item.get("summary", "")
                
                if not target_uid and not target_summary:
                    LOGGER.warning("Item has no UID or summary, skipping")
                    continue
                
                # Check if this item is already in the correct position
                current_position = None
                if target_uid and target_uid in current_uids:
                    current_position = current_uids.index(target_uid)
                
                if current_position == i:
                    # Item is already in correct position
                    LOGGER.debug("Item '%s' already in correct position %d", target_summary, i)
                    previous_uid = target_uid
                    continue
                
                # Item needs to be moved
                LOGGER.debug("Moving item '%s' to position %d (after UID: %s)", 
                           target_summary, i, previous_uid)
                
                try:
                    # Try multiple methods to get the actual entity object
                    actual_entity = None
                    
                    # Method 1: Try to get from entity platform
                    try:
                        from homeassistant.helpers import entity_platform
                        platforms = hass.data.get("entity_platform", {})
                        if TODO_DOMAIN in platforms:
                            for platform in platforms[TODO_DOMAIN]:
                                for entity in platform.entities:
                                    if entity.entity_id == entity_id:
                                        actual_entity = entity
                                        break
                                if actual_entity:
                                    break
                    except Exception as e:
                        LOGGER.debug("Method 1 failed: %s", e)
                    
                    # Method 2: Try accessing via domain data
                    if not actual_entity:
                        try:
                            domain_data = hass.data.get(TODO_DOMAIN, {})
                            if isinstance(domain_data, dict):
                                for key, value in domain_data.items():
                                    if hasattr(value, 'entity_id') and value.entity_id == entity_id:
                                        actual_entity = value
                                        break
                        except Exception as e:
                            LOGGER.debug("Method 2 failed: %s", e)
                    
                    # Method 3: Try the entity registry approach
                    if not actual_entity:
                        try:
                            from homeassistant.helpers import entity_registry as er
                            registry = er.async_get(hass)
                            entity_entry = registry.async_get(entity_id)
                            if entity_entry:
                                # Try to find the actual entity through the entity component
                                entity_component = hass.data.get("entity_components", {}).get(TODO_DOMAIN)
                                if entity_component:
                                    actual_entity = entity_component.get_entity(entity_id)
                        except Exception as e:
                            LOGGER.debug("Method 3 failed: %s", e)
                    
                    # Method 4: Fallback to service call if direct entity access fails
                    if not actual_entity:
                        try:
                            LOGGER.debug("Trying service call approach as fallback for %s", entity_id)
                            await hass.services.async_call(
                                TODO_DOMAIN,
                                "move_item",
                                {
                                    "entity_id": entity_id,
                                    "uid": target_uid,
                                    "previous_uid": previous_uid
                                }
                            )
                            moves_made += 1
                            LOGGER.debug("Successfully moved item '%s' via service call", target_summary)
                            
                            # Update our tracking of current order
                            if target_uid and target_uid in current_uids:
                                current_uids.remove(target_uid)
                                current_uids.insert(i, target_uid)
                            previous_uid = target_uid
                            continue
                            
                        except Exception as service_error:
                            LOGGER.error("Could not move todo item %s via service call: %s", target_summary, service_error)
                            LOGGER.error("Could not access todo entity %s using any method", entity_id)
                            continue
                    
                    # Check if the entity supports MOVE_TODO_ITEM
                    if not hasattr(actual_entity, 'supported_features') or \
                       not (actual_entity.supported_features & TodoListEntityFeature.MOVE_TODO_ITEM):
                        LOGGER.warning("Entity %s does not support MOVE_TODO_ITEM feature", entity_id)
                        break
                    
                    LOGGER.debug("Successfully found entity %s, calling async_move_todo_item", entity_id)
                    
                    # Call the move method directly on the entity
                    await actual_entity.async_move_todo_item(
                        uid=target_uid,
                        previous_uid=previous_uid
                    )
                    
                    moves_made += 1
                    LOGGER.debug("Successfully moved item '%s'", target_summary)
                    
                    # Update our tracking of current order
                    if target_uid and target_uid in current_uids:
                        current_uids.remove(target_uid)
                        current_uids.insert(i, target_uid)
                    
                except Exception as move_err:
                    LOGGER.error("Failed to move item '%s': %s", target_summary, move_err)
                    # Check if move_todo_item service doesn't exist
                    if "not found" in str(move_err).lower() or "Unknown service" in str(move_err):
                        LOGGER.warning("move_todo_item service not available, todo provider may not support reordering")
                        break
                    # Continue with other items even if one fails
                
                previous_uid = target_uid
            
            LOGGER.info("Auto-sort completed: made %d moves for %s", moves_made, entity_id)
            
        except Exception as reorder_err:
            LOGGER.error("Error during auto-sort reordering for %s: %s", entity_id, reorder_err)
            
            # If move_item service fails completely, we could fall back to remove/re-add
            # But for now, we'll just log the error and continue
            if "Unknown service" in str(reorder_err) or "not found" in str(reorder_err).lower():
                LOGGER.warning("move_item service not supported by this todo provider")
            else:
                LOGGER.warning("Auto-sort reordering failed, items remain in original order")
        
        LOGGER.info("Auto-sorted %d items for %s", len(sorted_items), entity_id)
        
    except Exception as err:
        LOGGER.error("Error during auto-sort for %s: %s", entity_id, err)


async def apply_auto_sort_after_delay(hass: HomeAssistant, entity_id: str, settings: dict[str, Any]) -> None:
    """Apply auto-sort after a short delay to allow other processing to complete.
    
    Args:
        hass: Home Assistant instance
        entity_id: Todo entity ID to sort
        settings: Entity settings dictionary
    """
    import asyncio
    LOGGER.debug("Auto-sort delayed execution starting for %s", entity_id)
    # Wait a short time to allow other processing to complete
    await asyncio.sleep(1)
    await apply_auto_sort_if_enabled(hass, entity_id, settings)


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
    
    # Create separate background task for auto-sort to run after other processing
    if settings.get("auto_sort", False):
        LOGGER.debug("Triggering auto-sort for %s after state change", entity_id)
        hass.async_create_background_task(
            apply_auto_sort_after_delay(hass, entity_id, settings),
            name=f"todo_magic_auto_sort_{entity_id}"
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
        # Look for items without due dates that contain date patterns OR repeat patterns
        candidates = []
        for item in items:
            if "uid" not in item:
                continue
                
            summary = item.get("summary", "")
            due = item.get("due", "")
            
            # Skip items that already have due dates
            if due:
                continue
            
            # Skip newly created recurring tasks to prevent reprocessing
            task_key = f"{entity_id}:{summary}"
            if task_key in NEWLY_CREATED_RECURRING_TASKS:
                LOGGER.debug("Skipping reprocessing of newly created recurring task: %s", summary)
                continue
                
            # Check if summary contains potential date patterns OR repeat patterns
            cleaned_summary = remove_date_prefixes(summary)
            words = cleaned_summary.split()
            
            # Look for any recognizable date patterns OR repeat patterns
            has_date_pattern = False
            
            # Check individual words first
            for word in words:
                if (parse_natural_language_date(word) or 
                    re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', word) or
                    re.match(r'\d{4}-\d{1,2}-\d{1,2}', word) or
                    parse_repeat_pattern(word)):  # ADD THIS LINE - check for repeat patterns!
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
            
            # Apply auto-sort if enabled
            LOGGER.debug("Triggering auto-sort for %s after processing new item", entity_id)
            await apply_auto_sort_if_enabled(hass, entity_id, settings)
        else:
            LOGGER.debug("No date could be determined for item: %s", summary)

    except Exception as err:
        LOGGER.error("Error processing new todo item: %s", err)
    finally:
        # Always remove the processing lock
        PROCESSING_LOCKS.discard(entity_id)


async def find_duplicate_recurring_task(hass: HomeAssistant, entity_id: str, 
                                       summary_with_pattern: str) -> dict[str, Any] | None:
    """Find existing task with the same summary and repeat pattern.
    
    Args:
        hass: Home Assistant instance
        entity_id: Todo entity ID
        summary_with_pattern: Task summary including repeat pattern
    
    Returns:
        Existing task dict if found, None otherwise
    """
    try:
        result = await hass.services.async_call(
            TODO_DOMAIN,
            "get_items",
            {"entity_id": entity_id},
            blocking=True,
            return_response=True
        )
        
        if not result or entity_id not in result or "items" not in result[entity_id]:
            return None
        
        items = result[entity_id]["items"]
        
        for item in items:
            if item.get("summary") == summary_with_pattern and item.get("status") != "completed":
                return item
        
        return None
        
    except Exception as err:
        LOGGER.error("Error finding duplicate recurring task: %s", err)
        return None


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
        # Calculate next occurrence using completion date and original due date for proper timing logic
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        next_date = schedule_next_occurrence(today, original_due_date, repeat_info)
        if not next_date:
            LOGGER.error("Could not calculate next occurrence for recurring task: %s", original_summary)
            return
        
        LOGGER.debug("Calculated next occurrence from completion date (%s) and original due (%s): %s", 
                    today.strftime('%Y-%m-%d'), original_due_date.strftime('%Y-%m-%d'), next_date.strftime('%Y-%m-%d %H:%M'))
        
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
        
        # Check for duplicate tasks before creating
        existing_task = await find_duplicate_recurring_task(hass, entity_id, new_summary)
        
        # Format next due date
        next_date_str = f'{next_date.year}-{next_date.month:02d}-{next_date.day:02d}'
        
        if existing_task:
            # Task already exists, check if due dates differ
            existing_due = existing_task.get("due", "")
            new_due_datetime = f"{next_date_str} {time_string}" if time_string else next_date_str
            
            if existing_due != new_due_datetime:
                # Due dates differ, update the existing task with new due date
                LOGGER.debug("Updating existing recurring task due date: %s from %s to %s", 
                           new_summary, existing_due, new_due_datetime)
                
                update_item_dict = {
                    "entity_id": entity_id,
                    "item": new_summary,
                    "status": existing_task.get("status", "needs_action"),
                }
                
                if time_string:
                    update_item_dict["due_datetime"] = f"{next_date_str} {time_string}"
                else:
                    update_item_dict["due_date"] = next_date_str
                
                await hass.services.async_call(
                    TODO_DOMAIN,
                    "update_item",
                    update_item_dict,
                    blocking=True
                )
                
                LOGGER.info("Updated recurring task due date: %s", new_summary)
            else:
                # Same task with same due date already exists, skip creation
                LOGGER.debug("Recurring task already exists with same due date: %s", new_summary)
        else:
            # No duplicate found, create the new task
            # Track this as a newly created recurring task to prevent reprocessing
            task_key = f"{entity_id}:{new_summary}"
            NEWLY_CREATED_RECURRING_TASKS.add(task_key)
            
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
            
            # Clean up the tracking after a short delay to prevent permanent accumulation
            # The task should be processed and have its due date set by then
            import asyncio
            def cleanup_tracking():
                NEWLY_CREATED_RECURRING_TASKS.discard(task_key)
            
            # Schedule cleanup in 5 seconds
            hass.loop.call_later(5, cleanup_tracking)
            
            LOGGER.info("Created recurring task: %s", new_summary)
        
        # Apply auto-sort after creating recurring task
        # Need to get settings for this entity
        from homeassistant.config_entries import ConfigEntry
        # Note: We need access to the config entry to get settings, but it's not passed to this function
        # For now, we'll skip auto-sort in recurring task creation and rely on state change listener
        
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
            
            # Create a unique identifier for this completed task
            task_uid = item.get("uid", "")
            if not task_uid:
                # Fallback to summary + due date as identifier
                due_date_str = item.get("due", "")
                task_uid = f"{summary}|{due_date_str}"
            
            # Check if we've already processed this completed task
            task_key = f"{entity_id}:{task_uid}"
            if task_key in PROCESSED_COMPLETED_ITEMS:
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
                    # Convert to naive datetime for comparison (remove timezone info)
                    original_due_date = original_due_date.replace(tzinfo=None)
                else:
                    # Due date only format
                    original_due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
            except ValueError as date_err:
                LOGGER.error("Could not parse due date %s: %s", due_date_str, date_err)
                continue
            
            # Mark this task as processed before creating the new one
            PROCESSED_COMPLETED_ITEMS.add(task_key)
            
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
