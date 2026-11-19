# Output artifacts produced by this recording.
Output cli-demo.mp4
Output cli-demo.gif

# Ensure the demo command exists before recording.
Require dot-tasks

# Terminal recording look-and-feel settings.
Set Shell "bash"
Set FontSize 18
Set Width 1100
Set Height 680
Set Padding 16
Set TypingSpeed 80ms
Set CursorBlink false

# Hide setup commands from the visible recording.
Hide
# Move into isolated demo workspace copied by render script.
Type "cd /tmp/dot-tasks-gif-demo"
Enter
# Clear terminal so recording starts clean.
Type "clear"
Enter
# Start showing terminal output to the viewer.
Show

# Open root interactive picker.
Type "dot-tasks"
Enter
# Brief pause so picker is visible before navigation.
Sleep 900ms
# 'list' is the first command in the picker (Inspect section), so select it directly.
Enter
# Hold on list output so user can read it.
Sleep 2200ms

# Start interactive create flow after listing tasks.
Type "clear"
Enter
Sleep 700ms
Type "dot-tasks create"
Enter
Sleep 700ms

# Fill create form: task_name prompt.
Type "cli-demo-task"
Enter
# Change priority from default p2 to p3.
Sleep 750ms
Down
Sleep 250ms
Enter
# Change effort from default m to s.
Sleep 750ms
Up
Sleep 250ms
Enter
# Accept default "no" for setting a due date.
Sleep 750ms
Enter
# Accept blank owner.
Sleep 750ms
Enter
# Provide summary text (multiline).
Sleep 750ms
Backspace 4
Type "Add README CLI demo media"
Escape
Enter

# Provide spec_readiness.
Sleep 750ms
Down 2
Sleep 250ms
Enter

# Provide tags (select + add new, then type them).
Sleep 750ms
Down 3
Space
Sleep 750ms
Type "add"
Sleep 750ms
Space
Sleep 750ms
Enter
Sleep 750ms
Type "demo,readme"
Enter

# Select default "no" for dependencies.
Sleep 500ms
Enter
# Pause so the creation message is visible.
Sleep 2500ms

# Resolve the new task's folder by name.
Type "dot-tasks path cli-demo-task"
Enter
# Final pause so the output remains visible.
Sleep 3500ms
