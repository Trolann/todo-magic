#!/usr/bin/env python3
"""
Test script for smart list migration functionality.
This tests the core logic without Home Assistant dependencies.
"""

import sys
import os
from datetime import datetime, timedelta

# Add the custom component path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components', 'todo_magic'))

# Import the functions we want to test
from __init__ import analyze_task_timeframe, get_smart_list_for_timeframe

def test_analyze_task_timeframe():
    """Test the timeframe analysis function."""
    print("Testing analyze_task_timeframe...")
    
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Test today
    assert analyze_task_timeframe(today) == 'today', "Today's task should be 'today'"
    print("✓ Today task correctly identified")
    
    # Test tomorrow (should be this_week)
    tomorrow = today + timedelta(days=1)
    result = analyze_task_timeframe(tomorrow)
    print(f"Tomorrow timeframe: {result}")
    
    # Test this week
    in_3_days = today + timedelta(days=3)
    result = analyze_task_timeframe(in_3_days)
    print(f"In 3 days timeframe: {result}")
    
    # Test this month
    in_15_days = today + timedelta(days=15)
    result = analyze_task_timeframe(in_15_days)
    print(f"In 15 days timeframe: {result}")
    
    # Test other (far future)
    next_year = today + timedelta(days=400)
    result = analyze_task_timeframe(next_year)
    assert result == 'other', "Far future task should be 'other'"
    print("✓ Far future task correctly identified as 'other'")

def test_get_smart_list_for_timeframe():
    """Test the smart list selection function."""
    print("\nTesting get_smart_list_for_timeframe...")
    
    smart_config = {
        'enable_smart_lists': True,
        'daily_list': 'todo.daily',
        'weekly_list': 'todo.weekly', 
        'monthly_list': 'todo.monthly',
        'fallback_list': 'todo.fallback'
    }
    
    # Test timeframe mapping
    assert get_smart_list_for_timeframe('today', smart_config) == 'todo.daily'
    print("✓ Today maps to daily list")
    
    assert get_smart_list_for_timeframe('this_week', smart_config) == 'todo.weekly'
    print("✓ This week maps to weekly list")
    
    assert get_smart_list_for_timeframe('this_month', smart_config) == 'todo.monthly'
    print("✓ This month maps to monthly list")
    
    assert get_smart_list_for_timeframe('other', smart_config) is None
    print("✓ Other timeframe returns None (should use fallback)")
    
    # Test disabled smart lists
    disabled_config = {'enable_smart_lists': False}
    assert get_smart_list_for_timeframe('today', disabled_config) is None
    print("✓ Disabled smart lists return None")

def test_migration_scenario():
    """Test a realistic migration scenario."""
    print("\nTesting migration scenario...")
    
    # Simulate tasks that were in fallback but are now due today
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Task that was due "in 3 days" but is now due today
    task_due_today = today
    timeframe = analyze_task_timeframe(task_due_today)
    print(f"Task due today gets timeframe: {timeframe}")
    
    smart_config = {
        'enable_smart_lists': True,
        'daily_list': 'todo.daily',
        'weekly_list': 'todo.weekly', 
        'monthly_list': 'todo.monthly',
        'fallback_list': 'todo.fallback'
    }
    
    target_list = get_smart_list_for_timeframe(timeframe, smart_config)
    print(f"Should move to list: {target_list}")
    
    assert target_list == 'todo.daily', "Task due today should move to daily list"
    print("✓ Migration logic works correctly")

if __name__ == "__main__":
    try:
        test_analyze_task_timeframe()
        test_get_smart_list_for_timeframe() 
        test_migration_scenario()
        print("\n🎉 All tests passed! Smart list migration logic is working correctly.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)