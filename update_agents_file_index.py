#!/usr/bin/env python3
# Copyright 2025 Marc-Antoine Ruel. All rights reserved.
# Use of this source code is governed under the Apache License, Version 2.0
# that can be found in the LICENSE file.

"""Maintain the generated file index in AGENTS.md files.

To opt in a directory, add these two markers to its AGENTS.md:

    <!-- BEGIN FILE INDEX -->
    <!-- END FILE INDEX -->

The script discovers tracked AGENTS.md files containing the markers, generates
an index from source-file comments, and injects it between the markers. It also
ensures each tracked AGENTS.md has a sibling CLAUDE.md -> AGENTS.md symlink.
"""

import argparse
import fnmatch
import os
import re
import subprocess
import sys


def get_git_root() -> str | None:
    """Return the root of the repository containing this script."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            cwd=os.path.dirname(os.path.realpath(__file__)),
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"Error locating git repository: {error}", file=sys.stderr)
        return None
    return result.stdout.strip()


def get_script_path(git_root: str) -> str:
    """Return this script's path relative to git_root."""
    return os.path.relpath(os.path.realpath(__file__), git_root).replace(os.sep, "/")


def get_git_files(git_root: str) -> list[str]:
    """Return the files tracked by git_root, or [] on failure."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            capture_output=True,
            cwd=git_root,
            text=True,
            check=True,
        )
        return [
            f
            for f in result.stdout.split("\0")
            if f
            and (
                os.path.exists(os.path.join(git_root, f))
                or os.path.islink(os.path.join(git_root, f))
            )
        ]
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"Error listing git files: {error}", file=sys.stderr)
        return []


def _py_docstring(lines: list[str], i: int) -> str:
    """Extract the description from a Python triple-quoted docstring starting at lines[i].

    Returns the description string, or "" if none found.
    """
    sline = lines[i].strip()
    quote = sline[:3]
    # Single-line docstring: """text"""
    if sline.endswith(quote) and len(sline) > 6:
        return sline[3:-3].strip()
    # Multi-line: return the first content line.
    content = sline[3:].strip()
    if content:
        return content
    # Opening quotes on their own line; use next non-empty line.
    for j in range(i + 1, len(lines)):
        if lines[j] and lines[j].strip():
            return lines[j].strip()
    return ""


def _c_style_block_comment(lines: list[str], i: int) -> str:
    """Extract the description from a C-style block comment starting at lines[i]."""
    comment_parts: list[str] = []
    for line_index, line in enumerate(lines[i:]):
        text = line.strip()
        if line_index == 0:
            text = text[2:].strip()
        end = text.find("*/")
        if end >= 0:
            text = text[:end].strip()
        text = text.lstrip("*").strip()
        if text:
            comment_parts.append(text)
        if end >= 0:
            break
    return " ".join(comment_parts)


def get_file_description(filepath: str) -> str | None:
    """Return the description for a file, or None if not applicable.

    Returns None if the file type has no comment convention (or is explicitly
    excluded). Returns "" if the file supports comments but has no description,
    which is treated as an error by callers.
    """
    # Glob patterns mapping filenames to their comment prefix. None skips the file.
    comment_prefixes: dict[str, str | None] = {
        "*.d.ts": None,
        "pnpm-lock.yaml": None,
        "*.cjs": "//",
        "*.css": "/*",
        "*.go": "//",
        "*.h": "//",
        "*.js": "//",
        "*.kt": "//",
        "*.md": "#",
        "*.mjs": "//",
        "*.py": "#",
        "*.sh": "#",
        "*.swift": "//",
        "*.service": "#",
        "*.timer": "#",
        "*.toml": "#",
        "*.ts": "//",
        "*.tsx": "//",
        "*.yaml": "#",
        "*.yml": "#",
        "Dockerfile*": "#",
        "Makefile": "#",
    }
    if os.path.islink(filepath):
        return None
    fname = os.path.basename(filepath)
    match = next(
        (
            (pat, p)
            for pat, p in comment_prefixes.items()
            if fnmatch.fnmatch(fname, pat)
        ),
        None,
    )
    _, prefix = match if match else (None, None)
    if not prefix:
        return None  # unrecognised extension or explicitly excluded pattern
    with open(filepath, encoding="utf-8") as f:
        lines = [f.readline() for _ in range(20)]
    in_copyright = False
    for i, line in enumerate(lines):
        if not line:
            break
        sline = line.strip()
        if not sline:
            in_copyright = False
            continue
        if fname.endswith(".py") and sline.startswith(('"""', "'''")):
            return _py_docstring(lines, i)
        if prefix == "/*" and sline.startswith(prefix):
            return _c_style_block_comment(lines, i)
        # Skip common directives/metadata that aren't descriptions.
        if sline.startswith(f"{prefix}go:"):
            continue
        if sline.startswith(f"{prefix} +build"):
            continue
        if sline.startswith(f"{prefix} nolint"):
            continue
        if sline.startswith(f"{prefix} swift-tools-version:"):
            continue
        if sline.startswith(f"{prefix} ///"):
            continue
        # Skip YAML front-matter delimiters and shebangs.
        if sline == "---" or sline.startswith("#!"):
            continue
        # Skip copyright headers and their continuation lines (until blank).
        if in_copyright:
            continue
        if " copyright " in sline.lower():
            in_copyright = True
            continue
        # Skip PEP 723 inline script metadata fields (requires-python, dependencies, etc.)
        # that appear between # /// script and # /// markers.
        if fname.endswith(".py") and sline.startswith(
            (f"{prefix} requires-", f"{prefix} dependencies")
        ):
            continue
        if sline.startswith(prefix):
            comment = sline[len(prefix) :].strip()
            if not comment:
                continue
            return comment
        # Hit code before a comment.
        return ""
    return ""


