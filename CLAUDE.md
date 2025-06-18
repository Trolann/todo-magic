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

### Date/Time Parsing - **COMPLETED**

The integration supports extensive date formats via `check_date_format()` and `parse_natural_language_date()`:

- MM/DD/YY, MM/DD/YYYY patterns and many format variations
- ISO date formats (YYYY-MM-DD)
- European formats (DD/MM/YYYY, DD-MM-YYYY)
- Natural language patterns: `today`, `tomorrow`
- Relative duration patterns: `5d`, `2w`, `1m`, `1y` (days/weeks/months/years)
- Flexible word forms: `5 days`, `2 weeks`, `1 month`, `1 year`
- Time formats: HH:MM, with optional "at" or "@" separators
- Text prefixes: Handles "in" and ":" prefixes (e.g., "wash clothes in 5d")
- Repeat patterns in brackets: `[d]`, `[w]`, `[m]`, `[y]`, `[w-mwf]` - **FULLY IMPLEMENTED**

### Configuration System

Uses Home Assistant's options flow to provide per-entity settings with a friendly UI:

- Auto due date parsing (enabled/disabled per todo list) - **IMPLEMENTED**
- Auto-sort functionality (Phase 1 - next priority)
- Smart list management (Phase 2 - planned)
- Recurring task processing - **IMPLEMENTED** (with minor bug noted below)
- Auto-clear completed tasks (planned)

The config flow has been updated with:

- Clean UI layout with clear descriptions
- Friendly entity names for better user experience
- Per-list configuration options
- Hardcoded English translations (no description parameter needed)

## Development Commands

- **Testing**: Manual testing in Home Assistant development container
- **Development Sync**: `./watch_and_sync.sh` - Automatically sync changes to test environment
- **Python**: Use `python3` for all Python operations
- **Unit Testing**: Run tests with `python3 tests/test_<module>.py` for isolated logic testing
- **Test Examples**:
  - `python3 tests/test_natural_dates.py` - Natural language date parsing
  - `python3 tests/test_repeat_patterns.py` - Repeat pattern parsing and scheduling
  - `python3 tests/test_repeatability_complete.py` - Comprehensive recurring task testing
  - `python3 tests/test_comprehensive_repeat_patterns.py` - Advanced repeat pattern edge cases
- **Debug Scripts**: Individual debug scripts available for specific pattern testing:
  - `python3 debug_patterns.py` - Debug specific date/time patterns
  - `python3 debug_removal.py` - Debug text removal patterns
  - `python3 debug_word_forms.py` - Debug word form variations

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

We're actually going to do Phase 3, 1, 2 order instead of 1,2,3. It's fine.

### Phase 1: Auto-Sorting System - **COMPLETED**

**Goal: Implement automatic task sorting within individual todo lists**

**Status: Fully implemented and tested**

#### Completed Features

1. **Configuration options** in `config_flow.py` - ✅ **DONE**:
   - Enable/disable auto-sorting per todo list
   - Sort criteria selection (due date, priority, alphabetical, creation date)
   - Sort direction (ascending/descending)

2. **Sorting logic** in `__init__.py` - ✅ **DONE**:
   - `sort_todo_items(items: list, sort_criteria: str, direction: str) -> list` - core sorting function
   - `apply_auto_sort(entity_id: str)` - apply sorting to specific list
   - Integration with existing todo processing flow
   - Fixed entity access for `async_move_todo_item()` calls

3. **Processing step integration** - ✅ **DONE**:
   - Auto-sort triggers after date/time processing and repeat pattern handling
   - Proper task order management and reordering via TodoListEntity methods
   - Multiple entity access methods with fallback approaches

#### Known Bug

- **Manual sort position not preserved**: When manually moving/sorting a task, the location it is manually moved to is not saved. Any new/complete tasks will cause it to be sorted by date, overriding manual positioning.

### Phase 2: Smart List Management System

**Goal: Implement automatic task movement between todo lists based on due date ranges**

#### Tasks

1. **Extend configuration options** in `config_flow.py`:
   - List type designation (daily/weekly/monthly/normal)
   - Fallback list selection (required for smart lists)
   - Enable/disable smart list management per list

