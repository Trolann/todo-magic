"""Config flow for Todo Magic integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


class MagicTodoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Todo Magic."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Todo Magic", data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MagicTodoOptionsFlowHandler:
        """Create the options flow."""
        return MagicTodoOptionsFlowHandler(config_entry)


class MagicTodoOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Todo Magic."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.user_input = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the main settings form with entity selectors."""
        if user_input is not None:
            # Store the user input and check if we need auto-clear configuration
            self.user_input = user_input
            auto_clear_entities = user_input.get("auto_clear_entities", [])
            
            if auto_clear_entities:
                # Proceed to auto-clear configuration step
                return await self.async_step_auto_clear_config()
            else:
                # No auto-clear entities, convert and finish
                converted_options = self._convert_selections_to_entity_options(user_input)
                return self.async_create_entry(title="", data=converted_options)

        # Check if we have todo entities
        todo_entity_ids = [eid for eid in self.hass.states.async_entity_ids(TODO_DOMAIN)
                          if self.hass.states.get(eid) and self.hass.states.get(eid).state != "unavailable"]
        
        LOGGER.debug("Found todo entities: %s", todo_entity_ids)
        
        if not todo_entity_ids:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors={"base": "no_todo_entities"},
            )

        # Get current selections from existing options
        current_selections = self._get_current_selections_from_options()
        LOGGER.debug("Current selections: %s", current_selections)

        # Filter current selections to only include valid entities
        valid_selections = self._filter_valid_entities(current_selections, todo_entity_ids)
        LOGGER.debug("Valid selections: %s", valid_selections)
        
        # Build schema with entity selectors for each feature
        schema_dict = {
            # Auto Due Date Parsing
            vol.Optional(
                "auto_due_parsing_entities",
                default=valid_selections.get("auto_due_parsing_entities", [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=TODO_DOMAIN,
                    multiple=True
                )
            ),
            
            # Auto Sort
            vol.Optional(
                "auto_sort_entities",
                default=valid_selections.get("auto_sort_entities", [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=TODO_DOMAIN,
                    multiple=True
                )
            ),
            
            # Process Recurring Tasks
            vol.Optional(
                "process_recurring_entities",
                default=valid_selections.get("process_recurring_entities", [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=TODO_DOMAIN,
                    multiple=True
                )
            ),
            
            # Auto-clear settings
            vol.Optional(
                "auto_clear_entities",
                default=valid_selections.get("auto_clear_entities", [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=TODO_DOMAIN,
                    multiple=True
                )
            ),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "todo_count": str(len(todo_entity_ids))
            },
        )
    
    async def async_step_auto_clear_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure individual day settings for auto-clear entities."""
        if user_input is not None:
            # Merge the auto-clear configuration with the original input
            merged_input = self.user_input.copy()
            merged_input.update(user_input)
            
            # Convert and finish
            converted_options = self._convert_selections_to_entity_options(merged_input)
            return self.async_create_entry(title="", data=converted_options)
        
        # Get the selected auto-clear entities from the previous step
        auto_clear_entities = self.user_input.get("auto_clear_entities", [])
        
        if not auto_clear_entities:
            # No entities selected, skip this step
            converted_options = self._convert_selections_to_entity_options(self.user_input)
            return self.async_create_entry(title="", data=converted_options)
        
        # Get current day settings for these entities
        current_day_settings = self._get_current_auto_clear_days(auto_clear_entities)
        
        # Build schema for each auto-clear entity
        schema_dict = {}
        entity_descriptions = {}
        
        for entity_id in auto_clear_entities:
            state = self.hass.states.get(entity_id)
            if state:
                friendly_name = state.attributes.get("friendly_name", entity_id)
                entity_key = self._entity_id_to_key(entity_id)
                
                schema_dict[vol.Optional(
                    f"{entity_key}_clear_days",
                    default=current_day_settings.get(entity_id, 7)
                )] = selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-1,
                        max=365,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX
                    )
                )
                
                # Add description for this entity
                entity_descriptions[f"{entity_key}_clear_days"] = f"Days to keep completed tasks in {friendly_name}"
        
        return self.async_show_form(
            step_id="auto_clear_config",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "entity_count": str(len(auto_clear_entities)),
                **entity_descriptions
            },
        )
    
    def _get_current_selections_from_options(self) -> dict[str, Any]:
        """Convert current per-entity options back to entity lists."""
        current_options = self.config_entry.options
        selections = {
            "auto_due_parsing_entities": [],
            "auto_sort_entities": [],
            "process_recurring_entities": [],
            "auto_clear_entities": []
        }
        
        # Get all actual todo entities to use for validation
        all_todo_entities = [eid for eid in self.hass.states.async_entity_ids(TODO_DOMAIN)
                            if self.hass.states.get(eid) and self.hass.states.get(eid).state != "unavailable"]
        
        # Convert individual entity settings back to lists
        for key, value in current_options.items():
            if "_auto_due_parsing" in key and value:
                entity_id = self._key_to_entity_id(key.replace("_auto_due_parsing", ""), all_todo_entities)
                if entity_id:
                    selections["auto_due_parsing_entities"].append(entity_id)
            elif "_auto_sort" in key and value:
                entity_id = self._key_to_entity_id(key.replace("_auto_sort", ""), all_todo_entities)
                if entity_id:
                    selections["auto_sort_entities"].append(entity_id)
            elif "_process_recurring" in key and value:
                entity_id = self._key_to_entity_id(key.replace("_process_recurring", ""), all_todo_entities)
                if entity_id:
                    selections["process_recurring_entities"].append(entity_id)
            elif "_clear_days" in key and isinstance(value, int) and value >= 0:
                entity_id = self._key_to_entity_id(key.replace("_clear_days", ""), all_todo_entities)
                if entity_id:
                    selections["auto_clear_entities"].append(entity_id)
        
        return selections
    
    def _filter_valid_entities(self, selections: dict[str, Any], valid_entities: list[str]) -> dict[str, Any]:
        """Filter selections to only include entities that currently exist."""
        filtered = {}
        for key, entity_list in selections.items():
            if isinstance(entity_list, list):
                filtered[key] = [eid for eid in entity_list if eid in valid_entities]
            else:
                filtered[key] = entity_list
        return filtered
    
    def _entity_id_to_key(self, entity_id: str) -> str:
        """Convert entity ID to option key."""
        return entity_id.replace(".", "_")
    
    def _key_to_entity_id(self, key: str, all_entities: list[str]) -> str | None:
        """Convert option key back to entity ID by matching against known entities."""
        # Try direct conversion first
        candidate = key.replace("_", ".")
        if candidate in all_entities:
            return candidate
        
        # If that doesn't work, try to find a matching entity
        for entity_id in all_entities:
            if self._entity_id_to_key(entity_id) == key:
                return entity_id
        
        LOGGER.warning("Could not find entity for key: %s", key)
        return None
    
    def _get_current_auto_clear_days(self, entity_ids: list[str]) -> dict[str, int]:
        """Get current day settings for auto-clear entities."""
        current_options = self.config_entry.options
        day_settings = {}
        
        for entity_id in entity_ids:
            entity_key = self._entity_id_to_key(entity_id)
            clear_days_key = f"{entity_key}_clear_days"
            day_settings[entity_id] = current_options.get(clear_days_key, 7)
        
        return day_settings
    
    def _convert_selections_to_entity_options(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Convert entity list selections to individual entity options."""
        options = {}
        
        # Get all todo entities for reference
        all_todo_entities = [eid for eid in self.hass.states.async_entity_ids(TODO_DOMAIN)
                            if self.hass.states.get(eid) and self.hass.states.get(eid).state != "unavailable"]
        
        # Convert each entity selection to individual settings
        for entity_id in all_todo_entities:
            entity_key = self._entity_id_to_key(entity_id)
            
            # Auto due parsing
            options[f"{entity_key}_auto_due_parsing"] = entity_id in user_input.get("auto_due_parsing_entities", [])
            
            # Auto sort
            options[f"{entity_key}_auto_sort"] = entity_id in user_input.get("auto_sort_entities", [])
            
            # Process recurring
            options[f"{entity_key}_process_recurring"] = entity_id in user_input.get("process_recurring_entities", [])
            
            # Auto clear - check for individual day setting
            if entity_id in user_input.get("auto_clear_entities", []):
                # Look for individual day setting for this entity
                day_key = f"{entity_key}_clear_days"
                if day_key in user_input:
                    options[f"{entity_key}_clear_days"] = user_input[day_key]
                else:
                    options[f"{entity_key}_clear_days"] = 7  # Default
            else:
                options[f"{entity_key}_clear_days"] = -1
        
        return options
