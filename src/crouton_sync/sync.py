"""Sync logic: compare recipes in Crouton DB vs Markdown directory."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from crouton_sync.crouton_db import read_all_recipes
from crouton_sync.markdown import markdown_to_recipe


@dataclass
class SyncStatus:
    """Result of comparing Crouton and Markdown recipe sets."""

    crouton_only: list[str] = field(default_factory=list)
    markdown_only: list[str] = field(default_factory=list)
    both: list[str] = field(default_factory=list)

    # Maps UUID → recipe name for display
    crouton_names: dict[str, str] = field(default_factory=dict)
    markdown_names: dict[str, str] = field(default_factory=dict)


def compare(
    markdown_dir: Path,
    db_path: Path | None = None,
) -> SyncStatus:
    """Compare recipes in Crouton DB vs a directory of Markdown files."""
    # Load Crouton recipes
    crouton_recipes = read_all_recipes(db_path)
    crouton_uuids = {}
    for r in crouton_recipes:
        crouton_uuids[r.uuid] = r.name

    # Load Markdown recipes
    md_uuids = {}
    for md_file in markdown_dir.glob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
            recipe = markdown_to_recipe(text)
            if recipe.uuid:
                md_uuids[recipe.uuid] = recipe.name
        except Exception as e:
            print(f"  Warning: skipping {md_file.name}: {e}", file=sys.stderr)
            continue

    # Compare
    crouton_set = set(crouton_uuids.keys())
    md_set = set(md_uuids.keys())

    return SyncStatus(
        crouton_only=sorted(crouton_set - md_set),
        markdown_only=sorted(md_set - crouton_set),
        both=sorted(crouton_set & md_set),
        crouton_names=crouton_uuids,
        markdown_names=md_uuids,
    )


def print_sync_status(status: SyncStatus) -> None:
    """Print a human-readable sync status report."""
    print(f"In both:         {len(status.both)} recipes")
    print(f"Crouton only:    {len(status.crouton_only)} recipes")
    print(f"Markdown only:   {len(status.markdown_only)} recipes")

    if status.crouton_only:
        print("\n── New in Crouton (not yet exported) ──")
        for uuid in status.crouton_only:
            print(f"  • {status.crouton_names.get(uuid, uuid)}")

    if status.markdown_only:
        print("\n── New in Markdown (not yet imported) ──")
        for uuid in status.markdown_only:
            print(f"  • {status.markdown_names.get(uuid, uuid)}")
