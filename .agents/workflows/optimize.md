---
description: Audit and surgically improve the shared agent workflows and skills. Use when the agent setup feels slow, repetitive, or underperforming — or when you want to clean up low-value skills, fix overlapping instructions, or embed lessons from past conversa
---

This workflow audits the current `.agent/` setup and produces a targeted improvement plan. It does not create documents or output files. All findings and proposed changes are presented in-conversation for your approval before anything is touched.

## 1. Audit — read the raw material

1. **Inventory the current setup** — list all files in `.agent/workflows/` and `.agent/skills/`. Note each item's name and description.
2. **Check the audit state file** — look for `.agent/optimize-state.json`. If it exists, read `lastAuditedAt` (ISO timestamp) and `analyzedConversationIds` (array). Only process conversations created or modified **after** `lastAuditedAt` and not already in the analyzed list. If the file does not exist, this is a first run — process all conversations. Tell the user how many new conversations are in scope before proceeding.
3. **Read conversation logs** — go to the persistent context log directory (`<appDataDir>/brain/`). For each conversation in scope (per step 2), read the `overview.txt` to extract:
   - Problems that came up more than once across conversations
   - Prompt chains that took many iterations to get right
   - Moments where a skill was suggested but not used
   - Workarounds the user had to do that a workflow should have handled
   - Patterns that repeated across different projects (these are the strongest candidates for a new workflow step)
4. **Read the active workflows** — load each workflow file in `.agent/workflows/` to understand what is currently instructed.
5. **Spot-read overlapping skills** — for any skills with similar names or descriptions, read their `SKILL.md` to determine if they genuinely differ or are redundant.

## 2. Diagnose — find the friction

Across the audit data, identify:

1. **Repeated questions** — things the user had to ask the agent more than once. These indicate missing standard operating procedures or gaps in existing workflows.
2. **Prompt iteration waste** — steps that needed many back-and-forths. These are candidates for embedding as explicit workflow steps or grill-me checkpoints.
3. **Underused features** — skills that were mentioned in conversations but never invoked, or workflow steps that were skipped.
4. **Skill redundancy** — pairs or groups of skills covering the same ground. Flag specific overlaps with evidence from the SKILL.md files.
5. **Instruction gaps** — places where a workflow gives a vague instruction ("do a review") that could be made concrete and actionable.

## 3. Plan — draft the improvement list

1. **Check for actionable findings** — if fewer than 3 new conversations were processed *and* no new skill overlaps were detected, exit early. Tell the user clearly: *"Ran audit. X new conversations processed. No friction patterns strong enough to act on yet. Run again after more activity."* Do **not** write those conversation IDs to the state file — keep them unanalyzed so they are included in the next run.
2. **Draft the improvement list** — for each finding, write a specific, surgical change:
   - What file is affected
   - What exact change is needed (add a step, sharpen wording, merge two skills, delete a redundant one)
   - Why: what past friction does it fix
   - Risk level: **low** (rewording, adding a step) or **high** (skill deletion, skill merge, removing a workflow step)
3. **Skill cleanup candidates** — a skill is only a cleanup candidate if *both* signals are present:
   - It was never explicitly invoked by name in any conversation log
   - Its `SKILL.md` content is thin, generic, or clearly duplicated by another skill
   Either signal alone is not enough. For each candidate, state which other skill covers the same ground, whether any workflow references it by name, and the recommended action: merge, delete, or keep with a narrowed description.

## 4. Present & grill — get informed approval

Present findings as a concise in-conversation plan:

- **Summary**: 2–3 sentences on what the audit found
- **Proposed changes table**: one row per change, with file, change type (add step / reword / merge / delete), risk level (low / high), and rationale
- **Skill cleanup list** (if any): skills proposed for removal or merge, with justification per the dual-signal threshold
- **Risk flag**: explicitly call out any change that touches a file referenced by name in other workflows or skills

Once the user has read the plan, **invoke the `grill-me` skill** — walk through each proposed change with the user, one branch at a time: Is this the root cause or a symptom? Is the change minimal enough? Any risk to other teams? Resolve all open branches before asking for final approval.

Do not execute any changes until the user explicitly approves after the grill-me session.

## 5. Execute — surgical changes only

Batch changes by risk level before starting:

- **Low-risk batch** (rewording, adding a step, sharpening an instruction): apply all approved low-risk changes together, then show a combined summary of what was touched.
- **High-risk changes** (skill deletion, skill merge, removing a workflow step): apply one at a time, pausing after each for the user to confirm before proceeding to the next.

For every change, regardless of risk level:

1. **Never overwrite a section to rewrite it** — use targeted edits. Preserve all existing content that is not explicitly in scope.
2. **Skill deletion** — before deleting a skill folder, confirm it is not referenced by name in any workflow file or other skill. Search first.
3. **Skill merge** — when merging two skills, move unique content into the surviving skill's `SKILL.md`. Do not silently drop useful instructions.
4. **Update the state file** — after all approved changes are applied, write or update `.agent/optimize-state.json` with:
   - `lastAuditedAt`: current ISO timestamp
   - `analyzedConversationIds`: the full accumulated list (previous IDs + IDs processed in this run)
   - `lastRunSummary`: one-sentence description of what was changed

   This file is gitignored — it is local per user, not shared across the team.

   Example:
   ```json
   {
     "lastAuditedAt": "2026-05-18T10:30:00Z",
     "analyzedConversationIds": ["ea66c08e-...", "b74cd0ce-..."],
     "lastRunSummary": "Merged architecture and architecture-decision-records skills; added grill-me checkpoint to TDD workflow."
   }
   ```

## Key rules

1. **No documents created** — output is in-conversation only. No files in `docs/`.
2. **Approval required before execution** — present the full plan, wait for explicit go-ahead.
3. **Surgical edits only** — never rewrite an entire workflow or skill file. Target specific lines or sections.
4. **No breaking changes** — if a change would affect other teams using the shared repo, flag it explicitly and require separate confirmation.
5. **Shared repo awareness** — these workflows and skills are used across architecture teams. Treat every change as a shared-library change: minimal, backward-compatible, well-justified.