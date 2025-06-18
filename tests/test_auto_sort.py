#!/usr/bin/env python3
"""
Test script for auto-sort functionality.
This script tests the todo item sorting logic without requiring Home Assistant.
"""

from datetime import datetime, timedelta
from typing import Any


def sort_todo_items_by_due_date(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort todo items by due date with earliest due dates first.
    
    Items without due dates are placed at the end.
    Items with the same due date maintain their relative order.
    
    Args:
        items: List of todo item dictionaries
    
    Returns:
        Sorted list of todo items
    """
    def get_sort_key(item: dict[str, Any]) -> tuple:
        """Generate sort key for todo item."""
        due_str = item.get("due", "")
        
        if not due_str:
            # Items without due dates go to the end
            return (1, "")
        
        try:
            # Parse due date/time
            if "T" in due_str:
                # Due datetime format
                due_date = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                # Convert to naive datetime for comparison
                due_date = due_date.replace(tzinfo=None)
            else:
                # Due date only format
                due_date = datetime.strptime(due_str, "%Y-%m-%d")
            
            # Items with due dates go first, sorted by date
            return (0, due_date)
            
        except (ValueError, TypeError):
            # Invalid due date format, treat as no due date
            print(f"Warning: Invalid due date format for item: {due_str}")
            return (1, "")
    
    # Sort items using the sort key
    sorted_items = sorted(items, key=get_sort_key)
    
    print(f"Sorted {len(sorted_items)} items by due date")
    return sorted_items


def test_basic_sorting():
    """Test basic due date sorting."""
    print("\n=== Testing Basic Due Date Sorting ===")
    
    # Create test items with different due dates
    items = [
        {"summary": "Task C", "due": "2025-01-03"},
        {"summary": "Task A", "due": "2025-01-01"},
        {"summary": "Task B", "due": "2025-01-02"},
    ]
    
    sorted_items = sort_todo_items_by_due_date(items)
    
    expected_order = ["Task A", "Task B", "Task C"]
    actual_order = [item["summary"] for item in sorted_items]
    
    print(f"Input order:    {[item['summary'] for item in items]}")
    print(f"Expected order: {expected_order}")
    print(f"Actual order:   {actual_order}")
    
    assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"
    print("✓ Basic sorting test passed")


def test_no_due_dates():
    """Test sorting with items that have no due dates."""
    print("\n=== Testing Items Without Due Dates ===")
    
    items = [
        {"summary": "Task with due date", "due": "2025-01-01"},
        {"summary": "Task without due date 1", "due": ""},
        {"summary": "Task without due date 2"},
        {"summary": "Another task with due date", "due": "2025-01-02"},
    ]
    
    sorted_items = sort_todo_items_by_due_date(items)
    actual_order = [item["summary"] for item in sorted_items]
    
    print(f"Actual order: {actual_order}")
    
    # Items with due dates should come first, then items without
    assert actual_order[0] == "Task with due date"
    assert actual_order[1] == "Another task with due date"
    assert "Task without due date 1" in actual_order[2:]
    assert "Task without due date 2" in actual_order[2:]
    
    print("✓ No due dates test passed")


def test_datetime_sorting():
    """Test sorting with datetime (time included) due dates."""
    print("\n=== Testing DateTime Sorting ===")
    
    items = [
        {"summary": "Late morning", "due": "2025-01-01T11:00:00"},
        {"summary": "Early morning", "due": "2025-01-01T08:00:00"},
        {"summary": "Evening", "due": "2025-01-01T18:00:00"},
        {"summary": "Next day", "due": "2025-01-02T08:00:00"},
    ]
    
    sorted_items = sort_todo_items_by_due_date(items)
    actual_order = [item["summary"] for item in sorted_items]
    
    expected_order = ["Early morning", "Late morning", "Evening", "Next day"]
    
    print(f"Expected order: {expected_order}")
    print(f"Actual order:   {actual_order}")
    
    assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"
    print("✓ DateTime sorting test passed")


def test_mixed_date_formats():
    """Test sorting with mixed date and datetime formats."""
    print("\n=== Testing Mixed Date Formats ===")
    
    items = [
        {"summary": "Date only", "due": "2025-01-02"},
        {"summary": "DateTime earlier", "due": "2025-01-01T23:59:00"},
        {"summary": "DateTime later", "due": "2025-01-02T08:00:00"},
        {"summary": "No due date", "due": ""},
    ]
    
    sorted_items = sort_todo_items_by_due_date(items)
    actual_order = [item["summary"] for item in sorted_items]
    
    print(f"Actual order: {actual_order}")
    
    # DateTime earlier should be first, then Date only, then DateTime later, then no due date
    assert actual_order[0] == "DateTime earlier"
    assert actual_order[1] == "Date only"
    assert actual_order[2] == "DateTime later"
    assert actual_order[3] == "No due date"
    
    print("✓ Mixed date formats test passed")


def test_invalid_date_formats():
    """Test handling of invalid date formats."""
    print("\n=== Testing Invalid Date Formats ===")
    
    items = [
        {"summary": "Valid date", "due": "2025-01-01"},
        {"summary": "Invalid date", "due": "not-a-date"},
        {"summary": "Empty date", "due": ""},
        {"summary": "Malformed date", "due": "2025-13-45"},
    ]
    
    sorted_items = sort_todo_items_by_due_date(items)
    actual_order = [item["summary"] for item in sorted_items]
    
    print(f"Actual order: {actual_order}")
    
    # Valid date should come first, invalid dates should be treated as no due date
    assert actual_order[0] == "Valid date"
    assert "Invalid date" in actual_order[1:]
    assert "Empty date" in actual_order[1:]
    assert "Malformed date" in actual_order[1:]
    
    print("✓ Invalid date formats test passed")


def test_same_due_dates():
    """Test that items with same due dates maintain relative order."""
    print("\n=== Testing Same Due Dates ===")
    
    items = [
        {"summary": "Task C", "due": "2025-01-01"},
        {"summary": "Task A", "due": "2025-01-01"},
        {"summary": "Task B", "due": "2025-01-01"},
    ]
    
    sorted_items = sort_todo_items_by_due_date(items)
    actual_order = [item["summary"] for item in sorted_items]
    
    print(f"Input order:  {[item['summary'] for item in items]}")
    print(f"Actual order: {actual_order}")
    
    # All items have same due date, so order should be preserved
    expected_order = ["Task C", "Task A", "Task B"]
    assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"
    
    print("✓ Same due dates test passed")


def test_empty_list():
    """Test sorting empty list."""
    print("\n=== Testing Empty List ===")
    
    items = []
    sorted_items = sort_todo_items_by_due_date(items)
    
    assert sorted_items == [], "Empty list should remain empty"
    print("✓ Empty list test passed")


def test_single_item():
    """Test sorting single item."""
    print("\n=== Testing Single Item ===")
    
    items = [{"summary": "Only task", "due": "2025-01-01"}]
    sorted_items = sort_todo_items_by_due_date(items)
    
    assert len(sorted_items) == 1
    assert sorted_items[0]["summary"] == "Only task"
    print("✓ Single item test passed")


def run_all_tests():
    """Run all auto-sort tests."""
    print("Running Auto-Sort Tests")
    print("=" * 50)
    
    try:
        test_basic_sorting()
        test_no_due_dates()
        test_datetime_sorting()
        test_mixed_date_formats()
        test_invalid_date_formats()
        test_same_due_dates()
        test_empty_list()
        test_single_item()
        
        print("\n" + "=" * 50)
        print("✅ All auto-sort tests passed!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)