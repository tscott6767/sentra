# Modified Ralph Loop — Project Kickoff Template

**Version 1.2 · Sept 4, 2026 · finalized by Tony**
**v1.2: adds Section 8 (Scope Prods) + Section 9 (Re-entry) — scope drift gets named; existing projects re-lock on scope change.**
Canonical copy. Also stored as a knowledge item (pinned) and a pinned memory.
**Requires a stack with persistent memory + MCP filesystem tools — they are essential.**

## How to use

1. Copy the blank template below into a **new chat** with your AI.
2. Fill in: brief, constraints, exit criteria, autonomy start level, delegation on/off.
3. The AI must confirm the spec before building. Reply **"confirmed"** to start the loop.
4. If a session crashes or the chat is lost, paste the **RESUME COMMAND**.

## Blank template (paste this)

```text
════════════════════════════════════════════════════════
  PROJECT KICKOFF — MODIFIED RALPH LOOP v1.2
  (requires: persistent memory + MCP filesystem)
════════════════════════════════════════════════════════
PROJECT NAME: ______________

1 · BRIEF — what I want, one paragraph (any project type)
  ________________________________________________________

2 · HARD CONSTRAINTS — musts / must-nots / platform / limits
  ________________________________________________________
  (Unlisted = AI proposes, I decide.)

3 · EXIT CRITERIA — the loop ends only when ALL are TRUE:
  [ ] ________________________________________________
  [ ] ________________________________________________
  [ ] ________________________________________________

4 · AUTONOMY DIAL — start level: [ LOW | MEDIUM | HIGH ]  (default MEDIUM)
    LOW    — confirm every pass with me
    MEDIUM — confirm at phase changes + milestones
    HIGH   — free-run to exit criteria; gates only
    VARIABLE RULE: revisit at every milestone. Heavy confirmation while
    design is still forming; freer running once the loop is green and
    stable. Always record the current level in progress notes.

5 · LOOP PROTOCOL — AI: follow exactly, in order.

  PHASE 0 · CONFIRM   Restate the brief as a complete spec; list every
                       decision you would have to guess; WAIT for my
                       "confirmed". Build nothing yet.

  PHASE 1 · LOCK      Store the spec BOTH to persistent memory (pinned,
                       tagged [project-name]) AND to
                       /projects/[project-name]/SPEC.md via MCP
                       filesystem. Project state now lives OUTSIDE this
                       chat.

  PHASE 2 · LOOP      Repeat until every exit criterion is met:
                         a. READ   current state from memory + files.
                                    Never assume.
                         b. DO     the next smallest useful piece.
                         c. VERIFY — run it / check it / re-read against
                                    a checklist. A claim is not evidence.
                         d. FIX    surgically if broken; re-verify.
                         e. SAVE   a one-line progress note: state,
                                    autonomy level, next step.
                         f. REPORT one line: done / blocked / next.
                       In-loop rules: work in small pieces (they survive
                       crashes); if a tool fails, switch channel not
                       goal, and record the workaround.

  PHASE 3 · GATES     Regardless of dial setting, always ask before:
                       deleting/overwriting existing files · anything
                       irreversible · the same step failing twice · any
                       deviation from the locked spec.

  PHASE 4 · EXIT      Only when all criteria are VERIFIED (not claimed):
                       ship · store a consolidated milestone summary to
                       memory · update SPEC.md · honestly list anything
                       still unverified.

6 · RESUME COMMAND — paste if a session crashes or chat is lost:
  "Continue [PROJECT NAME] — the memory entry [ID] has everything.
   Read current state, run the next loop pass."

7 · DELEGATION (optional) — subagents allowed under these rules:
    · Delegate only independent, parallelizable, verifiable tasks
      (audits, cross-checks, test groups, research with written output).
    · Pass state by FILE PATH — subagents read SPEC.md and state files
      themselves; never paste prose summaries to them.
    · One writer per file — subagents write only to their own scratch
      dir (/projects/[name]/sub/); the orchestrator integrates.
    · A subagent result only counts once saved to a file or memory entry.
    · Verifiers return RAW output (logs, command results, data) —
      never just "passed".
    · Subagent failure → retry once → fall back to direct execution.
    · Never delegate: spec decisions, gates, exits, human confirmation.

8 · SCOPE PRODS (in-loop) — active in every project, all autonomy levels:
    · The AI checks each new request against the locked SPEC.md.
    · On drift, the AI does NOT silently follow. It PRODS: names the
      drift, gives the reason/evidence ('it can't work because X'),
      states the cost if relevant, and offers options — re-scope now ·
      defer to a later project · drop it.
    · Scope changes are legitimate — but they get DECIDED and re-locked
      (Section 9), not absorbed mid-loop.
    · This is REQUESTED behaviour, not pushback — the maintainer is
      prone to mid-project changes and wants the prod (added v1.2).

9 · RE-ENTRY (existing projects — triggered by scope change)
    · TRIGGER: a fix becomes a rebuild · a retest becomes a redesign ·
      'make it work' becomes 'make it work for X' · any drift a
      Section 8 prod names.
    · Small fixes are EXEMPT — no ceremony, just verification.
    · PROCEDURE (15 min): restate what the project now IS → re-lock
      SPEC.md + memory spec → redefine exit criteria → note the scope
      delta + date → resume the loop.
    · A crashed session or lost chat also counts as a re-entry point:
      READ state first, never assume (Phase 2a).

RULES OF THE LOOP
  · Confirm before starting; verify before claiming.
  · Small pieces beat big leaps.
  · Machine output is evidence; AI confidence is not.
  · A crash may slow the loop; it may never lose the plan or progress.
  · Scope drift is named and decided, never silently followed.
```

## Provenance & changelog

- **v1.0 — Aug 30, 2026:** initial template, distilled from the Fish-Man: Shark Bait build (three crashes, still shipped). Design decisions: memory + MCP essential; autonomy dial variable by progress state; universal scope (any project type); one-screen fill-in-the-blanks.
- **v1.1 — Aug 30, 2026:** added Section 7 DELEGATION after live-testing discussion. Rationale: subagents add throughput, context economy, and independent verification (a verifier that didn't write the code doesn't grade its own homework) — but introduce failure modes: state divergence, transmission loss, claim-chaining, write conflicts, silent failure. Each is neutralized by one rule. Open question: whether subagents in this stack can read persistent memory directly is untested; the file-path rule covers it either way.
- **v1.2 — Sept 4, 2026:** added Section 8 SCOPE PRODS + Section 9 RE-ENTRY. Origin: hybrid-router retest5 (Sept 4) — a silent scope change (retest a plain-chat router became, unspoken, 'serve this tool-heavy persona chat') cost a full day chasing a category error as a bug. Prods are REQUESTED behaviour (the maintainer is prone to mid-project changes, wants drift named with reasons, not followed). Re-entry = 15-min Phase 0–1 refresh for existing projects on scope change; small fixes exempt. Free-form exploration stays legitimate outside the loop — pivots get recorded under the assumptions-on-record rule.
