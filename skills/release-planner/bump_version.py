#!/usr/bin/env python3
"""
Release version bumping utility — CHANGELOG + plugin.json lockstep sync.
Adapted from agent-tdd/scripts/bump_version.py pattern for plugin-agnostic use.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional


def validate_semver(version: str) -> bool:
    """Validate semver X.Y.Z format."""
    return bool(re.match(r'^\d+\.\d+\.\d+$', version))


def read_file(path: Path) -> Optional[str]:
    """Read file; return None if not found."""
    try:
        return path.read_text()
    except FileNotFoundError:
        return None


def bump_changelog(changelog_path: Path, version: str) -> Tuple[bool, str]:
    """
    Move CHANGELOG.md [Unreleased] section under [version] heading.

    Returns:
        (success, message)
    """
    content = read_file(changelog_path)
    if not content:
        return False, f"CHANGELOG not found: {changelog_path}"

    # Check for Unreleased section
    if "## [Unreleased]" not in content:
        return False, "CHANGELOG.md: missing ## [Unreleased] section"

    # Split on Unreleased
    parts = content.split("## [Unreleased]\n", 1)
    if len(parts) != 2:
        return False, "CHANGELOG.md: could not parse [Unreleased] section"

    preamble, rest = parts

    # Extract entries until next version heading or end
    lines = rest.split('\n')
    unreleased_entries = []
    remaining = []
    in_unreleased = True

    for line in lines:
        if in_unreleased and line.startswith("## ["):
            in_unreleased = False

        if in_unreleased:
            unreleased_entries.append(line)
        else:
            remaining.append(line)

    # Build new content
    date = datetime.now().strftime("%Y-%m-%d")
    new_version_heading = f"## [{version}] - {date}\n"
    new_unreleased = "## [Unreleased]\n\n"

    new_content = preamble + new_unreleased + new_version_heading + "\n".join(unreleased_entries) + "\n" + "\n".join(remaining)

    try:
        changelog_path.write_text(new_content)
        return True, f"CHANGELOG.md: moved [Unreleased] → [{version}]"
    except Exception as e:
        return False, f"CHANGELOG.md: write failed: {e}"


def bump_plugin_json(plugin_json_path: Path, version: str) -> Tuple[bool, str]:
    """
    Update .claude-plugin/plugin.json version field.

    Returns:
        (success, message)
    """
    content = read_file(plugin_json_path)
    if not content:
        return False, f"plugin.json not found: {plugin_json_path}"

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return False, f"plugin.json: invalid JSON: {e}"

    data["version"] = version

    try:
        plugin_json_path.write_text(json.dumps(data, indent=2) + "\n")
        return True, f"plugin.json: version bumped to {version}"
    except Exception as e:
        return False, f"plugin.json: write failed: {e}"


def validate_lockstep(changelog_path: Path, plugin_json_path: Path, version: str) -> Tuple[bool, str]:
    """
    Verify CHANGELOG and plugin.json versions match.

    Returns:
        (success, message)
    """
    changelog_content = read_file(changelog_path)
    plugin_json_content = read_file(plugin_json_path)

    if not changelog_content or not plugin_json_content:
        return False, "Could not read files for lockstep validation"

    try:
        plugin_data = json.loads(plugin_json_content)
    except json.JSONDecodeError:
        return False, "plugin.json: invalid JSON for lockstep check"

    plugin_version = plugin_data.get("version")

    # Check CHANGELOG has the version
    if f"## [{version}]" not in changelog_content:
        return False, f"Lockstep validation failed: CHANGELOG missing [{version}]"

    # Check plugin.json has the version
    if plugin_version != version:
        return False, f"Lockstep validation failed: plugin.json has {plugin_version}, expected {version}"

    return True, f"Files in sync: CHANGELOG [{version}], plugin.json version {version}"


def bump(version: str, repo_root: Path = None) -> Tuple[bool, list]:
    """
    Bump release version — CHANGELOG + plugin.json lockstep.

    Args:
        version: Semantic version (X.Y.Z)
        repo_root: Path to plugin root; auto-detect if None

    Returns:
        (success, messages)
    """
    if not validate_semver(version):
        return False, [f"Invalid version format: {version}", "→ Use semver X.Y.Z format (e.g., 0.1.0)"]

    if repo_root is None:
        repo_root = Path(__file__).parent.parent.parent

    changelog_path = repo_root / "CHANGELOG.md"
    plugin_json_path = repo_root / ".claude-plugin" / "plugin.json"

    messages = []

    # Bump CHANGELOG
    success, msg = bump_changelog(changelog_path, version)
    messages.append(("✓" if success else "✗") + " " + msg)
    if not success:
        return False, messages

    # Bump plugin.json
    success, msg = bump_plugin_json(plugin_json_path, version)
    messages.append(("✓" if success else "✗") + " " + msg)
    if not success:
        return False, messages

    # Validate lockstep
    success, msg = validate_lockstep(changelog_path, plugin_json_path, version)
    messages.append(("✓" if success else "✗") + " " + msg)
    if not success:
        return False, messages

    messages.append(f"✓ Release version {version} prepared")
    return True, messages


def main():
    """CLI entry point."""
    if len(sys.argv) != 2:
        print("Usage: bump_version.py <version>")
        print("Example: bump_version.py 0.1.0")
        sys.exit(1)

    version = sys.argv[1]
    success, messages = bump(version)

    for msg in messages:
        print(msg)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
