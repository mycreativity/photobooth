---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

# Grill Me

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one by one.

---

## Cadence

For each question:

1. **Ask the question** — one at a time, never stack multiple questions
2. **Give your recommended answer** — be direct, explain the reasoning briefly
3. **Wait for the user's response** — accept, reject, or modify
4. **Move to the next branch** — only after the current one is resolved

If a question can be answered by exploring the codebase or existing documentation, do that first instead of asking.

---

## Stopping condition

Stop when the user says **"done"**, **"enough"**, or **"x"** — or when all branches of the design tree are resolved.

When stopping, output a **resolution table**:

| Question         | Decision           | Rationale |
| ---------------- | ------------------ | --------- |
| [what was asked] | [what was decided] | [why]     |

---

## Workflow mode

When invoked from inside a workflow (e.g., after a plan is proposed):
- Run the grill-me session on the specific plan or section at hand
- After the user exits, return the resolution table to the workflow
- The agreed decisions feed directly into the next workflow step