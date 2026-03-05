Push the current branch and open a GitHub pull request against main.

## Steps

1. **Determine the environment.** Run `git worktree list` and `git branch --show-current` to determine:
   - The current branch name.
   - Whether you are in a worktree or the main repo directory.
   - The path to the main worktree (first line of `git worktree list`).

2. **Ensure you are on a branch.** If the current branch is `main`:
   - Ask the user for a branch name. Suggest one based on recent commit messages or staged changes (e.g., `feat/add-submit-pr-command`).
   - Create the branch with `git checkout -b <branch>`.
   - If no changes exist to submit, inform the user and stop.

3. **Fetch and rebase onto remote main.** Run `git fetch origin main`. Then run `git rebase origin/main`. If the rebase has conflicts, pause and show the conflicting files to the user. Let the user decide how to resolve them before continuing.

4. **Stage all changes.** Run `git status --short` to see untracked and modified files. If there are any, run `git add -A` to stage them all. Files excluded by `.gitignore` will not appear in `git status`, so this is safe.

5. **Commit.** If there are staged changes (check with `git diff --cached --quiet`; non-zero exit means staged changes exist):
   - Show the user `git diff --cached --stat` and ask for a commit message.
   - Create the commit. Do NOT add any `Co-Authored-By` lines or AI attribution — follow the `commit-identity` skill.
   - If there are no staged changes, inform the user. If there are also no unpushed commits (check with `git log origin/main..HEAD --oneline`), stop — there is nothing to submit.

6. **Push the branch to remote.** Run `git push origin HEAD -u`. If the push is rejected:
   - If the remote branch has diverged, re-run step 3 (fetch + rebase) and retry once. If it fails again, stop and ask the user.
   - If the remote branch does not exist, the push should succeed with `-u` creating it.

7. **Check for an existing PR.** Run `gh pr view --json url,state 2>/dev/null` to check if a PR already exists for this branch.
   - If a PR exists and is **open**: show its URL and ask the user whether to update the existing PR's title/description or leave it as-is. If update, proceed to step 8 to collect new title/description, then run `gh pr edit <number> --title "<title>" --body "<body>"`. Then skip to step 9.
   - If a PR exists and is **merged** or **closed**: inform the user and stop. They need a new branch for a new PR.
   - If no PR exists: continue to step 8.

8. **Collect PR details and create the PR.** Show the user a summary of what will be in the PR:
   - Run `git log origin/main..HEAD --oneline` to list the commits.
   - Run `git diff origin/main..HEAD --stat` to show a file-level summary.
   - Ask the user for a PR title and description. Suggest a title based on the commit messages.
   - Run `gh pr create --base main --title "<title>" --body "<body>"`. Do NOT add any AI attribution footer — follow the `commit-identity` skill.

9. **Show the result.** Print the PR URL returned by `gh pr create` (or `gh pr view` if updating). Ask the user if they would like to open it in the browser. If yes, run `gh pr view --web`.

## Rules

- **Respect `commit-identity`.** Never add `Co-Authored-By` lines for Claude/AI/Anthropic. Never include AI attribution footers in PR titles or descriptions. Write everything as if the local user authored it.
- **Always rebase, never merge.** Use `git rebase origin/main` to keep history linear.
- **Ask before destructive actions.** Show conflicts, never force-push, never delete branches without asking.
- **Never `git checkout main` in a worktree.** If you need to create a branch in a worktree, create it from the current HEAD.
- **Abort on ambiguity.** If state is unexpected (detached HEAD, missing remote, `gh` not authenticated), describe the situation to the user rather than guessing.
- **One retry for push races.** If push fails because remote advanced, re-fetch and rebase once, then stop.
- **Never force-push.** Use only regular `git push`. If the remote branch has diverged in a way that cannot be resolved by rebase, stop and ask the user.
