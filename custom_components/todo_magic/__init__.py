"""
Custom integration to enhance all Todo lists in Home Assistant.
"""
from __future__ import annotations

import logging
from functools import partial
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN

from datetime import datetime

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.TODO]

# Keep track of items we've already processed to prevent loops
PROCESSED_ITEMS = set()

def check_date_format(given_string) -> datetime | None:
    date_formats = ['%m/%d/%y', '%m/%d/%Y', '%m-%d-%y', '%m-%d-%Y', '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y', '%m-%d-%Y', '%m/%d/%Y', '%m.%d.%Y', '%Y-%d-%m', '%Y/%d/%m', '%Y.%d.%m', '%d-%Y-%m', '%d/%Y/%m', '%d.%Y.%m', '%m-%Y-%d', '%m/%Y/%d', '%m.%Y.%d']
    return check_formats(given_string, date_formats)

def check_time_format(given_string) -> datetime | None:
    time_formats = ['%H:%M', '%H %M', '%H%M']
    return check_formats(given_string, time_formats)

def check_formats(given_string, formats) -> datetime | None:
    for given_format in formats:
        try:
            return_time = datetime.strptime(given_string, given_format)
            return return_time
        except ValueError:
            continue

@callback
def state_changed_listener(hass: HomeAssistant, evt: Event) -> None:
    """Handle state changed events for todo entities."""
    entity_id = evt.data.get("entity_id", "")
    if not entity_id.startswith("todo."):
        return

    new_state = evt.data.get("new_state")
    if not new_state or new_state.state == "unavailable":
        return

    LOGGER.debug("Processing state change for %s", entity_id)

    # Create background task to handle the updates with better tracking
    hass.async_create_background_task(
        process_todo_items(hass, entity_id),
        name=f"todo_magic_update_{entity_id}"
    )

async def process_todo_items(hass: HomeAssistant, entity_id: str) -> None:
    """Process todo items for the given entity."""
    try:
        result = await hass.services.async_call(
            TODO_DOMAIN,
            "get_items",
            {"entity_id": entity_id},
            blocking=True,
            return_response=True
        )

        LOGGER.debug("get_items result: %s", result)

        # Check if result has the correct structure
        if not result or entity_id not in result or "items" not in result[entity_id]:
            LOGGER.debug("No items found for %s", entity_id)
            return

        # Access items correctly through the entity_id key
        items = result[entity_id]["items"]
        LOGGER.debug("Found %d items for %s", len(items), entity_id)

        for item in items:
            if "uid" not in item:
                continue

            # Skip if we've already processed this item
            item_key = f"{entity_id}_{item['uid']}"
            if item_key in PROCESSED_ITEMS:
                continue

            summary = item.get("summary", "")
            due = item.get("due", "")

            LOGGER.debug(f'{item=}')
            # Check if there is a date as one of the last words in the summary. If there is, extract the date, determine if there's a time, and save to variables
            # Check if there's a date object in the summary and determine how many words from the end it is
            summary_split = summary.split()

            current_element = -1
            repeat_string = ""
            time_string = ""
            if summary_split[current_element].startswith("[") and summary_split[current_element].endswith("]"):
                repeat_string = summary_split[current_element]
                current_element -= 1
            due_time = check_time_format(summary_split[current_element])
            if due_time:
                time_string = summary_split[current_element]
                if summary_split[current_element - 1] in ("at", "@"):
                    current_element -= 1
                current_element -= 1

            date_string = check_date_format(summary_split[current_element])
            if date_string:
                date_string = f'{date_string.year}-{date_string.month:02d}-{date_string.day:02d}'
                if not time_string:
                    # default to 23:59
                    due_time = datetime.strptime("23:59", "%H:%M")
                date_index = current_element
                new_summary = f'{" ".join(summary_split[:date_index])} {repeat_string}'
                # Assemble due datetime
                update_item_dict = {
                    "entity_id": entity_id,
                    "item": summary,
                    "rename": f"{new_summary}",
                    "status": item.get("status", "needs_action"),
                }
                if time_string:
                    update_item_dict["due_datetime"] = f"{date_string} {time_string}"
                else:
                    update_item_dict["due_date"] = date_string

                PROCESSED_ITEMS.add(item_key)

                # Using the correct parameters according to service docs
                await hass.services.async_call(
                    TODO_DOMAIN,
                    "update_item",
                    update_item_dict,
                    blocking=True
                )
            else:
                # Already has prefix, but mark as processed
                PROCESSED_ITEMS.add(item_key)
    except Exception as err:
        LOGGER.error("Error processing todo items: %s", err)

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
        partial(state_changed_listener, hass)
    )

    # Make sure to clean up the listener when unloading
    entry.async_on_unload(remove_listener)

    # Set up platforms (keeping this empty since we don't need an actual platform)
    LOGGER.debug("Todo Magic setup complete")
    return True

async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    # Unloading is handled by entry.async_on_unload
    return True
