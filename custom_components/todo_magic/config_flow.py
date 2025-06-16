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

        # Sort entities by friendly name for better organization
        todo_entities.sort(key=lambda x: x[1])

        for entity_id, friendly_name in todo_entities:
            entity_key = entity_id.replace(".", "_")
            
            # Auto-due date parsing with friendly name
            schema_dict[vol.Optional(
                f"{entity_key}_auto_due_parsing",
                default=current_options.get(f"{entity_key}_auto_due_parsing", True),
                description=f"{friendly_name}: Auto Due Date Parsing"
            )] = selector.BooleanSelector()
            
            # Auto-sort with friendly name
            schema_dict[vol.Optional(
                f"{entity_key}_auto_sort",
                default=current_options.get(f"{entity_key}_auto_sort", False),
                description=f"{friendly_name}: Auto Sort Tasks"
            )] = selector.BooleanSelector()
            
            # Process recurring tasks with friendly name
            schema_dict[vol.Optional(
                f"{entity_key}_process_recurring",
                default=current_options.get(f"{entity_key}_process_recurring", False),
                description=f"{friendly_name}: Process Recurring Tasks"
            )] = selector.BooleanSelector()
            
            # Clear todolist every X days with friendly name
            clear_days_default = current_options.get(f"{entity_key}_clear_days", -1)
            schema_dict[vol.Optional(
                f"{entity_key}_clear_days",
                default=clear_days_default,
                description=f"{friendly_name}: Auto-Clear Days (-1=disabled, 0=immediate, 1+=days)"
            )] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-1,
                    max=365,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX
                )
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "todo_count": str(len(todo_entities))
            },
        )
