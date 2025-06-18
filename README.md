# 📝✨ TODO Magic

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/trolann/todo-magic.svg)](https://github.com/trolann/todo-magic/releases)
[![GitHub License](https://img.shields.io/github/license/trolann/todo-magic.svg)](https://github.com/trolann/todo-magic/blob/main/LICENSE)

Add magical parsing to your Home Assistant to-do lists! This integration automatically extracts due dates and times from your to-do item summaries and converts them into proper due dates in Home Assistant.

## ✨ Features

- 🔍 **Auto Due Date Parsing**: Automatically parses due dates from your to-do items using a wide variety of date formats
- ⏰ **Time Recognition**: Recognizes and sets due times (defaults to 23:59 if not specified)
- 🔄 **Recurring Tasks**: Full support for recurring tasks with flexible scheduling patterns
- 📊 **Auto-Sort**: Automatically sorts tasks by due date within individual lists
- 📅 **Smart Lists**: Intelligent task management across multiple lists based on due date ranges
- 🧹 **Auto-Clear**: Automatically remove completed tasks after a configurable number of days
- 🧩 **Universal Compatibility**: Works with any Home Assistant to-do list integration
- ⚙️ **Per-List Configuration**: Granular settings with friendly UI for each todo list

## 📋 Syntax

```
<todo summary/title> <due date> <optionally 'at' or '@'> <due time (defaults to 23:59)> <repeat pattern>
```

### Examples:

- `Buy groceries 2/28/25 [w]` → Due on Feb 28, 2025 at 23:59; repeating every 7 days
- `Call mom 3/1/25 @ 17:00` → Due on Mar 1, 2025 at 5:00 PM
- `Take out trash 3/5/25 at 8:00` → Due on Mar 5, 2025 at 8:00 AM
- `Submit report 2025-03-15` → Due on Mar 15, 2025 at 23:59

### Date Formats

The component accepts a wide variety of date formats:
- MM/DD/YY (e.g., 3/5/25)
- MM/DD/YYYY (e.g., 3/5/2025)
- MM-DD-YY, MM-DD-YYYY
- YYYY-MM-DD (e.g., 2025-03-05)
- YYYY/MM/DD, YYYY.MM.DD
- DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY
- And many other variations!

### Natural Language Dates

- `today` - Today's date
- `tomorrow` - Tomorrow's date
- `5d` - 5 days from now
- `2w` - 2 weeks from now
- `1m` - 1 month from now
- `1y` - 1 year from now

### 🔄 Repeat Patterns

Repeat patterns allow scheduling recurring tasks:
- `[d]` - Daily
- `[w]` - Weekly  
- `[m]` - Monthly
- `[y]` - Yearly
- `[w-mwf]` - Weekly on Monday, Wednesday, and Friday
- `[2w]` - Every 2 weeks
- `[3m]` - Every 3 months

When you complete a recurring task, TODO Magic automatically schedules the next occurrence based on the repeat pattern.

## 🛠️ Installation

### HACS Installation (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed
2. Go to HACS → Integrations → ⋮ (top right) → Custom repositories
3. Add the URL `https://github.com/trolann/todo-magic` with category "Integration"
4. Click "Add"
5. Find "TODO Magic" in the integrations list and click "Download"
6. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/trolann/todo-magic/releases)
2. Create a `custom_components/todo_magic` directory in your Home Assistant configuration directory
3. Extract the downloaded files into this directory
4. Restart Home Assistant

## ⚙️ Configuration

After installation, you can configure TODO Magic through the Home Assistant UI:

1. Go to Settings → Devices & Services → Integrations
2. Find "TODO Magic" and click "Configure"

### Configuration Options

**🧠 Smart Lists** (Global Setting)
Enable intelligent task management across multiple todo lists. When enabled, you'll configure:
- **Daily List**: Tasks due today or overdue
- **Weekly List**: Tasks due within the next 7 days  
- **Monthly List**: Tasks due within the next 30 days
- **Fallback List**: Required - where tasks go if they don't match any timeframe

Smart Lists automatically:
- Replicate new tasks to appropriate lists based on due dates
- Move tasks between lists when due dates change
- Sync completion status across all lists
- Clean up old completed tasks automatically

**📋 Per-List Settings**
Configure each todo list individually:
- **Auto Due Date Parsing**: Enable/disable automatic date parsing
- **Auto-Sort**: Automatically sort items by due date (earliest first)
- **Process Recurring Tasks**: Enable repeat pattern processing
- **Auto-Clear Completed**: Remove completed items after specified days (-1 to disable, 0 for immediate clearing, 1+ for days to wait)

### Smart Lists Explained

Smart Lists provide intelligent task distribution:

- **Daily Lists** show tasks due today or overdue - perfect for morning reviews
- **Weekly Lists** display all tasks for the current week - great for weekly planning  
- **Monthly Lists** contain tasks for the entire month - ideal for long-term visibility
- **Fallback Lists** catch everything else - your general inbox

When you add a task like "Meeting tomorrow 2pm", it automatically appears in:
- The list where you created it
- Your Daily List (if tomorrow is within 1 day)
- Your Weekly List (if configured)

When you complete it in any list, it's marked complete everywhere.

### Auto-Clear Behavior

The Auto-Clear feature automatically removes completed tasks based on their age:

- **Midnight Scheduler**: Runs daily at 00:00:00 to check for tasks to clear
- **Age Calculation**: Based on the task's due date (completion date if available)
- **Configuration Options**:
  - `-1`: Disabled (no auto-clearing)
  - `0`: Clear completed tasks immediately (next midnight after completion)
  - `1+`: Keep completed tasks for N days, then clear them

**Examples**:
- Daily Lists: Set to `1` to clear completed tasks after 1 day
- Weekly Lists: Set to `7` to clear completed tasks after 1 week  
- Monthly Lists: Set to `30` to clear completed tasks after 1 month
- Archive Lists: Set to `-1` to never auto-clear

### Usage Tips

- Use Smart Lists for time-based task management across multiple todo apps/lists
- Enable Auto-Sort to keep your lists organized by due date
- Set different Auto-clear periods for different list types (e.g., 1 day for daily lists, 30 days for monthly lists)
- Use Auto-Clear to maintain clean lists without manual maintenance

## 💡 Usage

### Basic Usage
1. Add to-do items to any Home Assistant to-do list using the syntax shown above
2. When you add a new to-do item, TODO Magic will:
   - Extract the date and time from the summary text
   - Set the proper due date/time properties on the to-do item
   - Remove the date/time information from the task name
   - Process any repeat patterns for recurring tasks
   - Apply auto-sorting if enabled
   - Replicate to Smart Lists if configured
3. Daily at midnight, TODO Magic will:
   - Check all lists with auto-clear enabled
   - Remove completed tasks older than the configured retention period
   - Keep your lists clean automatically

### Smart Lists Workflow
1. **Create Lists**: Set up your daily, weekly, and monthly todo lists in Home Assistant
2. **Configure Smart Lists**: Enable Smart Lists and assign your lists to each timeframe
3. **Add Tasks**: Create tasks in any list - they'll automatically appear in relevant Smart Lists
4. **Stay Organized**: Tasks move between lists as due dates approach, and completed tasks sync everywhere

### Auto-Sort Behavior
- Tasks are sorted by due date (earliest first)
- Tasks without due dates appear at the bottom
- Manual positioning is not preserved when new tasks are added or completed
- Sorting applies automatically after any task changes

### Recurring Tasks
- Add repeat patterns in brackets: `[d]`, `[w]`, `[m]`, `[y]`
- When you mark a recurring task complete, the next occurrence is automatically scheduled
- Advanced patterns supported: `[w-mwf]`, `[2w]`, `[3m]`, etc.

The integration listens for state changes and processes new to-do items automatically. It maintains tracking to avoid processing the same item multiple times.

## 🚀 Future Enhancements

### Calendar Integration *(Planned)*
Associate daily, weekly, and monthly lists with Home Assistant calendar entities for enhanced scheduling and visualization:
- Create calendar events for tasks with due dates
- Sync task completion status with calendar events  
- Bidirectional synchronization between calendars and todo lists
- Configurable event creation settings (title format, duration, etc.)

### Additional Features *(Under Consideration)*
- **Smart date context awareness**: Better recognition of ambiguous dates
- **Task dependencies**: Link tasks together with prerequisite relationships
- **Priority-based sorting**: Sort by priority in addition to due dates
- **Bulk operations**: Mass edit multiple tasks at once

## 🐛 Reporting Issues & Feature Requests

Found a bug or have a great idea for a new feature? Please open an issue on the [GitHub repository](https://github.com/trolann/todo-magic/issues).

When reporting bugs, please include:
- A clear description of what happened vs. what you expected
- Steps to reproduce the issue
- Your Home Assistant version
- A sample of the to-do item text that's not working correctly
- Any relevant log entries (you can enable debug logging for this component)

### Enabling Debug Logging

Add the following to your `configuration.yaml` to enable debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.todo_magic: debug
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/trolann/todo-magic/blob/main/LICENSE) file for details.

## 🙏 Acknowledgments

- Thanks to the Home Assistant community for their amazing support
- All the contributors who make this project better
- @ludeeus for the HACS integration blueprint
- @kolaente for creating Vikunja which was the inspiration for this project
- @Craftoncu for the `hacs-vikunja-integration` repository which served as a starting point for this project
