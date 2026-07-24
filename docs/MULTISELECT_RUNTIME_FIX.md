# Reading Multi-select Runtime Fix

## Symptom

A Reading session could fail before `start_session_callback` executed with an error such as:

```text
Value: 'G' is not in the list of choices
```

The selected value was actually `Government and politics`. A single selected CheckboxGroup value was received as a scalar string in the affected browser/event path. Gradio's stock CheckboxGroup preprocessor iterated that string one character at a time and rejected the first character.

## Correction

The scalar-tolerant component factory returns Gradio's built-in CheckboxGroup and patches only that instance to normalize scalar input to a one-element list before standard validation. Both Topics and Comprehension competencies use this component.

`start_session_callback` also normalizes both fields independently, removes accidental duplicates, and rejects values outside the current allow lists. This second boundary protects direct API usage and future component changes.

## Session safety

The exception occurred during Gradio preprocessing, before the application created a new session or altered a checkpoint. Existing checkpoints and generated-bank records were not damaged.

The repeated `BaseEventLoop.__del__` messages in the same log were not the Reading failure. The actionable exception was the CheckboxGroup validation traceback.
