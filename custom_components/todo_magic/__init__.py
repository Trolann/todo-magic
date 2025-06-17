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
        time_string = ""
        
        # Check bounds before accessing elements
        if len(summary_split) >= abs(current_element) and summary_split[current_element].startswith("[") and summary_split[current_element].endswith("]"):
            repeat_string = summary_split[current_element]
            current_element -= 1
        
        # Check bounds before accessing elements
        if len(summary_split) >= abs(current_element):
            due_time = check_time_format(summary_split[current_element])
            if due_time:
                time_string = summary_split[current_element]
                if len(summary_split) >= abs(current_element - 1) and summary_split[current_element - 1] in ("at", "@"):
                    current_element -= 1
                current_element -= 1

        # Check bounds before accessing elements
        date_string = None
        date_words_used = 1  # Track how many words were used for the date pattern
        
        if len(summary_split) >= abs(current_element):
            # First try single word
            date_string = check_date_format(summary_split[current_element])
            
            # If single word didn't work, try two-word combinations
            if not date_string and len(summary_split) >= abs(current_element - 1):
                two_words = f"{summary_split[current_element - 1]} {summary_split[current_element]}"
                date_string = check_date_format(two_words)
                if date_string:
                    date_words_used = 2
            
        if date_string:
            LOGGER.debug("Found date in new item: %s", date_string)
            date_string = f'{date_string.year}-{date_string.month:02d}-{date_string.day:02d}'
            if not time_string:
                # default to 23:59
                due_time = datetime.strptime("23:59", "%H:%M")
            date_index = current_element - (date_words_used - 1)
            new_summary = f'{" ".join(summary_split[:date_index])} {repeat_string}'.strip()
            
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
        else:
            LOGGER.debug("No date pattern found in new item: %s", summary)

    except Exception as err:
        LOGGER.error("Error processing new todo item: %s", err)
    finally:
        # Always remove the processing lock
        PROCESSING_LOCKS.discard(entity_id)


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
