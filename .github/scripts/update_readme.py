#!/usr/bin/env python3
# Synchronize the README file-index example with the generated root index.

"""Synchronize README.md's file-index example with the root AGENTS.md index."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

INDEX_PATTERN = re.compile(
    r"(?P<index><!-- BEGIN FILE INDEX -->\n.*?<!-- END FILE INDEX -->)", re.DOTALL
)
README_EXAMPLE_PATTERN = re.compile(
    r"(?P<prefix>## Example\n\n```markdown\n)"
    r"(?P<index><!-- BEGIN FILE INDEX -->\n.*?<!-- END FILE INDEX -->)"
    r"(?P<suffix>\n```)",
    re.DOTALL,
)


def get_git_root() -> Path | None:
    """Return the root of the repository containing this script."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            cwd=Path(__file__).resolve().parent,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"Error locating git repository: {error}", file=sys.stderr)
        return None
    return Path(result.stdout.strip())


def get_file_index(agents_file: Path) -> str | None:
    """Return the generated file index in agents_file, or None if it is absent."""
    match = INDEX_PATTERN.search(agents_file.read_text(encoding="utf-8"))
    if match is None:
        print(f"Error: {agents_file} has no file index.", file=sys.stderr)
        return None
    return match.group("index")


def remove_internal_script_entry(index: str, script_path: str) -> str:
    """Return index without the entry for this internal script."""
    entry_prefix = f"- `{script_path}`:"
    return "\n".join(line for line in index.splitlines() if not line.startswith(entry_prefix))


def update_readme(readme_file: Path, index: str, check: bool) -> bool:
    """Update or check README's example. Return whether it changed or needs changing."""
    original = readme_file.read_text(encoding="utf-8")
    match = README_EXAMPLE_PATTERN.search(original)
    if match is None:
        print(f"Error: {readme_file} has no file-index example.", file=sys.stderr)
        return True
    updated = README_EXAMPLE_PATTERN.sub(
        lambda current: f"{current.group('prefix')}{index}{current.group('suffix')}", original
    )
    if updated == original:
        return False
    if check:
        print(f"Error: {readme_file} file-index example is out of date.", file=sys.stderr)
        return True
    readme_file.write_text(updated, encoding="utf-8")
    print(f"Updated: {readme_file}")
    return True


def main() -> int:
    """Parse arguments and synchronize README.md's file-index example."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="check that the README example is up to date without modifying it",
    )
    args = parser.parse_args()

    git_root = get_git_root()
    if git_root is None:
        return 1
    index = get_file_index(git_root / "AGENTS.md")
    if index is None:
        return 1
    script_path = Path(__file__).resolve().relative_to(git_root).as_posix()
    example = remove_internal_script_entry(index, script_path)
    return int(update_readme(git_root / "README.md", example, check=args.check))


if __name__ == "__main__":
    sys.exit(main())
