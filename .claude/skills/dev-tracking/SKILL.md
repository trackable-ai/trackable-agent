---
name: dev-tracking
description: Update progress tracking file - update task status and move them to correct sections. Use when a task or a user's request is done
---

Update the progress tracking file [dev_tracking.md](../../../docs/dev_tracking.md) when a task or a user's request is done

## Instructions

1. Read the current progress tracking file
   - There are three task status in this file: "⏸️ Not Started", "🔄 In Progress", and "✅ Completed"
   - **Mark done**: Move items from "🔄 In Progress" or "⏸️ Not Started" to "✅ Completed"
   - **Start task**: Move items from "⏸️ Not Started" to "🔄 In Progress"
2. Based on recent actions, determine which tasks are done
   - Add `[x]` checkbox under appropriate category in "✅ Completed"
   - Add entry to "Recent Updates" with today's date: `- ✅ <description>`
   - Remove from previous section
3. Evaluate the priorities of remaining tasks and prioritize them
   - Move the prioritized task(s) to "🔄 In Progress" section and mark priorities
   - Add entry to "Recent Updates" with today's date: `- ✅ <description>`
   - Remove from previous section
4. Update `**Last Updated**` date at top of file
5. Show diff summary of changes made
