# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Todo Magic is a Home Assistant custom integration that automatically parses due dates and times from todo item summaries. It processes natural language date/time patterns in todo text and converts them into proper due date properties.

## Architecture

### Core Components

- **`__init__.py`**: Main integration logic that handles state change listening and todo item processing
- **`config_flow.py`**: Configuration UI flow for per-entity settings and options
- **`const.py`**: Domain constants and configuration
- **`manifest.json`**: Home Assistant integration metadata
- **`translations/en.json`**: UI text translations for configuration interface

### Key Processing Flow

1. Listens for `EVENT_STATE_CHANGED` events on todo entities
2. Processes todo items via `process_todo_items()` function using Home Assistant's `todo.get_items` service
3. Parses date/time patterns from item summaries using `check_date_format()` and `check_time_format()`
4. Updates items via `todo.update_item` service with extracted due dates/times
5. Maintains `PROCESSED_ITEMS` set to prevent duplicate processing

### Date/Time Parsing

The integration supports extensive date formats via `check_date_format()`:
- MM/DD/YY, MM/DD/YYYY patterns
- ISO date formats (YYYY-MM-DD)
- European formats (DD/MM/YYYY, DD-MM-YYYY)
- Time formats: HH:MM, with optional "at" or "@" separators
- Repeat patterns in brackets (future feature): `[d]`, `[w]`, `[m]`, `[y]`

### Configuration System

Uses Home Assistant's options flow to provide per-entity settings with a friendly UI:
- Auto due date parsing (enabled/disabled per todo list) - **IMPLEMENTED**
- Auto-sort functionality (planned)
- Recurring task processing (planned)
- Auto-clear completed tasks (planned)

The config flow has been updated with:
- Clean UI layout with clear descriptions
- Friendly entity names for better user experience
- Per-list configuration options
- Hardcoded English translations (no description parameter needed)

## Development Commands

- **Testing**: Manual testing in Home Assistant development container
- **Development Sync**: `./watch_and_sync.sh` - Automatically sync changes to test environment

Note: This project does not use automated linting or code formatting tools.

## Development Environment

This integration uses the Home Assistant integration blueprint development setup with a containerized Home Assistant instance for testing. The integration follows Home Assistant's custom component patterns and service call conventions.

### Virtual Environment Setup
- Python dependencies are managed via `.venv/` virtual environment
- Key dependencies: `homeassistant`, `colorlog`
- Activate with: `source .venv/bin/activate`

### Development Workflow
- Use `watch_and_sync.sh` for real-time development sync to test instance
- The integration automatically installs as a single instance (prevents multiple config entries)
- Debug logging: Enable `custom_components.todo_magic: debug` in Home Assistant configuration

## Key Implementation Notes

- All todo processing is asynchronous using `hass.async_create_background_task()`
- Uses Home Assistant's service calling system (`hass.services.async_call()`) for todo operations
- Implements proper cleanup via `entry.async_on_unload()` for event listeners
- Follows Home Assistant's config entry and options flow patterns for user configuration

## Next Development Session Plan

### Phase 1: Enhanced Date Parsing
**Goal: Implement natural language date parsing**

#### Tasks:
1. **Extend `check_date_format()` function** to support natural language patterns:
   - `today`, `tomorrow` - relative to current date
   - `5d`, `2w`, `1m`, `1y` - relative duration patterns (days/weeks/months/years)
   - Integration with existing date parsing logic
   
2. **Add utility functions** for natural language processing:
   - `parse_relative_date(text: str) -> datetime | None`
   - `extract_duration_pattern(text: str) -> tuple[int, str] | None`
   - Handle edge cases (weekends, month boundaries, leap years)

3. **Update configuration** to include natural language parsing toggle per list

#### Implementation Details:
- Modify `__init__.py:check_date_format()` to include new patterns
- Add regex patterns for natural language detection
- Ensure backward compatibility with existing date formats
- Add proper error handling and logging

### Phase 2: Smart List Management System
**Goal: Implement automatic task movement based on due date ranges**

#### Tasks:
1. **Extend configuration options** in `config_flow.py`:
   - List type designation (daily/weekly/monthly/normal)
   - Fallback list selection (required for smart lists)
   - Enable/disable smart list management per list

2. **Implement list management logic** in `__init__.py`:
   - `analyze_task_timeframe(due_date: datetime) -> str` - categorize tasks
   - `move_task_to_appropriate_list(item, source_list, target_list)` - handle task movement
   - `get_appropriate_list_for_timeframe(timeframe: str) -> str` - list resolution

3. **Add new processing step** to main flow:
   - Check if task belongs in current list based on due date
   - Move task to appropriate list if mismatch detected
   - Update PROCESSED_ITEMS tracking across list moves
   - Handle cases where no appropriate list exists (use fallback)

#### Configuration Schema Updates:
```python
# Add to const.py
CONF_LIST_TYPE = "list_type"
CONF_FALLBACK_LIST = "fallback_list"
LIST_TYPES = ["normal", "daily", "weekly", "monthly"]
```

### Phase 3: Recurring Task System Implementation
**Goal: Full implementation of repeat patterns with advanced scheduling**

#### Tasks:
1. **Implement repeat pattern parsing**:
   - Parse `[d]`, `[w]`, `[m]`, `[y]` patterns from task text
   - Support advanced patterns like `[w-mwf]` (weekly on specific days)
   - Store repeat information in task metadata or separate tracking

2. **Add recurring task scheduling logic**:
   - `schedule_next_occurrence(item, pattern: str) -> datetime`
   - `create_recurring_task(original_item, next_due_date)`
   - Integration with Home Assistant's scheduling system

3. **Extend configuration** for recurring task management:
   - Enable/disable recurring tasks per list
   - Default repeat behavior settings
   - Cleanup options for completed recurring tasks

### Phase 4: Calendar Integration
**Goal: Associate daily/weekly/monthly lists with calendar items**

#### Tasks:
1. **Add calendar entity discovery**:
   - Scan available calendar entities in Home Assistant
   - Allow association of todo lists with calendar entities in config

2. **Implement calendar synchronization**:
   - Create calendar events for tasks with due dates
   - Sync task completion status with calendar
   - Handle calendar event updates and deletions

3. **Extend configuration UI**:
   - Calendar entity selection for each list
   - Sync direction options (todo->calendar, calendar->todo, bidirectional)
   - Event creation settings (title format, duration, etc.)

### Implementation Priority:
1. **Phase 1** (Natural Language Dates) - Extends existing parsing, high user value
2. **Phase 2** (Smart List Management) - Core workflow improvement
3. **Phase 3** (Recurring Tasks) - Completes existing placeholder functionality  
4. **Phase 4** (Calendar Integration) - Advanced feature, requires careful Home Assistant integration

### Technical Considerations:
- Maintain backward compatibility throughout all phases
- Extensive testing of date/time edge cases
- Proper error handling and user feedback
- Performance optimization for large todo lists
- Home Assistant service call patterns and async handling
- Configuration migration strategies for existing users
- We don't do linting
