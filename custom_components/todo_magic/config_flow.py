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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get all todo entities
        todo_entities = []
        for entity_id in self.hass.states.async_entity_ids(TODO_DOMAIN):
            state = self.hass.states.get(entity_id)
            if state:
                friendly_name = state.attributes.get("friendly_name", entity_id)
                todo_entities.append((entity_id, friendly_name))

        if not todo_entities:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                description_placeholders={"error": "No todo entities found"},
            )

        # Build schema dynamically based on available todo entities
        schema_dict = {}
        current_options = self.config_entry.options

        for entity_id, friendly_name in todo_entities:
            entity_key = entity_id.replace(".", "_")
            
            # Auto-due date parsing
            schema_dict[vol.Optional(
                f"{entity_key}_auto_due_parsing",
                default=current_options.get(f"{entity_key}_auto_due_parsing", True)
            )] = bool
            
            # Auto-sort
            schema_dict[vol.Optional(
                f"{entity_key}_auto_sort",
                default=current_options.get(f"{entity_key}_auto_sort", False)
            )] = bool
            
            # Process recurring tasks
            schema_dict[vol.Optional(
                f"{entity_key}_process_recurring",
                default=current_options.get(f"{entity_key}_process_recurring", False)
            )] = bool
            
            # Clear todolist every X days
            schema_dict[vol.Optional(
                f"{entity_key}_clear_days",
                default=current_options.get(f"{entity_key}_clear_days", 0)
            )] = vol.All(int, vol.Range(min=0))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "todo_entities": ", ".join([name for _, name in todo_entities])
            },
        )
