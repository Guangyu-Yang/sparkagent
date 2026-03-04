Commit all current changes to remote main and optionally clean up the working branch/worktree.

## Steps

1. **Determine the environment.** Run `git worktree list` and `git branch --show-current` to determine:
   - The current branch name.
   - Whether you are in a worktree or the main repo directory.
   - The path to the main worktree (first line of `git worktree list`).

2. **Fetch and reconcile with remote main.** Run `git fetch origin main`. Then run `git rebase origin/main`. If the rebase has conflicts, pause and show the conflicting files to the user. Let the user decide how to resolve them before continuing.

3. **Stage all changes.** Run `git status --short` to see untracked and modified files. If there are any, run `git add -A` to stage them all. Files excluded by `.gitignore` will not appear in `git status`, so this is safe.

4. **Commit.** If there are staged changes (check with `git diff --cached --quiet`; non-zero exit means staged changes exist):
   - Show the user `git diff --cached --stat` and ask for a commit message.
   - Create the commit. Do NOT add any `Co-Authored-By` lines or AI attribution — follow the `commit-identity` skill.
   - If there are no staged changes, inform the user and ask whether to continue pushing any existing unpushed commits or to stop.

5. **Push changes to remote main.**

   **If on `main`:** Run `git push origin main`.

   **If on a branch (including worktree branch):**
   - The branch is already rebased onto `origin/main` (step 2), so this is a fast-forward.
   - Run `git push origin HEAD:main`.
   - If rejected (non-fast-forward), re-run step 2 (fetch + rebase) and retry once. If it fails again, stop and ask the user.
   - After success, run `git fetch origin main:main` to update the local `main` ref without checking it out.

6. **Verify clean state.** Run `git status --short`. If uncommitted changes remain, list them and warn the user. Otherwise confirm all changes are on remote `main`.

7. **Cleanup prompt.** If the current branch is NOT `main`:
   - Ask: "Remove branch `<branch>` and its worktree, or keep it?"
   - If remove and in a worktree: run `git worktree remove <path>` from the main worktree directory, then `git branch -d <branch>`.
   - If remove and on a regular branch: run `git checkout main`, then `git branch -d <branch>`.
   - If keep: do nothing.
   - If on `main`: skip this step.

## Rules

- **Respect `commit-identity`.** Never add `Co-Authored-By` lines for Claude/AI/Anthropic. Write messages as the local user.
- **Always rebase, never merge.** Use `git rebase origin/main` to keep history linear.
- **Ask before destructive actions.** Show conflicts, never force-push, never delete branches without asking.
- **Never `git checkout main` in a worktree.** Use `git push origin HEAD:main` + `git fetch origin main:main` instead.
- **Abort on ambiguity.** If state is unexpected (detached HEAD, missing main worktree), describe the situation to the user rather than guessing.
- **One retry for push races.** If push fails because remote advanced, re-fetch and rebase once, then stop.
