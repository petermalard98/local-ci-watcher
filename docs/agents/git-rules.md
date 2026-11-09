# Git rules

## Commits

- Commit or push only when asked.
- On default branch: create a new branch before committing.
- Make new commits. Do not amend existing commits.
- Never skip hooks (`--no-verify`) or signing. If a hook fails, fix the cause.
- No interactive commands (`rebase -i`, `add -i`).
- Do not end commit messages with:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Pull requests

- Do not end PR descriptions with:
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
- No bare `@name` unless notifying a real user. Put placeholders in backticks.

## Destructive operations

- Confirm before `reset --hard`, force push, `checkout --`, branch deletion.
- Prefer a safer alternative when one exists.
