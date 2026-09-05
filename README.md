# md-sync-manager

A small Markdown transport for GitHub, Gitee, and YouTrack. Each Markdown file binds to exactly one remote object. The tool moves only `title` and Markdown body; `parent` is used only when creating an object.

## Install

```powershell
python -m pip install -r requirements.txt
```

## Resource paths

| Object | Collection path | Object path |
|---|---|---|
| GitHub Issue | `github/issues/owner/repo` | `github/issues/owner/repo/12` |
| GitHub Pull Request | `github/pulls/owner/repo` | `github/pulls/owner/repo/12` |
| Gitee Issue | `gitee/issues/owner/repo` | `gitee/issues/owner/repo/IKDETB` |
| Gitee Pull Request | `gitee/pulls/owner/repo` | `gitee/pulls/owner/repo/12` |
| YouTrack Issue | `youtrack/issues/project` | `youtrack/issues/project/12` |
| YouTrack Article | `youtrack/articles/project` | `youtrack/articles/project/12` |

YouTrack paths store only the numeric part of a readable ID. For example, `DEMO-39` becomes `youtrack/issues/DEMO/39`, and `DEMO-A-22` becomes `youtrack/articles/DEMO/22`. Project name matching is case-insensitive.

A collection path is accepted by `list` and `upload`. An object path is accepted by `pull` and stored as `remote` for `push`.

## Commands

```powershell
# Show the first 100 IDs and titles in a collection.
python -m src.controller.main list github/issues/owner/repo

# Create or replace a local file from an explicit remote object.
python -m src.controller.main pull C:\docs\local.md --from youtrack/issues/DEMO/39

# Refresh an existing local file from its YAML remote.
python -m src.controller.main pull C:\docs\local.md

# Update the bound remote. This command never creates an object.
python -m src.controller.main push C:\docs\local.md

# Explicitly create and bind one new object. The file must not have remote.
python -m src.controller.main upload C:\docs\local.md --target youtrack/issues/DEMO
python -m src.controller.main upload C:\docs\local.md --target youtrack/issues/DEMO --parent youtrack/issues/DEMO/10

# Pull Request creation requires the remote branches.
python -m src.controller.main upload C:\docs\local.md --target github/pulls/owner/repo --base main --head feature/docs
```

`list` prints a two-column `ID` / `TITLE` table. YouTrack rows also use numeric IDs, so the output can be appended directly to the corresponding collection path.

## Markdown contract

```yaml
---
title: "Document title"
parent: "youtrack/issues/DEMO/10" # optional, upload only
remote: "youtrack/issues/DEMO/39" # optional, exactly one object
---

Markdown body.
```

Only `title`, `parent`, and `remote` are accepted in Front Matter. `--parent` overrides the YAML parent and writes the canonical path back to the file. A parent must use the same route and repository/project as the upload target. Pull Requests do not support parents.

## Safety

- `pull` reads one remote and overwrites the local title/body. It never writes remote state.
- `push` requires `remote` and updates only title/body. It never creates anything and ignores `parent`.
- `upload` requires no `remote` and an explicit collection `--target`. It creates one object and then saves its object path.
- Status, labels, assignee, priority, relations, and other project-management fields are outside this tool's contract.

## Configuration

Provider endpoints and token sources live in `src/core/sync.yaml`. A provider is registered when `enabled` is true and its token resolves to a non-empty value.

```powershell
$env:GITHUB_TOKEN = "..."
$env:GITEE_TOKEN = "..."
$env:YOUTRACK_TOKEN = "..."
```

An explicit `token` in `sync.yaml` takes precedence over `token_env`. Do not commit real credentials. The checked-in YouTrack endpoint uses `http://localhost:20263` for the local development service.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Update from GitHub

The Skill package can check for or apply a fast-forward update from its configured GitHub `origin`:

```powershell
python scripts/update_from_github.py --check
python scripts/update_from_github.py
```

The updater refuses dirty worktrees, non-GitHub remotes, and divergent history. It never commits, stashes, resets, or discards local work.
