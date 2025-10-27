#!/bin/bash
# Fix markdown code fences in Python files

for feature in FEATURE-003-003_Gantt_Chart_Generator FEATURE-003-004_Milestone_Tracker FEATURE-003-005_Change_Management_Logger FEATURE-003-006_PowerPoint_Generator; do
    echo "Processing $feature..."
    find "$feature" -name "implementation.py" -type f | while read file; do
        echo "  Fixing: $file"
        # Remove first line if it's ```python and last line if it's ```
        sed -i '1{/^```python$/d}' "$file"
        sed -i '${ /^```$/d}' "$file"
    done
done

echo "Done!"
