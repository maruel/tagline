# AGENTS.md File Index

A generated source-file map for coding agents.

`agents-file-index` maintains a generated file index in `AGENTS.md`. The index
helps coding agents understand a repository's source files without a
repository-wide search.

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

The updater locates its own Git repository, so it may be invoked from any
subdirectory of that repository.

## Opt in a directory

Add these markers to the directory's `AGENTS.md`:

```markdown
<!-- BEGIN FILE INDEX -->
<!-- END FILE INDEX -->
```

The updater discovers tracked `AGENTS.md` files containing these markers,
indexes tracked files below each one, and replaces the content between the
markers. A nested opted-in directory becomes its own index scope.

Descriptions come from the first applicable comment near the start of a source
file. Files without a supported comment convention are skipped. Supported files
without a description cause check mode to fail.

## CLAUDE.md compatibility

For every tracked `AGENTS.md`, the updater ensures a sibling symlink exists:

```text
CLAUDE.md -> AGENTS.md
```

Commit that symlink with its `AGENTS.md`. Tools that look for either filename
then read the same instructions from one source of truth.

## Example

See the root [AGENTS.md](AGENTS.md) for a current generated index.
