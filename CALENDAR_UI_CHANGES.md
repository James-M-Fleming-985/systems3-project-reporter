# Calendar Modal UI Changes - Visual Description

## Before (Original):
```
┌─────────────────────────────────────────────────┐
│ 🔵 Milestone                              ✕     │
│ Install Kardex System                           │
├─────────────────────────────────────────────────┤
│                                                 │
│ Type: Milestone                                 │
│ Status: In Progress                             │
│ Description: Install Kardex System              │
│ Due Date: 15 Mar 2024                          │
│ Program: ZnNi Line Development ↗                │
│                                                 │
│ Details:                                        │
│ Start Date: 01 Feb 2024                        │
│ Target Date: 15 Mar 2024                       │
│ Progress: 45%                                   │
│                                                 │
├─────────────────────────────────────────────────┤
│ Program Name                                    │
│                    [Open in Dashboard ↗] [Close] │
└─────────────────────────────────────────────────┘
```

## After (With Edit/Delete Buttons):
```
┌─────────────────────────────────────────────────┐
│ 🔵 Milestone                              ✕     │
│ Install Kardex System                           │
├─────────────────────────────────────────────────┤
│                                                 │
│ Type: Milestone                                 │
│ Status: In Progress                             │
│ Description: Install Kardex System              │
│ Due Date: 15 Mar 2024                          │
│ Program: ZnNi Line Development ↗                │
│                                                 │
│ Details:                                        │
│ Start Date: 01 Feb 2024                        │
│ Target Date: 15 Mar 2024                       │
│ Progress: 45%                                   │
│                                                 │
├─────────────────────────────────────────────────┤
│ [✏️ Edit Milestone] [🗑️ Delete]                │
│                    [Open in Dashboard ↗] [Close] │
└─────────────────────────────────────────────────┘
```

## Button Behavior:

### Edit Milestone Button:
- **Appears**: Only for milestone events
- **Action**: Opens prompt dialog to change status
- **Prompt**: "Edit Milestone Status for: [name]
              Current Status: [status]
              Enter new status: NOT_STARTED, IN_PROGRESS, or COMPLETED"
- **Validation**: Converts input to uppercase, replaces spaces with underscores
- **API Call**: POST /milestones/update
- **Result**: Reloads calendar on success

### Delete Button:
- **Appears**: Only for milestone events  
- **Action**: Shows confirmation dialog
- **Confirmation**: "Are you sure you want to delete milestone: [name]?"
- **Current**: Shows "coming soon" message (API endpoint not yet implemented)

### Button Visibility:
```javascript
// Buttons shown ONLY for milestone events
if (ep.type === 'milestone' && ep.milestone) {
    editBtn.classList.remove('hidden');
    deleteBtn.classList.remove('hidden');
} else {
    editBtn.classList.add('hidden');  // Hidden for changes, schedule, metrics
    deleteBtn.classList.add('hidden');
}
```

## User Flow:

1. User clicks milestone event in calendar
2. Modal opens with event details
3. If event is a milestone:
   - ✏️ Edit and 🗑️ Delete buttons appear
4. User clicks "✏️ Edit Milestone"
5. Prompt appears with current status
6. User enters new status
7. Validation checks input
8. API updates milestone (only first match, no duplicates!)
9. Success message shown
10. Calendar reloads with updated data

## Error Messages:

### Before:
- "Cannot edit this event"
- "Cannot delete this event"

### After:
- "This event cannot be edited. Only milestone events can be edited from the calendar."
- "This event cannot be deleted. Only milestone events can be deleted from the calendar."

## Future Improvements (TODO):
1. Replace prompt() with modern modal dialog
2. Add status dropdown/radio buttons for better UX
3. Implement delete API endpoint
4. Add loading spinner during API calls
5. Show inline success/error messages instead of alerts
