---
name: elicitation
description: Push on the most recent output — sharpen, critique, and improve it using proven elicitation methods. Use when the user wants deeper critique, a second pass, or mentions "push on this", "make it better", "go deeper", or a specific method like socratic, red team, pre-mortem.
---

# Advanced Elicitation

Push the most recent output further: reconsider it, stress-test it, and surface what's hidden. Every pass sharpens what's already there.

---

## Flow

Present 5 methods chosen for the current context. The user picks one, you apply it, show the improved version, and re-offer the menu. Continue until the user exits with **x**.

```
Choose a method (1–5), [r] reshuffle, [a] list all, or [x] done:

1. [Method]
2. [Method]
3. [Method]
4. [Method]
5. [Method]
```

After each method:
- Show what it revealed or improved
- Ask: apply these changes? (y / n / partial)
- Re-present the menu

---

## Method Catalog

### Critical
- **Socratic Questioning** — ask a chain of probing questions that expose unstated assumptions; never accept the first answer
- **Steel Man** — construct the strongest possible version of the opposing view, then respond to *that*
- **Red Team** — attack the output as an adversary: find every gap, exploit, or flaw a critic would land on
- **Pre-Mortem** — project 12 months forward; the idea has failed catastrophically — narrate exactly why
- **Devil's Advocate** — argue the opposite position as compellingly as possible; surface what the output glosses over

### Structural
- **First Principles Deconstruction** — strip every assumption to bedrock; rebuild only from what's provably true
- **Assumption Audit** — list every assumption embedded in the output, flag which are load-bearing, which are guesses
- **Completeness Check** — what's missing? what case isn't handled? what stakeholder isn't represented?
- **Scope Pressure** — what would this look like if we had 10× the constraint? 10× the budget? How does it break at the edges?

### Generative
- **Yes And** — accept every element of the output and add a layer that makes it more ambitious
- **Inversion** — flip the core goal: design for the opposite outcome; harvest the inversions as insights
- **Analogical Leap** — find an unrelated domain that solved a structurally identical problem; steal its solution
- **Second Order Effects** — trace each decision two steps forward: what does *that* cause?

### Perspective
- **User Lens** — narrate the output from the perspective of the least technical end user; surface the friction
- **Stakeholder Panel** — give voice to 3 stakeholders who weren't consulted; each names their biggest objection
- **Future Self Review** — your wise future self looks back at this decision; what do they wish you'd caught now?
- **Critic vs. Champion** — write a scathing one-paragraph review, then a glowing one; find the truth between them

### Precision
- **Claim Audit** — identify every factual or causal claim; flag which need evidence, which are speculation
- **Language Tightening** — every vague word ("good", "fast", "simple") gets a concrete definition or gets cut
- **Constraint Mining** — name every implicit constraint; decide which to honor, relax, or remove
- **Edge Case Hunt** — enumerate 5 edge cases the output doesn't handle; decide which to address

---

## Selection logic

Pick 5 methods that fit the content at hand:
- **Spec / plan / design** → favor Assumption Audit, Pre-Mortem, Completeness Check, Scope Pressure, Red Team
- **Argument / pitch / doc** → favor Steel Man, Socratic, Claim Audit, Language Tightening, Stakeholder Panel
- **Creative output** → favor Yes And, Analogical Leap, Inversion, Second Order Effects
- **Personal decision** → favor Pre-Mortem, Future Self Review, Critic vs. Champion, Values Archaeology

When reshuffling, prefer diversity across categories over repeating the same category.

---

## Stopping condition

Exit when the user selects **x** or says "done" / "enough". Output the final improved version with a one-line summary of what changed.
