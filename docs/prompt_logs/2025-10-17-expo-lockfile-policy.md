# Codex Prompt Log

- **Date / Time**: 2025-10-17 00:00 (UTC)
- **Feature / Task**: Expo lockfile policy clarification
- **Context Summary**:
  - Current state / branch: working tree with Expo SDK 54 upgrade pending review
  - Key constraints (deps, performance, security): Keep deterministic npm installs for Expo workspace; align with existing documentation workflow
- **Prompt**:
  ```text
  package-lock.jsonda çok fazla değişiklik var. hepsini değişikliklerimizi koruyacak şekilde merge eder misin? manuel yapamıyorum çok uzun sürüyor.

  we should be using expo 54

  package-lock.jsonda çok fazla değişiklik var. hepsini değişikliklerimizi koruyacak şekilde merge eder misin? manuel yapamıyorum çok uzun sürüyor.

  do we need the package-lock.json?
  ```
- **Assistant Output Summary**:
  - Proposed solution: Documented the repository policy requiring `apps/expo/package-lock.json` to remain committed for reproducible npm installs.
  - Files touched / to create: `docs/frontend/expo_dependency_policy.md`, new prompt log entry.
  - Follow-up actions requested: None beyond communicating the documented decision.
- **Decision**:
  - Accepted / Modified / Rejected (with reason): Accepted — documentation added clarifying the lockfile requirement.
- **Validation**:
  - Tests run: Not applicable (documentation-only change).
  - Manual checks: Reviewed documentation for clarity and compliance with repository guidance.
- **Notes / Next Steps**:
  - TODOs: Ensure future Expo dependency updates continue to regenerate and commit the lockfile.
  - Risks: Low; policy relies on contributors running `npm install` to regenerate lockfile when necessary.
