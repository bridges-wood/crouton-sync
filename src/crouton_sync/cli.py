"""CLI entry point for crouton-sync."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from crouton_sync.crouton_db import (
    DEFAULT_DB_PATH,
    DEFAULT_IMAGES_DIR,
    _backup_database,
    _validate_image_path,
    read_all_recipes,
    write_recipe,
)
from crouton_sync.crumb import write_crumb
from crouton_sync.markdown import IMAGES_SUBDIR, markdown_to_recipe, recipe_to_markdown
from crouton_sync.sync import compare, print_sync_status
from crouton_sync.verify import format_result, validate_markdown

# Delay between opening .crumb files to avoid overwhelming the app
_CRUMB_OPEN_DELAY = 0.5

console = Console()


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
            console.print(f"[red]✗[/red]  No recipes matching '{args.recipe}'")
            return 1

    include_images = not args.no_images
    count = 0
    img_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Exporting recipes...", total=len(recipes))

        for recipe in recipes:
            md = recipe_to_markdown(recipe, include_images=include_images)
            filename = _safe_filename(recipe.name) + ".md"
            (output_dir / filename).write_text(md, encoding="utf-8")
            count += 1

            if include_images:
                img_count += _copy_recipe_images(
                    recipe.image_filenames, args.images_dir, output_dir
                )

            progress.update(task, advance=1)

    console.print(
        f"[green]✓[/green]  Exported [cyan]{count}[/cyan] recipes to [blue]{output_dir}[/blue]"
    )
    if img_count:
        console.print(
            f"    Copied [cyan]{img_count}[/cyan] images to "
            f"[blue]{output_dir / IMAGES_SUBDIR}[/blue]"
        )
    return 0


def _copy_recipe_images(
    image_filenames: list[str],
    src_images_dir: Path,
    output_dir: Path,
) -> int:
    """Copy recipe image files to the output images subdirectory. Returns count copied."""
    if not image_filenames:
        return 0

    dest_dir = output_dir / IMAGES_SUBDIR
    dest_dir.mkdir(exist_ok=True)
    copied = 0

    for img_name in image_filenames:
        try:
            src_path = _validate_image_path(img_name, src_images_dir)
        except ValueError:
            console.print(
                f"[yellow]⚠[/yellow]  Warning: skipping invalid image path: {img_name}",
                file=sys.stderr,
            )
            continue
        if not src_path.exists():
            console.print(
                f"[yellow]⚠[/yellow]  Warning: image not found: {img_name}",
                file=sys.stderr,
            )
            continue

        dest_path = dest_dir / img_name
        if not dest_path.exists() or dest_path.stat().st_mtime < src_path.stat().st_mtime:
            shutil.copy2(src_path, dest_path)
            copied += 1

    return copied


def cmd_import(args: argparse.Namespace) -> int:
    input_dir: Path = args.input_dir
    if not input_dir.is_dir():
        console.print(f"[red]✗[/red]  Input directory not found: {input_dir}")
        return 1

    md_files = list(input_dir.glob("*.md"))
    if not md_files:
        console.print(f"[red]✗[/red]  No .md files found in {input_dir}")
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

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating .crumb files...", total=len(md_files))

        for md_file in md_files:
            text = md_file.read_text(encoding="utf-8")
            recipe = markdown_to_recipe(text)
            if not recipe.name:
                console.print(f"    Skipping {md_file.name}: no recipe name found")
                progress.update(task, advance=1)
                continue

            if dry_run:
                console.print(f"    Would generate: {_safe_filename(recipe.name)}.crumb")
                count += 1
                progress.update(task, advance=1)
                continue

            # Collect image data from the images/ subdirectory next to the Markdown file
            image_bytes: list[bytes] | None = None
            if recipe.image_filenames:
                images_src = md_file.parent / IMAGES_SUBDIR
                image_bytes = []
                for img_name in recipe.image_filenames:
                    img_path = images_src / img_name
                    if img_path.exists():
                        image_bytes.append(img_path.read_bytes())

            crumb_path = crumb_dir / (_safe_filename(recipe.name) + ".crumb")
            write_crumb(recipe, crumb_path, image_data=image_bytes or None)
            count += 1

            if args.open_in_app:
                if sys.platform == "darwin":
                    subprocess.run(["open", "-a", "Crouton", str(crumb_path)], check=False)
                    time.sleep(_CRUMB_OPEN_DELAY)
                else:
                    console.print(
                        f"    Auto-open not supported on {sys.platform}; open manually: "
                        f"{crumb_path}"
                    )

            progress.update(task, advance=1)

    prefix = "[dim]DRY RUN[/dim] " if dry_run else ""
    console.print(
        f"[green]✓[/green]  {prefix}Generated [cyan]{count}[/cyan] .crumb files in "
        f"[blue]{crumb_dir}[/blue]"
    )
    if args.open_in_app and not dry_run:
        console.print("[cyan]→[/cyan]  Opening in Crouton...")
    return 0


def _import_direct(args: argparse.Namespace, md_files: list[Path]) -> int:
    dry_run = args.dry_run

    if not dry_run:
        backup_path = _backup_database(args.db_path)
        console.print(f"[dim]Database backed up to {backup_path}[/dim]")

    count = 0
    errors = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Importing recipes...", total=len(md_files))

        for md_file in md_files:
            text = md_file.read_text(encoding="utf-8")
            recipe = markdown_to_recipe(text)
            if not recipe.name:
                console.print(f"    Skipping {md_file.name}: no recipe name found")
                progress.update(task, advance=1)
                continue

            if dry_run:
                console.print(f"    Would write: {recipe.name}")
                count += 1
                progress.update(task, advance=1)
                continue

            # Collect image data from the images/ subdirectory next to the Markdown file
            image_data: dict[str, bytes] | None = None
            if recipe.image_filenames:
                images_src = md_file.parent / IMAGES_SUBDIR
                image_data = {}
                for img_name in recipe.image_filenames:
                    img_path = images_src / img_name
                    if img_path.exists():
                        image_data[img_name] = img_path.read_bytes()

            try:
                uuid = write_recipe(
                    recipe,
                    db_path=args.db_path,
                    images_dir=args.images_dir,
                    image_data=image_data or None,
                    skip_backup=True,
                )
                console.print(f"    [green]✓[/green] {recipe.name} ({uuid})")
                count += 1
            except RuntimeError as e:
                console.print(f"    [red]✗[/red] {recipe.name}: {e}")
                errors += 1

            progress.update(task, advance=1)

    prefix = "[dim]DRY RUN[/dim] " if dry_run else ""
    console.print(
        f"[green]✓[/green]  {prefix}Imported [cyan]{count}[/cyan] recipes directly to database"
    )
    if errors:
        console.print(f"    [yellow]⚠[/yellow] {errors} recipes failed")
    if not dry_run and count > 0:
        console.print("[cyan]→[/cyan]  Restart Crouton to trigger CloudKit sync.")
    return 1 if errors and count == 0 else 0


def cmd_verify(args: argparse.Namespace) -> int:
    md_files: list[Path] = []
    for target in args.files:
        if target.is_dir():
            md_files.extend(sorted(target.glob("*.md")))
        elif target.is_file():
            md_files.append(target)
        else:
            console.print(f"[yellow]⚠[/yellow]  Not found: {target}")

    if not md_files:
        console.print("[red]✗[/red]  No .md files found to verify")
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
        console.print(f"\n[cyan]{valid_count}[/cyan]/[cyan]{len(md_files)}[/cyan] recipes valid")

    if not all_ok:
        return 1
    if args.strict and total_warnings > 0:
        return 1
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    md_dir: Path = args.markdown_dir
    if not md_dir.is_dir():
        console.print(f"[red]✗[/red]  Markdown directory not found: {md_dir}")
        return 1

    status = compare(md_dir, db_path=args.db_path)
    print_sync_status(status)

    if args.export_new and status.crouton_only:
        dry_run = args.dry_run
        prefix = "[dim]DRY RUN[/dim] " if dry_run else ""
        console.print(
            f"\n[cyan]→[/cyan]  {prefix}Exporting {len(status.crouton_only)} new recipes..."
        )

        recipes = read_all_recipes(args.db_path)
        include_images = not args.no_images
        crouton_only_set = set(status.crouton_only)
        count = 0
        img_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Exporting new recipes...", total=len(recipes))

            for recipe in recipes:
                if recipe.uuid in crouton_only_set:
                    if dry_run:
                        console.print(f"    Would export: {recipe.name}")
                        count += 1
                    else:
                        md = recipe_to_markdown(recipe, include_images=include_images)
                        filename = _safe_filename(recipe.name) + ".md"
                        (md_dir / filename).write_text(md, encoding="utf-8")
                        count += 1

                        if include_images:
                            img_count += _copy_recipe_images(
                                recipe.image_filenames, args.images_dir, md_dir
                            )

                progress.update(task, advance=1)

        console.print(f"[green]✓[/green]  {prefix}Exported [cyan]{count}[/cyan] recipes")
        if img_count:
            console.print(
                f"    Copied [cyan]{img_count}[/cyan] images to "
                f"[blue]{md_dir / IMAGES_SUBDIR}[/blue]"
            )

    return 0


def _safe_filename(name: str) -> str:
    """Convert a recipe name to a safe filename.

    Raises ValueError if name is empty or produces an empty filename.
    """
    safe = name.replace("/", "-").replace("\\", "-").replace(":", " -")
    safe = safe.replace('"', "'").replace("?", "").replace("*", "")
    safe = safe.replace("<", "").replace(">", "").replace("|", "-")
    safe = safe.strip()
    if not safe:
        raise ValueError(f"Recipe name is empty or contains only special characters: {name!r}")
    return safe


if __name__ == "__main__":
    sys.exit(main())
