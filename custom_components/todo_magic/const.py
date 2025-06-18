"""Constants for integration_blueprint."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "todo_magic"
ATTRIBUTION = "Template from @ludeeus. Magic syntax inspired by Vikunja."

# Smart list configuration constants
CONF_DAILY_LIST = "daily_smart_list"
CONF_WEEKLY_LIST = "weekly_smart_list"
CONF_MONTHLY_LIST = "monthly_smart_list"
CONF_FALLBACK_LIST = "fallback_list"
CONF_ENABLE_SMART_LISTS = "enable_smart_lists"
