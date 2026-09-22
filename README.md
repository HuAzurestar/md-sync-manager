# Markdown Focus Workbench

A single-file Markdown workbench for editing, exact heading focus, and synchronization with GitHub, Gitee, and YouTrack. One Markdown document can bind to one remote object. The P0 surface intentionally has no review workflow, database, template generation, audit/full profile, or pair-check feature.

## Run locally

Python 3.10 or newer is recommended.

```powershell
python -m pip install -r requirements.txt
$env:SMMD_CONFIG = "$PWD\data\sync.yaml"
python -m src.controller.server
```

Open <http://127.0.0.1:8000>. The server listens on loopback by default. `SMMD_CONFIG` enables persistent provider changes from the Workbench; without it, provider settings are read-only except for environment overrides.

The Workbench keeps one document open at a time:

1. Open or drag a `.md` file, then edit its source beside the rendered Markdown preview.
2. In **Document / Sections**, use the three explicit steps: refresh the catalog, read one or more selected headings, then write back exactly one selected section.
3. In **Sync**, use **Remote list** to browse and open objects. Use **Transfer** for the grouped Pull, Push, Download, and Upload/New operations.
4. Preview the diff before confirming either a pull or a push. Download saves a browser-edited copy, while Upload/New creates a remote object.

On narrow screens, use the Editor/Preview switch. Pull and push are always preview-plus-confirm operations. Focus apply rejects stale source and leaves the document unchanged.

## Docker

The Compose configuration builds and runs exactly one non-root application container. Port publishing is restricted to host loopback; provider settings and logs use the `sm-md-data` volume.

```powershell
docker compose up --build
```

Open <http://127.0.0.1:8000>. Stop it with:

```powershell
docker compose down
```

`docker compose down` preserves the named volume. Add `--volumes` only when you deliberately want to delete the stored provider configuration and logs.

## Provider configuration

Configure providers in the Workbench or with environment variables. Credentials are held server-side and are never returned by configuration APIs.

```powershell
$env:GITHUB_TOKEN = "..."
$env:GITEE_TOKEN = "..."
$env:YOUTRACK_TOKEN = "..."
```

Optional variables are:

| Variable | Purpose | Default |
| --- | --- | --- |
| `SMMD_HOST` | Server bind address | `127.0.0.1` |
| `SMMD_PORT` | Server port | `8000` |
| `SMMD_CONFIG` | Writable provider YAML | unset |
| `SMMD_LOG_DIR` | Runtime log directory | repository `logs/` |
| `GITHUB_ENABLED`, `GITEE_ENABLED`, `YOUTRACK_ENABLED` | Provider enable flags | bundled YAML value |
| `GITHUB_API_URL`, `GITEE_API_URL`, `YOUTRACK_URL` | Provider endpoints | bundled YAML value |
| `GITHUB_TOKEN`, `GITEE_TOKEN`, `YOUTRACK_TOKEN` | Provider credentials | unset |

The checked-in YouTrack endpoint targets the local development service at `http://localhost:20263`. Do not commit real credentials. When `SMMD_CONFIG` is set, Workbench changes are written atomically to that file; environment values still override stored values at runtime.

## Remote paths

| Object | Collection path | Object path |
| --- | --- | --- |
| GitHub Issue | `github/issues/owner/repo` | `github/issues/owner/repo/12` |
| GitHub Pull Request | `github/pulls/owner/repo` | `github/pulls/owner/repo/12` |
| Gitee Issue | `gitee/issues/owner/repo` | `gitee/issues/owner/repo/IKDETB` |
| Gitee Pull Request | `gitee/pulls/owner/repo` | `gitee/pulls/owner/repo/12` |
| YouTrack Issue | `youtrack/issues/project` | `youtrack/issues/project/12` |
| YouTrack Article | `youtrack/articles/project` | `youtrack/articles/project/12` |

YouTrack paths store the numeric part of a readable ID: `DEMO-39` becomes `youtrack/issues/DEMO/39`, and `DEMO-A-22` becomes `youtrack/articles/DEMO/22`. Project matching is case-insensitive. Collection paths are accepted by list and upload; object paths are accepted by pull and stored as the document's `remote` binding for push.

## Markdown contract

Remote synchronization uses optional YAML Front Matter:

```yaml
---
title: "Document title"
parent: "youtrack/issues/DEMO/10" # optional, upload only
remote: "youtrack/issues/DEMO/39" # optional, exactly one object
---

Markdown body.
```

Only `title`, `parent`, and `remote` are accepted. A parent must use the same route and repository/project as the upload target. Pull Requests do not support parents.

Catalog and focus work with ordinary Markdown too. Catalog returns ATX headings in original source order with their exact heading source, level, text, and line. Headings inside fenced code are ignored. A selector is the full case-sensitive heading source, such as `## Alpha`; duplicate exact headings are rejected as ambiguous.

The selected range starts at that heading and ends before the next heading of the same or higher level, or at end of file. Apply compares the complete retained source before atomically replacing it, so concurrent changes cause a zero-write conflict. No Markdown-file SHA is used.

## CLI

Remote operations:

```powershell
python -m src.controller.main list github/issues/owner/repo
python -m src.controller.main pull C:\docs\local.md --from youtrack/issues/DEMO/39
python -m src.controller.main pull C:\docs\local.md
python -m src.controller.main push C:\docs\local.md
python -m src.controller.main upload C:\docs\local.md --target youtrack/issues/DEMO
python -m src.controller.main upload C:\docs\local.md --target github/pulls/owner/repo --base main --head feature/docs
```

Catalog and focus operations:

```powershell
python -m src.controller.main catalog C:\docs\local.md
python -m src.controller.main focus-read C:\docs\local.md --selector "## Alpha"
python -m src.controller.main focus-read C:\docs\local.md --selector "## Alpha" --selector "## Omega"
python -m src.controller.main focus-apply C:\docs\local.md --selector "## Alpha" --expected-file retained.md --replacement-file replacement.md
```

`focus-read` prints JSON containing each complete retained range in its `source` field. Decode and save that field alone as `retained.md`; write the desired complete replacement section to `replacement.md`. `focus-apply` succeeds only while the file still contains the exact retained source.

Safety rules:

- `pull` reads one remote and overwrites only local title/body. The Workbench API requires preview and explicit confirmation before applying it.
- `push` requires `remote`, updates only title/body, and never creates an object. The Workbench API requires preview and explicit confirmation before applying it.
- `upload` requires no `remote` and an explicit collection target; it creates and binds one object.
- A partial multi-step provider result is reported explicitly instead of being presented as full success.
- Until stable error classes are introduced, API validation and provider failures return HTTP 500 with a readable error envelope.

## Verification

Install development dependencies and run all unit, CLI, API, source-gate, and browser tests:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
node --check src/ui/app.js
docker compose config --quiet
docker build --tag sm-md:local .
```

Browser tests use installed Edge or Chrome on Windows. The acceptance scenarios and their requirement mapping are documented in `tests/pirc14_acceptance_matrix.md`.

## Update from GitHub

The packaged updater can check for or apply a fast-forward update from a configured GitHub `origin`:

```powershell
python scripts/update_from_github.py --check
python scripts/update_from_github.py
```

It refuses dirty worktrees, non-GitHub remotes, and divergent history. It never commits, stashes, resets, or discards local work.
