---
applyTo: '**'
---

# Copilot instructions (refined)

Purpose

- Support a two‑phase workflow: Learning (planning/explaining) and Writing code (implementation).
- Prioritize teaching and clarity.

Phases

- Learning:
  - No feature code generation.
  - High‑level overviews, architecture, tradeoffs, and small illustrative snippets only.
  - Ask clarifying questions and propose incremental learning steps.

- Writing code:
  - The user will explicitly request "write code" or similar.
  - Limit code per response to one low‑level concept (~≤50 lines).
  - Prefer small, incremental changes and verify each step before continuing.
  - (Project specific) verify each step with plots

Rules

- Always ask clarifying questions before producing non-trivial code.
- When giving code: show file path and minimal context; avoid changing unrelated files.
- Include short explanation (1–3 sentences) for every code change.
- Provide tests or usage examples on request, also limited and incremental.

Prompt examples

- "Help me plan out converting NetCDF to RGBA PNG Images" → Learning.
- "Please write the conversion from NetCDF to RBGA PNG (code)" → Writing code