2. **Implement list management logic** in `__init__.py`:
   - `analyze_task_timeframe(due_date: datetime) -> str` - categorize tasks by timeframe
   - `move_task_to_appropriate_list(item, source_list, target_list)` - handle task movement
   - `get_appropriate_list_for_timeframe(timeframe: str) -> str` - list resolution logic

3. **Add smart list processing step** to main flow:
   - Check if task belongs in current list based on due date
   - Move task to appropriate list if mismatch detected
   - Update PROCESSED_ITEMS tracking across list moves
   - Handle cases where no appropriate list exists (use fallback)

#### Configuration Schema Updates

```python
# Add to const.py
CONF_LIST_TYPE = "list_type"
CONF_FALLBACK_LIST = "fallback_list"
CONF_SMART_LISTS = "smart_lists"
LIST_TYPES = ["normal", "daily", "weekly", "monthly"]
```

### Phase 3: Calendar Integration

**Goal: Associate daily/weekly/monthly lists with calendar items**

#### Tasks

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

### Phase 4: Recurring Task System Implementation - **COMPLETED**

**Status: Fully implemented with minor bug**

#### Completed Features

1. **Repeat pattern parsing** - ✅ **DONE**:
   - Parse `[d]`, `[w]`, `[m]`, `[y]` patterns from task text
   - Support advanced patterns like `[w-mwf]` (weekly on specific days)
   - Full integration with existing date parsing system

2. **Recurring task scheduling logic** - ✅ **DONE**:
   - `schedule_next_occurrence(item, pattern: str) -> datetime` implemented
   - Automatic due date advancement when tasks are completed
   - Integration with Home Assistant's todo system

#### Known Bug

- **Multi-week repeat advancement**: For patterns like `[w-mwf]` and `[w]`, repeatedly completing tasks only advances to the next occurrence within the current cycle, but doesn't properly advance to subsequent weeks/months/years after the current cycle completes. The logic correctly finds the next Monday/Wednesday/Friday but may not advance to the following week's Monday/Wednesday/Friday when all current week occurrences are exhausted.

### Implementation Priority

1. **Phase 1** (Auto-Sorting) - **NEXT TASK** - Automatic task sorting within individual lists
2. **Phase 2** (Smart List Management) - Task movement between lists based on due dates
3. **Phase 3** (Calendar Integration) - Advanced feature for broader productivity workflow
4. **Phase 4** (Recurring Tasks) - ✅ **COMPLETED** (minor bug to be addressed later)

### Technical Considerations

- Maintain backward compatibility throughout all phases
- Extensive testing of date/time edge cases
- Proper error handling and user feedback
- Performance optimization for large todo lists
- Home Assistant service call patterns and async handling
- Configuration migration strategies for existing users
- We don't do linting

## Testing and Debugging

### Testing Structure
- **Unit Tests**: Standalone test files in `tests/` directory that don't import `homeassistant` module
- **Test Approach**: Copy functions to test or import specific functions, avoiding full Home Assistant dependencies
- **Test Categories**:
  - Date/time parsing validation
  - Repeat pattern logic verification
  - Edge case handling and error conditions
  - Comprehensive integration scenarios

### Debugging and Logging
- **Container Logs**: `docker logs --since $(docker inspect -f '{{.State.StartedAt}}' ha_vikunja) ha_vikunja`
- **Debug Logging**: Enable `custom_components.todo_magic: debug` in Home Assistant configuration
- **Live Development**: Use `./watch_and_sync.sh` for real-time code synchronization

### Current Test Coverage
- ✅ Natural language date parsing (`test_natural_dates.py`)
- ✅ Repeat pattern parsing and scheduling (`test_repeat_patterns.py`)
- ✅ Comprehensive recurring task scenarios (`test_repeatability_complete.py`)
- ✅ Advanced repeat pattern edge cases (`test_comprehensive_repeat_patterns.py`)

## Memories

- Don't worry about git
- Create simpler tests that don't import the `homeassistant` module
- Next development session: Focus on Phase 1 (Auto-Sorting) - sorting tasks within individual lists
