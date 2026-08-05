# Resolved paths

## Roots

| Role | Resolved absolute path | Status |
|---|---|---|
| Lamha project root | `C:\Users\mhyah\Downloads\Code\Lamha` | CURRENT VERIFIED PATH |
| Source corpus root | `C:\Users\mhyah\Downloads\Code\Lamha\Codebase` | CURRENT VERIFIED PATH |
| Planning/evidence root | `C:\Users\mhyah\Downloads\Code\Lamha\graphify` | CURRENT VERIFIED PATH; Windows path matching is case-insensitive, so this is the canonical `Graphify/` authority root |
| Master Plan root | `C:\Users\mhyah\Downloads\Code\Lamha\graphify\Master Plan` | CURRENT VERIFIED PATH |
| Raw Graphify target | `C:\Users\mhyah\Downloads\Code\Lamha\graphify\graphify-out` | PLANNED TARGET PATH; outside `Codebase/` |

## Repository state

- The Lamha project root is not a Git worktree.
- `Codebase/` is not a Git worktree and contains no `.git` metadata.
- Branch, staged, modified, untracked, ignored, and Git-submodule status are unavailable for this unpacked snapshot.
- `Codebase/.gitmodules` declares `e2e/test-assets` with upstream URL `https://github.com/immich-app/test-assets`; the declared directory is empty in this snapshot.
- No additional repository roots were found.
- A recursive project scan found no symlinks, junctions, or reparse points.

## Execution boundary

- Permitted source reads: `C:\Users\mhyah\Downloads\Code\Lamha\Codebase`.
- Permitted writes: the three authoritative files under `Graphify/Master Plan/` during repair and planning/evidence under `C:\Users\mhyah\Downloads\Code\Lamha\graphify`.
- Forbidden writes: every path under `C:\Users\mhyah\Downloads\Code\Lamha\Codebase`.
- Commands that may create dependency, build, test, lint, formatter, migration, code-generation, cache, coverage, or package output are recorded but not executed in the source snapshot.

