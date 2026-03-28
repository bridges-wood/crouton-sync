"""CLI entry point for crouton-sync."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from crouton_sync.crouton_db import (
    DEFAULT_DB_PATH,
    DEFAULT_IMAGES_DIR,
    _backup_database,
    read_all_recipes,
    write_recipe,
)
from crouton_sync.crumb import write_crumb
from crouton_sync.markdown import markdown_to_recipe, recipe_to_markdown
from crouton_sync.sync import compare, print_sync_status
from crouton_sync.verify import format_result, validate_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crouton-sync",
        description="Bidirectional sync between Crouton recipe app and Obsidian Markdown",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to Crouton's Meals.sqlite",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=DEFAULT_IMAGES_DIR,
        help="Path to Crouton's MealImages directory",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── export ──
    export_parser = subparsers.add_parser("export", help="Export Crouton recipes to Markdown")
    export_parser.add_argument("output_dir", type=Path, help="Output directory for Markdown files")
    export_parser.add_argument("--no-images", action="store_true", help="Skip embedding images")
    export_parser.add_argument(
        "--recipe", type=str, help="Export a single recipe by name (substring match)"
    )

    # ── import ──
    import_parser = subparsers.add_parser("import", help="Import Markdown recipes into Crouton")
    import_parser.add_argument("input_dir", type=Path, help="Directory of Markdown files")
    import_parser.add_argument(
        "--mode",
        choices=["crumb", "direct"],
        default="crumb",
        help="Import mode: 'crumb' generates .crumb files (safe), 'direct' writes to DB",
    )
    import_parser.add_argument(
        "--crumb-dir",
        type=Path,
        help="Output directory for .crumb files (default: input_dir/.crumb)",
    )
    import_parser.add_argument(
        "--open",
        action="store_true",
        dest="open_in_app",
        help="Open generated .crumb files in Crouton",
    )
    import_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without making changes",
    )

    # ── verify ──
    verify_parser = subparsers.add_parser(
        "verify", help="Validate Markdown recipe files before importing"
    )
    verify_parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="Markdown files or directories to validate",
    )
    verify_parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit non-zero if any warnings)",
    )

    # ── sync ──
    sync_parser = subparsers.add_parser("sync", help="Compare Crouton and Markdown recipes")
    sync_parser.add_argument("markdown_dir", type=Path, help="Markdown recipes directory")
    sync_parser.add_argument(
        "--export-new",
        action="store_true",
        help="Export recipes that are only in Crouton",
    )
    sync_parser.add_argument(
        "--no-images", action="store_true", help="Skip embedding images when exporting"
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be exported without making changes",
    )

    args = parser.parse_args(argv)

    if args.command == "export":
        return cmd_export(args)
    elif args.command == "import":
        return cmd_import(args)
    elif args.command == "verify":
        return cmd_verify(args)
    elif args.command == "sync":
        return cmd_sync(args)

    return 1


def cmd_export(args: argparse.Namespace) -> int:
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    recipes = read_all_recipes(args.db_path)

    if args.recipe:
        query = args.recipe.lower()
        recipes = [r for r in recipes if query in r.name.lower()]
        if not recipes:
            print(f"No recipes matching '{args.recipe}'")
            return 1

    embed = not args.no_images
    count = 0
    for recipe in recipes:
        md = recipe_to_markdown(recipe, images_dir=args.images_dir, embed_images=embed)
        filename = _safe_filename(recipe.name) + ".md"
        (output_dir / filename).write_text(md, encoding="utf-8")
        count += 1

    print(f"Exported {count} recipes to {output_dir}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    input_dir: Path = args.input_dir
    if not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}")
        return 1

    md_files = list(input_dir.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {input_dir}")
        return 1

    if args.mode == "crumb":
        return _import_via_crumb(args, md_files)
    else:
        return _import_direct(args, md_files)


def _import_via_crumb(args: argparse.Namespace, md_files: list[Path]) -> int:
    crumb_dir = args.crumb_dir or (args.input_dir / ".crumb")
    dry_run = args.dry_run

    if not dry_run:
        crumb_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        recipe = markdown_to_recipe(text)
        if not recipe.name:
            print(f"  Skipping {md_file.name}: no recipe name found")
            continue

        if dry_run:
            print(f"  Would generate: {_safe_filename(recipe.name)}.crumb")
            count += 1
            continue

        crumb_path = crumb_dir / (_safe_filename(recipe.name) + ".crumb")
        write_crumb(recipe, crumb_path)
        count += 1

        if args.open_in_app:
            subprocess.run(["open", "-a", "Crouton", str(crumb_path)], check=False)
            time.sleep(0.5)  # Brief pause to avoid overwhelming the app

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}Generated {count} .crumb files in {crumb_dir}")
    if args.open_in_app and not dry_run:
        print("Opening in Crouton...")
    return 0


def _import_direct(args: argparse.Namespace, md_files: list[Path]) -> int:
    dry_run = args.dry_run

    if not dry_run:
        backup_path = _backup_database(args.db_path)
        print(f"  Database backed up to {backup_path}")

    count = 0
    errors = 0
    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        recipe = markdown_to_recipe(text)
        if not recipe.name:
            print(f"  Skipping {md_file.name}: no recipe name found")
            continue

        if dry_run:
            print(f"  Would write: {recipe.name}")
            count += 1
            continue

        try:
            uuid = write_recipe(
                recipe, db_path=args.db_path, images_dir=args.images_dir, skip_backup=True
            )
            print(f"  Wrote: {recipe.name} ({uuid})")
            count += 1
        except RuntimeError as e:
            print(f"  Error: {recipe.name}: {e}")
            errors += 1

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}Imported {count} recipes directly to database")
    if errors:
        print(f"  {errors} recipes failed")
    if not dry_run and count > 0:
        print("Restart Crouton to trigger CloudKit sync.")
    return 1 if errors and count == 0 else 0


def cmd_verify(args: argparse.Namespace) -> int:
    md_files: list[Path] = []
    for target in args.files:
        if target.is_dir():
            md_files.extend(sorted(target.glob("*.md")))
        elif target.is_file():
            md_files.append(target)
        else:
            print(f"Not found: {target}")

    if not md_files:
        print("No .md files found to verify")
        return 1

    all_ok = True
    total_warnings = 0
    valid_count = 0
    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        result = validate_markdown(text, file_path=str(md_file.name))
        print(format_result(result))
        print()
        if not result.ok:
            all_ok = False
        else:
            valid_count += 1
        total_warnings += len(result.warnings)

    # Summary
    if len(md_files) > 1:
        print(f"{valid_count}/{len(md_files)} recipes valid")

    if not all_ok:
        return 1
    if args.strict and total_warnings > 0:
        return 1
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    md_dir: Path = args.markdown_dir
    if not md_dir.is_dir():
        print(f"Markdown directory not found: {md_dir}")
        return 1

    status = compare(md_dir, db_path=args.db_path)
    print_sync_status(status)

    if args.export_new and status.crouton_only:
        dry_run = args.dry_run
        prefix = "[DRY RUN] " if dry_run else ""
        print(f"\n{prefix}Exporting {len(status.crouton_only)} new recipes...")
        recipes = read_all_recipes(args.db_path)
        embed = not args.no_images
        crouton_only_set = set(status.crouton_only)
        count = 0
        for recipe in recipes:
            if recipe.uuid in crouton_only_set:
                if dry_run:
                    print(f"  Would export: {recipe.name}")
                    count += 1
                    continue
                md = recipe_to_markdown(recipe, images_dir=args.images_dir, embed_images=embed)
                filename = _safe_filename(recipe.name) + ".md"
                (md_dir / filename).write_text(md, encoding="utf-8")
                count += 1
        print(f"{prefix}Exported {count} recipes")

    return 0


def _safe_filename(name: str) -> str:
    """Convert a recipe name to a safe filename."""
    # Replace problematic characters
    safe = name.replace("/", "-").replace("\\", "-").replace(":", " -")
    safe = safe.replace('"', "'").replace("?", "").replace("*", "")
    safe = safe.replace("<", "").replace(">", "").replace("|", "-")
    return safe.strip()


if __name__ == "__main__":
    sys.exit(main())
