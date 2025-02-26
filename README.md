# 📝✨ TODO Magic

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/trolann/todo_magic.svg)](https://github.com/trolann/todo_magic/releases)
[![GitHub License](https://img.shields.io/github/license/trolann/todo_magic.svg)](https://github.com/trolann/todo_magic/blob/main/LICENSE)

Add magical parsing to your Home Assistant to-do lists! This integration automatically extracts due dates and times from your to-do item summaries and converts them into proper due dates in Home Assistant.

## ✨ Features

- 🔍 Automatically parses due dates from your to-do items using a wide variety of date formats
- ⏰ Recognizes and sets due times (defaults to 23:59 if not specified)
- 🧩 Works with any Home Assistant to-do list integration
- 🔄 *(Coming Soon)* Support for recurring tasks with flexible scheduling

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

### 🔄 Repeat Patterns (Coming Soon)

Repeat patterns will allow scheduling recurring tasks:
- `d` - Daily
- `w` - Weekly
- `m` - Monthly
- `y` - Yearly
- `w-mwf` - Weekly on Monday, Wednesday, and Friday

*Note: Repeat functionality is currently under development*

## 🛠️ Installation

### HACS Installation (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed
2. Go to HACS → Integrations → ⋮ (top right) → Custom repositories
3. Add the URL `https://github.com/username/todo-magic` with category "Integration"
4. Click "Add"
5. Find "TODO Magic" in the integrations list and click "Download"
6. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/username/todo-magic/releases)
2. Create a `custom_components/todo_magic` directory in your Home Assistant configuration directory
3. Extract the downloaded files into this directory
4. Restart Home Assistant

## ⚙️ Configuration

No configuration is required! Simply install the integration and it will automatically process all to-do items in your Home Assistant instance.

The default time for items without a specified time is 23:59.

Coming soon: configuration items to set default times.

## 💡 Usage

1. Add to-do items to any Home Assistant to-do list using the syntax shown above
2. When you add a new to-do item, TODO Magic will:
   - Extract the date and time from the summary text
   - Set the proper due date/time properties on the to-do item
   - Rename the to-do item to remove the date/time information
   - Store the repeat information (coming soon)

The integration listens for state changes and processes new to-do items automatically. It also maintains tracking to avoid processing the same item multiple times.

## 🐛 Reporting Issues & Feature Requests

Found a bug or have a great idea for a new feature? Please open an issue on the [GitHub repository](https://github.com/username/todo-magic/issues).

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

This project is licensed under the MIT License - see the [LICENSE](https://github.com/username/todo-magic/blob/main/LICENSE) file for details.

## 🙏 Acknowledgments

- Thanks to the Home Assistant community for their amazing support
- All the contributors who make this project better
- @ludeeus for the HACS integration blueprint
- @kolaente for creating Vikunja which was the inspiration for this project
- @Craftoncu for the `hacs-vikunja-integration` repository which served as a starting point for this project
