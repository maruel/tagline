# AGENTS.md File Index

A generated source-file map for coding agents.

`agents-file-index` maintains a generated file index in `AGENTS.md`. The index
helps coding agents understand a repository's source files without a
repository-wide search.

The [script in this repository](https://github.com/maruel/tagline/blob/main/update_agents_file_index.py)
is the canonical source. Make improvements here first, then copy the same script
to repositories that use it and refresh their indexes when needed.

## Requirements

- Python 3.10 or later
- Git

## Use

Run the updater after adding or changing a source-file description:

```bash
python3 update_agents_file_index.py
```

CI uses check mode, which reports stale indexes without modifying files:

```bash
python3 update_agents_file_index.py --check
```

The working directory selects which indexes to update: running from the root
updates every opted-in index, while running from a subdirectory updates indexes
in that subtree. A scoped run can leave parent indexes stale; run from the root
to refresh or check the whole repository. The working directory must be inside
the repository containing the script, and its subtree must contain an opted-in
index.

## Opt in a directory

Add these markers to the directory's `AGENTS.md`:

```markdown
<!-- BEGIN FILE INDEX -->
<!-- END FILE INDEX -->
```

The updater discovers non-ignored `AGENTS.md` files containing these markers,
indexes tracked and non-ignored untracked files below each one, and replaces the content between the
markers. A nested opted-in directory becomes its own index scope.

Add glob patterns to `.agents-index-ignore` to exclude files from indexes.
Patterns are relative to the directory containing the ignore file and apply to
its descendants. Nested ignore files add exclusions to those inherited from
their parents; they cannot override a parent exclusion. Directories without
markers remain unchanged.

Descriptions come from the first applicable comment near the start of a source
file. Files without a supported comment convention are skipped. Supported files
without a description cause the updater to fail. Put Python summaries before
inline script metadata, and Markdown summaries before the first front-matter field.

## Example

See the root [AGENTS.md](AGENTS.md?plain=1) for a current generated index.
