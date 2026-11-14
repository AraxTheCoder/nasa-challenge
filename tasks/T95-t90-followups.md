# T95: T90 follow-ups (browser test, field labels)

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T95-t90-followups`
- **Depends on / feeds:** T90 (Jonathan), T46 (CI). Not in scope: missing tiles and the 422 layers (T94, Jonathan)

## Goal
CI green again and the viewer's field object complete after the T90 merge, with the smallest possible changes in
Jonathan's files.

## Plan
- [ ] `web/tests/browser_test.py`: fails at line 127 (`input[name=ra]` not found / not fillable since T90)
- [ ] `currentTarget().labels` empty for fields whose target.json has labels

## Findings

## Notes from others
