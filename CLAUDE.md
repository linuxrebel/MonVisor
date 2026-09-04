# CLAUDE.md — MonVisor

## Branch policy

All work happens on the `development` branch, never directly on `main`.

Before starting any code or changes, first verify the current branch:

```bash
git branch --show-current
```

If it is not `development`, switch to it (`git checkout development`) before editing. `main` is reserved for releases/merges only.

### Merge workflow

Commit on `development` → push → checkout `main` → `git merge --ff-only development` → push main → checkout `development`.

### Before editing or merging

- **Always `git pull` first.** Remote changes may have been pushed from another session or machine.
- Commits are authored as James's user — do not configure or override `user.name` / `user.email`. The system gitconfig is already correct.
- Never commit build output or release tarballs (`build/`, `dist/`, packages). They belong on the GitHub Releases page only.

## Workflow

- **Ask before coding.** Before writing code or making changes, ask first and get the go-ahead.
- **Plan first, act second.** Present a plan before implementing. No changes until the plan is agreed.

