---
name: md-sync-manager
description: Safely list, pull, update, or explicitly create one GitHub, Gitee, or YouTrack object from a Markdown file with a single remote binding.
---

# Markdown Sync Manager

Use this skill to transfer a Markdown title and body between one local file and one remote Issue, Pull Request, or Article.

Keep these boundaries:

- `push` updates an existing binding and never creates.
- `upload` is the only creation command and requires explicit creation intent.
- `parent` applies only during upload; omit it when no parent is requested.
- Do not add project-management metadata or multiple remotes.

Before selecting or running a command, read [references/commands.md](references/commands.md). It defines the required `<SKILL_PATH>` and `<LOCAL_MD_PATH>`, resource paths, YAML contract, and command-specific safety rules.

When the user asks to check for or apply Skill updates from GitHub, read [references/update.md](references/update.md) and use its bundled updater.
