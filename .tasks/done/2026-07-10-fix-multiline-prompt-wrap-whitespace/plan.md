## Plan
1. Preserve the deterministic PTY reproducer and characterize the terminal-width/answer-width/height boundary.
2. Trace InquirerPy's answered-message rendering and prompt-toolkit's final render behavior to identify the exact invariant violation.
3. Evaluate minimal candidate fixes against the reproducer, including wrapping policy and answered-value transformation, without changing multiline editing semantics.
4. Implement the smallest robust fix in the selector layer and add a real-PTY regression test with explanatory comments.
5. Validate adversarially across narrow and wide widths, multiple heights, exact boundary lengths, multiline answers, cancellation, CPR behavior, focused tests, and the full suite.
6. Review the diff for simplicity and complete the task only after every acceptance criterion has direct evidence.
