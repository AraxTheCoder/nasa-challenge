# Tasks

One file per task: `T<id>-<slug>.md`. The Board in `TEAM.md` is the index; this folder holds the
details. Rules are in `CLAUDE.md` ("Tasks").

## Template

```markdown
# T<id>: <title>

- **Owner:** <name>  ·  **Status:** open | doing | review | done | blocked
- **Branch:** `<name>/T<id>-<slug>`
- **Depends on / feeds:** T..

## Goal
What "done" means, in one or two sentences.

## Plan
- [ ] step

## Findings
What we learned, with numbers, links, query + timestamp where data was involved.

## Questions / needs from others
- [to <name>] ...

## Handoff
How to use the result; what's left; gotchas.

## Notes from others
(anyone may append here, dated and signed)
```
