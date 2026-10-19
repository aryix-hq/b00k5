# Research & Discovery Notes Directory (Stage 1)

This directory stores living Research & Discovery notes (`RES-001.md`, `RES-002.md`, etc.) produced during **Stage 1 of the 4-Stage Lifecycle**.

## Operating Invariants
1. **Research First**: Before drafting feature specs or jumping to code, discovery notes capture user pain points, domain exploration, client advocacy, and technical spikes.
2. **Authorship**: Authored collaboratively by `@research`, `@client-advocate`, and technical advisors (`@architect`).
3. **Product Handoff**: Every research note produces explicit capability proposals and baseline inputs for RICE prioritization by the **Product Manager (`@product-manager`)** in `wiki/features/FEAT-XXX.md`.
4. **Template**: Scaffold new discovery notes using [`wiki/templates/RESEARCH_NOTE.md`](../templates/RESEARCH_NOTE.md).
5. **Zero-Token Local Drafting**: Research summaries and synthesis are drafted via local Ollama (`qwen2.5-coder:14b` via `bin/local-coder.sh`) to conserve cloud credits.
