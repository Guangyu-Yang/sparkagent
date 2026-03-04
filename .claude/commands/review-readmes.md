Review all README.md files in this repository to ensure they accurately reflect the current code.

## Steps

1. **Find changed files.** Run `git diff HEAD --name-only` (combined staged and unstaged) to get the list of files that have changed. If there are no uncommitted changes, fall back to `git diff HEAD~1 --name-only` to check the last commit.

2. **Identify affected READMEs.** For each changed file, find the nearest `README.md` in the same directory or the closest parent directory (stop at the repo root). Collect a unique set of READMEs to review. Exclude `.pytest_cache/README.md` and any READMEs under `.claude/worktrees/`.

3. **Review each README against the code.** For each README, read it and then read every source file in its directory. Check for:
   - **File tables:** Does the README list all files that exist? Are any listed files missing or renamed?
   - **Class and function signatures:** Do constructor parameters, method names, and public API descriptions match the actual code?
   - **Data flow descriptions:** Do flow diagrams or prose descriptions match the current control flow?
   - **Imports and dependencies:** Are referenced modules or packages still accurate?
   - **Configuration shapes:** Do config examples match the current schema?

4. **Report findings.** For each README with issues, output:
   - The README path
   - A bulleted list of specific mismatches, each with:
     - What the README says
     - What the code actually has
     - A suggested correction

   If a README is fully accurate, say so briefly.

5. **Summary.** End with a count: how many READMEs were checked, how many have issues, how many are up to date.

## Rules

- Do NOT modify any files. Report only.
- Be specific — quote the exact line from the README and the corresponding code.
- Ignore stylistic preferences (wording, formatting) — focus only on factual accuracy.
- Skip generated files, lockfiles, and non-source directories.
