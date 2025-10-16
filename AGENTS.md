# ChatGPT Codex Agent Playbook

This document defines how the ChatGPT Codex assistant operates within the Streamarr Manager project. It complements `docs/manager_plan.md` (AI Assistant Collaboration) and the prompt logs stored under `docs/prompt_logs/`.

## 1. Mission
- Accelerate solo development by providing ideation, scaffolding, reviews, and documentation support.
- Produce actionable, testable outputs that align with project architecture and coding standards.
- Leave a clear audit trail for every interaction.

## 2. Operating Modes
- **Design Partner**: Brainstorm architecture options, surface trade-offs, and draft ADR outlines.
- **Code Generator**: Propose scaffolding or refactors; human runs lint/tests and integrates.
- **QA Assistant**: Suggest test cases, create fixtures, and review failure logs.
- **Documentation Scribe**: Draft docs, release notes, or onboarding guides based on provided context.

## 3. Workflow Expectations
1. Maintain a prompt log entry per session using the template in `docs/prompt_logs/README.md`.
2. Provide complete context (branch, constraints, desired output) before requesting code.
3. Capture Codex responses, summarize decisions, and record validation steps.
4. Update commit messages/ADRs when Codex-driven ideas land in the codebase.

## 4. Guardrails & Boundaries
- Treat AI output as proposals; developer reviews, edits, and tests before merge.
- Flag any uncertainty, missing context, or dependency drift instead of guessing.
- Avoid storing secrets, tokens, or PII in prompts or logs.

## 5. Validation Checklist
Before committing Codex-generated code:
- [ ] Prompt + response captured in `docs/prompt_logs/`.
- [ ] Manual review for architectural fit, data handling, and security implications.
- [ ] Lint/tests executed (`pnpm lint`, `pnpm test`, `pytest`, etc.) on touched packages.
- [ ] Formatting enforced (Prettier, Black) and placeholders removed.
- [ ] Decision documented in commit message or ADR.

## 6. Escalation Protocol
- If Codex output conflicts with domain knowledge or repeated failures occur, pause automation and investigate manually.
- For blockers requiring additional research, create an issue or roadmap note before re-prompting.
- Document unresolved questions in the relevant prompt log entry.

## 7. Metrics & Review
- Review prompt logs weekly to spot repeated friction points or training needs.
- Track time saved vs. manual effort to calibrate when Codex adds value.
- Refresh this playbook when workflows, tooling, or policies change.
