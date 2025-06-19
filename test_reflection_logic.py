#!/usr/bin/env python3
"""
Test the smart list reflection logic.
"""

from datetime import datetime, timedelta

def analyze_task_timeframe(due_date: datetime) -> str:
    """Copied from __init__.py for testing"""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    due_date_only = due_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if due_date_only == today:
        return 'today'
    
    days_since_sunday = (today.weekday() + 1) % 7
    week_start = today - timedelta(days=days_since_sunday)
    week_end = week_start + timedelta(days=6)
    
    if week_start <= due_date_only <= week_end:
        return 'this_week'
    
    if due_date_only.month == today.month and due_date_only.year == today.year:
        return 'this_month'
    
    return 'other'

def test_reflection_logic():
    """Test which smart lists a task should appear in"""
    print("Testing Smart List Reflection Logic")
    print("=" * 40)
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    test_cases = [
        ("Due today", today),
        ("Due tomorrow", today + timedelta(days=1)),
        ("Due in 3 days", today + timedelta(days=3)),
        ("Due in 15 days", today + timedelta(days=15)),
        ("Due in 2 months", today + timedelta(days=60))
    ]
    
    for desc, due_date in test_cases:
        timeframe = analyze_task_timeframe(due_date)
        
        # Determine which smart lists should reflect this task
        target_smart_lists = []
        
        if timeframe == 'today':
            target_smart_lists.append('daily')
        if timeframe in ['today', 'this_week']:
            target_smart_lists.append('weekly')
        if timeframe in ['today', 'this_week', 'this_month']:
            target_smart_lists.append('monthly')
        
        print(f"{desc:15} | Timeframe: {timeframe:10} | Appears in: {', '.join(target_smart_lists) if target_smart_lists else 'No smart lists'}")
    
    print("\n✅ Reflection Logic Summary:")
    print("• Tasks due TODAY appear in: Daily + Weekly + Monthly")
    print("• Tasks due THIS WEEK appear in: Weekly + Monthly") 
    print("• Tasks due THIS MONTH appear in: Monthly")
    print("• Tasks due LATER appear in: No smart lists")
    print("\n🎯 This creates smart views for planning:")
    print("• Daily list = Today's focused work")
    print("• Weekly list = This week's planning")
    print("• Monthly list = This month's overview")

if __name__ == "__main__":
    test_reflection_logic()