def discover_configs(all_files: list[str]) -> dict[str, set[str]]:
    """Auto-discover workspace roots from AGENTS.md files that contain a file index marker.

    Returns a dict mapping target AGENTS.md path to its set of excluded child directories.
    """
    candidates = sorted(f for f in all_files if os.path.basename(f) == "AGENTS.md")
    configs: dict[str, set[str]] = {"AGENTS.md": set()}
    for f in candidates:
        with open(f, "r", encoding="utf-8") as fh:
            if "<!-- BEGIN FILE INDEX -->" in fh.read():
                configs[f] = set()
    # For each config, find child workspaces and add them to exclude_dirs.
    for target, exclude in configs.items():
        root = os.path.dirname(target)
        prefix = root + "/" if root else ""
        for other_target in configs:
            oroot = os.path.dirname(other_target)
            if oroot == root:
                continue
            if prefix:
                if not oroot.startswith(prefix):
                    continue
                child_rel = oroot[len(prefix) :]
            else:
                child_rel = oroot
            exclude.add(child_rel)
    return configs


def generate_index(
    target: str,
    exclude: set[str],
    all_files: list[str],
    all_configs: dict[str, set[str]],
    script_path: str,
) -> tuple[str, list[str]]:
    """Generate the file index for target, returning (content, missing) where
    missing is a list of files that support comments but have no description."""
    root_dir = os.path.dirname(target)
    files_found: list[tuple[str, str]] = []
    missing: list[str] = []
    for filepath in all_files:
        # Skip own AGENTS.md.
        if filepath == target:
            continue
        # Scope to root_dir.
        if root_dir:
            if not filepath.startswith(root_dir + "/"):
                continue
            relpath = filepath[len(root_dir) + 1 :]
        else:
            relpath = filepath
        # Check excluded subdirectories, but let sub-workspace AGENTS.md through.
        rel_parts = relpath.replace("\\", "/").split("/")
        if "testdata" in rel_parts:
            continue
        # A file is excluded if its path starts with any excluded prefix.
        if (
            any(relpath.startswith(ex + "/") or relpath == ex for ex in exclude)
            and filepath not in all_configs
        ):
            continue
        desc = get_file_description(filepath)
        if desc is None:
            continue  # file type has no comment convention
        if desc == "":
            missing.append(relpath)
        else:
            files_found.append((relpath, desc))
    desc = f"Autogenerated from first-line comments. Run `python3 {script_path}` to refresh."
    lines: list[str] = ["## File Index", "", desc, ""]
    for path, comment in sorted(files_found):
        lines.append(f"- `{path}`: {comment}")
    return "\n".join(lines), missing


def update_markdown(
    target_file: str, content: str, check: bool, script_path: str
) -> bool:
    """Update or check the file index in target_file. Returns True if a change was made (or needed)."""
    if not os.path.exists(target_file):
        print(f"Warning: {target_file} not found, skipping.")
        return False
    start = "<!-- BEGIN FILE INDEX -->"
    end = "<!-- END FILE INDEX -->"
    with open(target_file, "r", encoding="utf-8") as f:
        original = f.read()
    new_section = f"{start}\n{content}\n{end}"
    if start in original and end in original:
        pattern = re.compile(f"{re.escape(start)}.*?{re.escape(end)}", re.DOTALL)
        updated = pattern.sub(new_section, original)
    else:
        updated = (
            (original.rstrip() + "\n\n" + new_section + "\n")
            if original.strip()
            else (new_section + "\n")
        )
    if updated == original:
        return False
    if check:
        print(
            f"Error: {target_file} file index is out of date. Run {script_path} to fix.",
            file=sys.stderr,
        )
        return True
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"Updated: {target_file}")
    return True


def ensure_claude_symlinks(all_files: list[str], check: bool, script_path: str) -> int:
    """Ensure every AGENTS.md has a sibling CLAUDE.md symlink pointing to it."""
    ret = 0
    for f in all_files:
        if os.path.basename(f) != "AGENTS.md":
            continue
        d = os.path.dirname(f) or "."
        link = os.path.join(d, "CLAUDE.md")
        if os.path.islink(link) and os.readlink(link) == "AGENTS.md":
            continue
        if os.path.exists(link):
            print(
                f"Error: {link} exists but is not a symlink to AGENTS.md.",
                file=sys.stderr,
            )
            return 1
        if check:
            print(
                f"Error: {link} -> AGENTS.md symlink is missing. Run {script_path} to fix.",
                file=sys.stderr,
            )
            ret = 1
            continue
        os.symlink("AGENTS.md", link)
        print(f"Created: {link} -> AGENTS.md")
    return ret


def main() -> int:
    """Parse arguments and update (or check) the file indexes."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check that indexes are up to date without modifying files (exit 1 if not)",
    )
    args = parser.parse_args()

    git_root = get_git_root()
    if git_root is None:
        return 1
    script_path = get_script_path(git_root)
    os.chdir(git_root)
    all_files = get_git_files(git_root)
    if not all_files:
        print("No files found in git repository.")
        return 1
    ret = ensure_claude_symlinks(all_files, check=args.check, script_path=script_path)
    if ret and not args.check:
        return ret
    configs = discover_configs(all_files)
    all_missing: list[str] = []
    for target, exclude in configs.items():
        content, missing = generate_index(
            target, exclude, all_files, configs, script_path
        )
        if update_markdown(target, content, check=args.check, script_path=script_path):
            ret = 1
        all_missing.extend(missing)
    if all_missing:
        print(
            "Error: the following files have no description comment:", file=sys.stderr
        )
        for f in sorted(all_missing):
            print(f"  {f}", file=sys.stderr)
        ret = 1
    return ret


if __name__ == "__main__":
    sys.exit(main())
