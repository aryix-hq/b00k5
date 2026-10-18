# Living Operational FAQs & Troubleshooting Ledger

> **Custodian**: Documentation Manager & Scribe (`@documentation-manager`)  
> **Status**: Living FAQ Ledger  
> **Last Synchronized**: 2026-10-17  

This document captures recurring operational questions, developer gotchas, and immediate troubleshooting resolutions.

---

## 1. Plugin & Customization FAQs

### Q: Why does Antigravity still show Google Drive after migrating to `~/Code/ai-agents`?
**A**: Antigravity's Language Server caches plugin discovery paths in memory on boot.
1. Run `Developer: Reload Window` (`Cmd + Shift + P`) to flush in-memory caches.
2. Verify that `ls -la ~/.gemini/config/plugins/ai-agents` points to `/Users/adithya/Code/ai-agents`.
3. Archive or rename the legacy Google Drive folder to prevent accidental reads.

### Q: Does a project-level agent override a global agent?
**A**: **Yes.** Antigravity enforces hierarchical precedence: Local project customizations (`.agents/agents/<name>.md`) always override global plugin definitions with the same name.

### Q: If I delete local agent files, do I lose project memory?
**A**: **No.** Agent definitions are stateless persona files (`.agents/agents/*.md`). Project memory is stored separately in `.agents/memory/` and `wiki/`. Deleting a local agent falls back seamlessly to the global plugin agent while preserving all memory graph state.

---

## 2. Model Routing & Token Optimization FAQs

### Q: How do I know if Ollama is actively processing a request?
**A**: Run `ollama ps` in your terminal. Active running models, memory consumption, and GPU utilization appear in real-time.

### Q: Why shouldn't I set Ollama as the universal default across all agents?
**A**: Local 7B-14B models struggle with dense multi-agent schemas, statutory accounting invariants (Schedule III, double-entry), and adversarial architectural synthesis. Use local models for worker execution (syntax, tests, code generation), and keep cloud models for top-level chat, orchestration, and review gates.

---

## 3. Git & Branching FAQs

### Q: Why does GitHub show "entirely different commit histories" when creating a PR?
**A**: This occurs when `main` on GitHub was initialized separately from local `git init`. The branches share no common ancestor. Align the feature branch base with `origin/main` using `git checkout -b <branch> origin/main` and force-push with lease.

