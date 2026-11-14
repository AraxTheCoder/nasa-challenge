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

## Decisions and consistency (the agents' main job)

- Humans don't ack each other's decisions. Whoever decides writes a dated line under TEAM.md
  "Decisions" and it is in effect. No "PROPOSED, please ack" waiting.
- Keeping the repo consistent is every agent's job, all the time. When you pull and see a change
  (a decision, contract, schema, task or code) that affects your area or contradicts something
  else in the repo, bring your side in line: docs, CONTRACTS, schema, fixtures, Board, your code.
  Say what you changed in the TEAM.md Log.
- If making it consistent needs a change in someone else's code, put it in their task file or under
  "Questions / Blockers" instead of editing their code.
- If two decisions contradict each other, the later one holds. Flag the conflict under
  "Questions / Blockers" so the humans see it.
- Stay synced: pull before every piece of work, merge main into your branch often, and keep a
  background `git fetch` running so new commits on main are noticed within a minute.

## Tasks (how we distribute and communicate work)

- Every task has a file `tasks/T<id>-<slug>.md` (template: `tasks/README.md`): goal, owner,
  status, plan, findings, questions, handoff. The Board row in TEAM.md is the one-line index and
  links the file.
- New task: add a Board row and its task file in the same commit. Existing rows without a file get
  one when someone picks the task up.
- The task file is where details go: what you found, what you need from whom, how to use the
  result. Keep it current while you work; it is what the next person reads.
- Only the owner edits a task file, except the "Notes from others" section, which anyone may
  append to.

## Claiming work (prevents two agents doing the same thing)

- Only work on a Board task that is `open` or already assigned to your human.
- Claiming = Board row (Owner, Status `doing`, Branch) + task file, in one commit.
- Claim it before writing code: set Owner and Status=`doing` in your Board row, commit
  `board: claim T<id>`, and push straight to main.
- If the push is rejected: pull, check nobody else claimed the task, then retry. If someone did,
  drop your claim and pick another task.

## While working

- Branch `<name>/T<id>-<slug>`. Small commits. Merge main into your branch often.
- When the task works, merge to main (or open a short PR if someone asks for review).
- Stay inside the files of your task. Track folders: `pipeline/` = A, `detect/` = B, `web/` = C.
  `app/` (URL `/app/`) is Jonathan's UI redesign (T55) and is for UI work only: everyone else keeps
  working in `web/` (URL `/web/`) exactly as before and does not edit `app/`.
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

## Personal rules: Jonathan only

These apply only to sessions with Jonathan (git user `Jonathan`). Other humans' agents ignore this
section.

- **Commit and push directly** once the automated checks pass (no waiting for his OK first).
- **Claude runs all automated checks itself** before handing over: unit tests, API calls (curl),
  schema validation, linters. Report the results; don't ask Jonathan to do these.
- **Never run viewer/browser tests yourself** (no Playwright, no `web/tests/browser_test.py`, no
  pixel-visibility probes on real data). Only start the apps and hand over.
- **Jonathan does the visual and integration tests.** After every task, start everything needed
  (servers, viewer, in the background) and tell him exactly what to look at end to end: URLs to
  open, steps to click, and the expected result for each (what he should see in the UI, how the
  parts work together).
