# Prompt Logs

This directory stores Codex prompt sessions using the template defined in `docs/manager_plan.md` under **AI Assistant Collaboration**.

## How To Use
- Create a new Markdown file per meaningful session using the naming scheme `YYYY-MM-DD-task.md`.
- Copy the template below and fill in every section after each interaction.

````markdown
# Codex Prompt Log

- **Date / Time**: YYYY-MM-DD HH:MM (TZ)
- **Feature / Task**: <link or short descriptor>
- **Context Summary**:
  - Current state / branch:
  - Key constraints (deps, performance, security):
- **Prompt**:
  ```text
  <exact prompt provided to Codex>
  ```
- **Assistant Output Summary**:
  - Proposed solution:
  - Files touched / to create:
  - Follow-up actions requested:
- **Decision**:
  - Accepted / Modified / Rejected (with reason)
- **Validation**:
  - Tests run:
  - Manual checks:
- **Notes / Next Steps**:
  - TODOs:
  - Risks:
````

## Tips
- Update the log immediately after each exchange to maintain accuracy.
- Reference related pull requests, commits, or roadmap items.
- Store sensitive credentials elsewhere—only include high-level descriptions in the log.
