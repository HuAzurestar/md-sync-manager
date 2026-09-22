# PIRC-14 P0 acceptance matrix

This matrix is the executable contract for the focused Markdown sync workbench. Test names use the `AT-*` identifiers below so that unit, CLI, API, browser, and Docker coverage can be traced back to a confirmed requirement.

## Fixed semantics

- A heading range includes its ATX heading line and ends immediately before the next heading of the same or higher level, or at end of file.
- A focus selector is the complete, case-sensitive heading source returned by catalog, such as `## Alpha`. Display numbers, heading keys, record IDs, and fuzzy matching are not selectors.
- Catalog and multi-select focus reads return source-file order, regardless of selector input order.
- Focus apply compares the complete source range returned by the earlier read. Any mismatch rejects the operation with zero writes.
- P0 does not expose review, audit/full profiles, template generation, pair checks, or Markdown-file SHA fields.

## Canonical fixtures

`catalog-basic.md` contains Front Matter, `# Root`, `## Alpha`, a fenced `# fake`, `### Child`, and `## Omega`. Catalog returns only the four real headings in source order. The `## Alpha` range includes its child and ends before `## Omega`.

`catalog-duplicates.md` contains two exact `## Same` headings. Both remain visible in catalog; focus read and apply report ambiguity and never select the first implicitly.

`focus-case.md` contains `## Alpha`, `## alpha`, and `## Tail`. The first two selectors resolve separately. A request listing `## alpha` before `## Alpha` still returns source order.

`focus-eof.md` contains Front Matter, `# Root`, and terminal `## Tail`. Replacing Tail preserves Front Matter, Root, unrelated bytes, and newline style.

## Traceable scenarios

| ID | Requirements | Layer | Action and expected result | Implementation task |
| --- | --- | --- | --- | --- |
| AT-001 | REQ-001, REQ-007 | Git/source gate | `feature/PIRC-18` has the implementation-time `main` as ancestor, contains no old-candidate-only commit, and registers only approved P0 capabilities | DEV-01, TEST-02 |
| AT-002 | REQ-002 | unit | GitHub, Gitee, and YouTrack fake providers support collection list, open/download, pull, push, and upload/new; a document rejects a second different remote binding | DEV-02 |
| AT-003 | REQ-002, REQ-005 | unit/API | Mixed provider results return per-item outcomes and top-level `partial`; credentials never appear in responses or logs | DEV-02, DEV-03 |
| AT-004 | REQ-002, REQ-005 | API | Initial pull or push returns a directional diff and confirmation token without changing either side; valid confirmation applies it, while stale/mismatched confirmation performs zero writes | DEV-03, DEV-07, REWORK-04 |
| AT-005 | REQ-003 | browser | One ordinary Markdown file can be opened, edited beside a rendered preview, cataloged, multi-read, single-section-applied, and synced through grouped preview/confirm controls; no review control exists | DEV-06, REWORK-04 |
| AT-006 | REQ-003, REQ-005 | browser | Dirty navigation, file replacement, and pull are guarded; cancel preserves work, confirm allows replacement; desktop and narrow layouts complete the same flow | DEV-07 |
| AT-007 | REQ-004 | unit/CLI | `catalog-basic.md` returns heading source, level, text, line, and source order; fenced fake headings are ignored; CLI display numbering never enters selectors | DEV-04 |
| AT-008 | REQ-004 | unit/CLI | Plain Markdown without PIRC Front Matter works; missing, non-file, and unreadable paths produce nonzero exits and readable errors | DEV-04 |
| AT-009 | REQ-004, REQ-005 | unit/API | Exact case-sensitive single and multi-read returns selector, line range, and full source range in catalog order | DEV-05 |
| AT-010 | REQ-004, REQ-005 | unit/API | Duplicate, missing, wrong-case, and fuzzy selectors fail explicitly and perform zero writes | DEV-05 |
| AT-011 | REQ-004, REQ-005 | unit/API | Same/higher-level and EOF boundaries are exact; successful replacement preserves Front Matter and all non-target content | DEV-05 |
| AT-012 | REQ-005 | unit/API | External target change after read causes conflict and byte-identical file preservation; success uses same-directory temporary output and atomic replace | DEV-05 |
| AT-013 | REQ-005 | API | Until stable error classes exist, internal/provider failures return HTTP 500 with a readable message and no traceback, credentials, or local secrets | DEV-03 |
| AT-014 | REQ-006, REQ-007 | unit/API/browser/source gate | No review routes, DTOs, services, repositories, database setup, CLI, UI, environment variables, or capabilities exist; deferred audit/full, template, and pair-check entries are absent | DEV-01, DEV-08, TEST-02 |
| AT-015 | REQ-003, REQ-006, REQ-007 | Docker smoke | A clean single-container build defaults to loopback, exposes health/capabilities, completes catalog → read → apply, and has no review database migration or dependency | DEV-08, TEST-02 |

Direct coverage is complete: REQ-001 → AT-001; REQ-002 → AT-002/003/004; REQ-003 → AT-005/006/015; REQ-004 → AT-007–011; REQ-005 → AT-003/004/006/009–013; REQ-006 → AT-014/015; REQ-007 → AT-001/014/015.

## Contract examples

Catalog entries use this shape:

```json
{"heading":"## Alpha","level":2,"text":"Alpha","line":7}
```

Focus read accepts selectors and returns the complete retained source:

```json
{
  "path":"fixtures/focus-case.md",
  "selectors":["## alpha","## Alpha"]
}
```

```json
{
  "sections":[
    {"selector":"## Alpha","start_line":2,"end_line":3,"source":"## Alpha\nupper\n"},
    {"selector":"## alpha","start_line":4,"end_line":5,"source":"## alpha\nlower\n"}
  ]
}
```

Focus apply carries the retained source instead of a file SHA:

```json
{
  "path":"fixtures/focus-eof.md",
  "selector":"## Tail",
  "expected_source":"## Tail\ntail body\n",
  "replacement":"## Tail\nnew tail\n"
}
```

Partial sync is explicit:

```json
{
  "status":"partial",
  "direction":"push",
  "results":[
    {"remote":"docs/a.md","status":"success"},
    {"remote":"docs/b.md","status":"failed","message":"permission denied"}
  ]
}
```

No response may contain provider credentials, passwords, Markdown-file SHA fields, or review state.
