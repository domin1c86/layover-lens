# Session Rename Design

## Overview
Add an inline rename capability to the AI search sidebar history items. Only the currently active (selected) session can be renamed.

## Behavior

### Trigger
- The edit button (✎) appears on hover **only for the `.active` history item**.
- It is positioned to the left of the delete button (×).
- Non-active items never show the edit button.

### Edit Mode
- Clicking the edit button transforms the title `<span>` into a focused `<input>` with all text selected.
- The edit button (✎) is replaced by a done button (✓).
- The delete button is hidden during editing to prevent accidental deletion.

### Save / Cancel
- **Save**: Click the done button (✓), press `Enter`, or click outside the pill.
- **Cancel**: Press `Escape` to revert to the original title.
- If the user clears the input completely, saving falls back to the original title (no blank names).

## Styling
- Edit / done buttons: 20px circle, same hover darken effect (`#d0d0d0` background) as the delete button.
- Input inside the pill: transparent background, no border, inherits font and color, fills remaining space.

## Edge Cases
- Only one session can be in edit mode at a time.
- Clicking another session while editing saves the current edit first.
- Deleting a session is impossible while it is being edited.
