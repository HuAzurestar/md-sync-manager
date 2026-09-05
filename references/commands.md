# CLI reference

## Paths

Resolve two independent absolute paths before invoking the CLI:

- `<SKILL_PATH>` is the directory containing `SKILL.md`, `requirements.txt`, and `src/`.
- `<LOCAL_MD_PATH>` is the Markdown file to transfer. It may be outside `<SKILL_PATH>`.

Verify `<SKILL_PATH>/src/controller/main.py` exists. Enter `<SKILL_PATH>` only so Python resolves this skill's module, and always pass `<LOCAL_MD_PATH>` explicitly:

```powershell
$skillPath = "<SKILL_PATH>"
$localMdPath = "<LOCAL_MD_PATH>"

Push-Location -LiteralPath $skillPath
try {
    python -m src.controller.main pull $localMdPath
} finally {
    Pop-Location
}
```

## Resource paths

```text
github/issues/<owner>/<repo>[/<id>]
github/pulls/<owner>/<repo>[/<id>]
gitee/issues/<owner>/<repo>[/<id>]
gitee/pulls/<owner>/<repo>[/<id>]
youtrack/issues/<project>[/<number>]
youtrack/articles/<project>[/<number>]
```

For YouTrack, use only the numeric suffix: `DEMO-39` is `youtrack/issues/DEMO/39`; `DEMO-A-22` is `youtrack/articles/DEMO/22`. Project matching is case-insensitive.

Use collection paths without an ID for `list` and `upload`. Use object paths with an ID for `pull`, `remote`, and `parent`.

## Operations

List IDs and titles without changing local or remote content:

```powershell
python -m src.controller.main list "github/issues/owner/repo"
python -m src.controller.main list "youtrack/articles/DEMO"
```

Pull an explicit object into a local file, or refresh from the file's existing `remote`:

```powershell
python -m src.controller.main pull "<LOCAL_MD_PATH>" --from "youtrack/issues/DEMO/39"
python -m src.controller.main pull "<LOCAL_MD_PATH>"
```

Push only when YAML already contains `remote`. Push updates title/body and never creates:

```powershell
python -m src.controller.main push "<LOCAL_MD_PATH>"
```

Upload only when YAML has no `remote`, the user explicitly wants creation, and the collection target is known:

```powershell
python -m src.controller.main upload "<LOCAL_MD_PATH>" --target "youtrack/issues/DEMO"
python -m src.controller.main upload "<LOCAL_MD_PATH>" --target "youtrack/issues/DEMO" --parent "youtrack/issues/DEMO/10"
python -m src.controller.main upload "<LOCAL_MD_PATH>" --target "github/pulls/owner/repo" --base "main" --head "feature/docs"
```

Never substitute `upload` for a failed or ambiguous `push`. Inspect YAML and use `list` to resolve IDs before creating remote objects. Pull Request upload requires `--base` and `--head`; Pull Requests do not accept `parent`.

## Document contract

```yaml
---
title: "Document title"
parent: "youtrack/issues/DEMO/10" # optional, upload only
remote: "youtrack/issues/DEMO/39" # optional, one scalar object path
---

Markdown body.
```

Accept only `title`, optional `parent`, optional scalar `remote`, and the Markdown body. Do not add status, labels, assignee, priority, relations, or multiple remote mappings.
