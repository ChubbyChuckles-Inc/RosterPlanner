# Command Palette State Diagram

The Command Palette orchestrates fuzzy searching and command execution while providing cancellable, keyboard-first interaction.

## States Overview

```mermaid
digraph CommandPalette {
  rankdir=LR;
  Idle -> Inputting [label="focus gained / shortcut"];
  Inputting -> Filtering [label="debounce elapsed"];
  Filtering -> Filtering [label="incremental keystroke"];
  Filtering -> Executing [label="Enter on selection"];
  Inputting -> Idle [label="escape / blur"];
  Filtering -> Idle [label="escape / blur"];
  Executing -> Result [label="success"];
  Executing -> Error [label="failure"];
  Result -> Idle [label="close / accept"];
  Error -> Idle [label="dismiss"];
}
```

## State Descriptions

- **Idle**: Component unfocused or hidden; no active query.
- **Inputting**: User has focused palette; raw query buffer being updated but debounce interval not yet elapsed.
- **Filtering**: Active fuzzy matcher producing ranked results each keystroke.
- **Executing**: Selected command action performing (may be sync or async placeholder).
- **Result**: (Optional) ephemeral success acknowledgment, then auto-close.
- **Error**: Failure path surfaced with message; user can dismiss or retry.

## Notes

- Debounce duration should be short (e.g., 120–160ms) to avoid sluggish feedback.
- Execution should dispatch off UI thread when heavy; integrate with EventBus next milestones.
