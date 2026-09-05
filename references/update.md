# Update from GitHub

Use the bundled updater when the user asks to check for or install a newer version of this Skill from its configured GitHub remote. Updating changes the entire Skill package so `SKILL.md`, references, scripts, and `src` remain compatible.

Check whether the current branch has a fast-forward update:

```powershell
python "<SKILL_PATH>/scripts/update_from_github.py" --check
```

Apply the update:

```powershell
python "<SKILL_PATH>/scripts/update_from_github.py"
```

Use `--remote <name>` or `--branch <name>` only when the user identifies a non-default configured GitHub remote or branch.

The updater refuses to run when:

- `<SKILL_PATH>` is not the root of a Git repository.
- The selected remote is not hosted on `github.com`.
- The working tree contains staged, unstaged, or untracked changes.
- The fetched branch cannot fast-forward the current commit.

Do not automatically commit, stash, reset, or discard work to bypass a refusal. Report the reason and let the user decide how to make the working tree clean or resolve divergent history.
