# README Conventions

## Structure
- **Main README** (`README.md`): Concise entry point — features, installation, quick start, and brief section overviews. Link to subfolder READMEs for details.
- **Subfolder READMEs** (`sparkagent/*/README.md`): Code architecture docs — files, classes, ABCs, data flow. Include a back-link to the relevant main README section.

## Rules
1. **No project structure tree in main README.** Subfolder READMEs document their own contents.
2. **No full config examples in main README.** Config is managed by CLI commands, not hand-edited. Link to `sparkagent/config/README.md` for schema details.
3. **Cross-reference, don't duplicate.** When content exists in a subfolder README, the main README should summarize in 1-2 sentences and link there.
4. **Back-links in subfolder READMEs.** Each subfolder README that is linked from the main README should have a blockquote back-link to the relevant main README section.
5. **Keep the main README scannable.** Prefer short summaries with links over detailed tables, config blocks, or directory trees.
