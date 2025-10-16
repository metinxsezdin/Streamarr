# Expo Dependency Policy

The Expo manager workspace under `apps/expo/` is installed with **npm**. To keep the build reproducible across local environments, CI, and EAS, we commit the generated `package-lock.json` alongside `package.json`.

## Why the lockfile stays in git
- npm resolves exact package versions through the lockfile; removing it causes "floating" installs that can break Expo projects when upstream packages ship breaking changes.
- The Expo CLI, Metro bundler, and EAS build runners all reuse the lockfile when present, so keeping it avoids "works on my machine" drift between contributors.
- Our CI commands (`npm --prefix apps/expo run typecheck` and future lint/test jobs) implicitly rely on the lockfile to install a deterministic dependency graph.

## Workflow guidance
1. Whenever dependencies change in `apps/expo/package.json`, run `npm install` from that directory so the lockfile stays in sync.
2. Commit both `package.json` **and** `package-lock.json` in the same change set. This keeps review diffs coherent and prevents CI from re-generating the lockfile with unexpected updates.
3. If merge conflicts occur, re-run `npm install` (or `npm install --lockfile-version=2` for this repo) and commit the regenerated lockfile. Avoid resolving conflicts manually; npm will produce a consistent result faster and with fewer mistakes.

Following this policy answers the question "do we need the `package-lock.json`?" with a clear **yes**—it is required for deterministic Expo builds in this repository.
