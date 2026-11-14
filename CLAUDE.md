# Rules for every agent in this repo

NASA Space Apps Challenge 2026 (Nov 14–15), challenge "Planet X and SPHEREx".
Three humans, each with their own Claude Code session, all on this repo. These rules keep the
three sessions in sync. Follow them exactly; if one seems wrong, raise it under
"Questions / Blockers" in TEAM.md instead of ignoring it.

Source of truth, in order: `docs/CHALLENGE.md` (official text) > `docs/CONTRACTS.md` (interfaces)
> `TEAM.md` (plan and state) > anything said in chat.

## Start of every session

1. `git checkout main && git pull --rebase`
2. Read `TEAM.md`, `docs/CONTRACTS.md`, `docs/CHALLENGE.md`.
3. Tell your human in ≤10 lines:
   - what changed since their last session (`git log` + TEAM.md Log),
   - open and blocked tasks,
   - anything waiting on them,
   - which task you suggest next.
4. Wait for their OK before doing anything else.
   Don't write code until I've OK'd the task and you've claimed it on the Board.

## Claiming work (prevents two agents doing the same thing)

- Only work on a Board task that is `open` or already assigned to your human.
- Claim it before writing code: set Owner and Status=`doing` in your Board row, commit
  `board: claim T<id>`, and push straight to main.
- If the push is rejected: pull, check nobody else claimed the task, then retry. If someone did,
  drop your claim and pick another task.

## While working

- Branch `<name>/T<id>-<slug>`. Small commits. Merge main into your branch often.
- When the task works, merge to main (or open a short PR if someone asks for review).
- Stay inside the files of your task. Track folders: `pipeline/` = A, `detect/` = B, `web/` = C.
  If you need a change in someone else's area, write it under "Questions / Blockers" in TEAM.md
  instead of editing their code.
- `docs/CONTRACTS.md` only changes together with a dated line under TEAM.md "Decisions" that says
  why. Never change an interface silently.
- Never commit large data. Cache downloads under `data/` (gitignored); commit only tiny samples to
  `fixtures/`. No `.fits` files in git.
- The demo uses real SPHEREx data. Anything simulated or injected is labeled as such in code
  (`"synthetic": true` in the JSON) and visibly in the UI.
- Record when and how you got data (query + UTC timestamp) in the target's `provenance`, so
  results can be reproduced.

## Editing TEAM.md (keep merge conflicts trivial)

- Only edit your own Board rows. Everything else is append-only.
- On a TEAM.md merge conflict, keep both sides.

## Ideas

- When you or your human have an idea, append it to TEAM.md "Ideas" as
  `[name] idea — status: new`.
- Don't act on an idea until a human has moved it onto the Board.

## End of session (and at least every ~90 min)

- Update your task status on the Board.
- Append a handoff note to the TEAM.md Log: who, what's done, what's next, gotchas.
- Commit `board: …` and push.
