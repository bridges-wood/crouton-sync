"""Convert between Recipe models and Obsidian-compatible Markdown."""

from __future__ import annotations

import base64
import re
from pathlib import Path

import yaml

from crouton_sync.models import Ingredient, Recipe, Step
from crouton_sync.quantity import format_amount, parse_amount, to_crouton_type, to_display


def recipe_to_markdown(
    recipe: Recipe,
    images_dir: Path | None = None,
    embed_images: bool = True,
) -> str:
    """Convert a Recipe to Obsidian-compatible Markdown with YAML frontmatter."""
    lines: list[str] = []

    # YAML frontmatter
    meta: dict = {}
    meta["crouton_uuid"] = recipe.uuid
    if recipe.source_name:
        meta["source_name"] = recipe.source_name
    if recipe.source_url:
        meta["source_url"] = recipe.source_url
    if recipe.prep_time is not None:
        meta["prep_time"] = _format_time(recipe.prep_time)
    if recipe.cook_time is not None:
        meta["cook_time"] = _format_time(recipe.cook_time)
    if recipe.servings is not None:
        meta["servings"] = recipe.servings
    if recipe.default_scale != 1.0:
        meta["default_scale"] = recipe.default_scale
    if recipe.rating:
        meta["rating"] = recipe.rating
    if recipe.difficulty:
        meta["difficulty"] = recipe.difficulty
    if recipe.tags:
        meta["tags"] = recipe.tags
    if recipe.folders:
        meta["folders"] = recipe.folders
    if recipe.nutritional_info:
        meta["nutritional_info"] = recipe.nutritional_info.strip() + "\n"

    frontmatter_str = yaml.dump(
        meta, default_flow_style=False, allow_unicode=True, sort_keys=False, width=200
    ).rstrip("\n")
    lines.append("---")
    lines.append(frontmatter_str)
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# {recipe.name}")
    lines.append("")

    # Image
    if embed_images and images_dir:
        for img_name in recipe.image_filenames:
            img_path = images_dir / img_name
            if img_path.exists():
                img_data = img_path.read_bytes()
                b64 = base64.b64encode(img_data).decode("ascii")
                lines.append(f"![recipe-image](data:image/jpeg;base64,{b64})")
                lines.append("")
                break  # Only embed the first image

    # Ingredients
    if recipe.ingredients:
        lines.append("## Ingredients")
        lines.append("")
        for ing in sorted(recipe.ingredients, key=lambda i: i.order):
            lines.append(f"- {_format_ingredient(ing)}")
        lines.append("")

    # Instructions
    if recipe.steps:
        lines.append("## Instructions")
        lines.append("")
        step_num = 1
        for step in sorted(recipe.steps, key=lambda s: s.order):
            if step.is_section:
                lines.append(f"### {step.text}")
                lines.append("")
            else:
                lines.append(f"{step_num}. {step.text}")
                step_num += 1
        lines.append("")

    # Notes
    if recipe.notes:
        lines.append("## Notes")
        lines.append("")
        lines.append(recipe.notes.strip())
        lines.append("")

    return "\n".join(lines)


def markdown_to_recipe(text: str) -> Recipe:
    """Parse Obsidian Markdown into a Recipe model."""
    # Split frontmatter and body
    frontmatter, body = _split_frontmatter(text)
    meta = _parse_yaml_frontmatter(frontmatter)

    # Parse body sections
    title = ""
    ingredients: list[Ingredient] = []
    steps: list[Step] = []
    notes = ""
    image_data: list[str] = []
    current_section = ""

    for line in body.split("\n"):
        stripped = line.strip()

        # Title
        if stripped.startswith("# ") and not title:
            title = stripped[2:].strip()
            continue

        # Section headers
        if stripped.startswith("## "):
            current_section = stripped[3:].strip().lower()
            continue

        # Subsection headers (step sections)
        if stripped.startswith("### ") and current_section == "instructions":
            section_text = stripped[4:].strip().rstrip(":")
            steps.append(Step(text=section_text, order=len(steps), is_section=True))
            continue

        # Image
        if stripped.startswith("![") and "data:image" in stripped:
            match = re.search(r"data:image/\w+;base64,([A-Za-z0-9+/=]+)", stripped)
            if match:
                image_data.append(match.group(1))
            continue

        # Ingredients
        if current_section == "ingredients" and stripped.startswith("- "):
            ing = _parse_ingredient_line(stripped[2:].strip())
            ing.order = len(ingredients)
            ingredients.append(ing)
            continue

        # Steps
        if current_section == "instructions" and re.match(r"\d+\.\s", stripped):
            step_text = re.sub(r"^\d+\.\s*", "", stripped)
            steps.append(Step(text=step_text, order=len(steps), is_section=False))
            continue

        # Notes
        if current_section == "notes" and stripped:
            notes = notes + stripped + "\n" if notes else stripped + "\n"

    # Build recipe from frontmatter + parsed body
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    folders = meta.get("folders", [])
    if isinstance(folders, str):
        folders = [f.strip() for f in folders.split(",") if f.strip()]

    return Recipe(
        name=title or meta.get("name", ""),
        uuid=meta.get("crouton_uuid", ""),
        ingredients=ingredients,
        steps=steps,
        tags=tags,
        folders=folders,
        prep_time=_parse_float(meta.get("prep_time")),
        cook_time=_parse_float(meta.get("cook_time")),
        servings=_parse_int(meta.get("servings")),
        default_scale=_parse_float(meta.get("default_scale")) or 1.0,
        source_name=meta.get("source_name", ""),
        source_url=meta.get("source_url", ""),
        nutritional_info=meta.get("nutritional_info", "").strip(),
        notes=notes.strip(),
        rating=_parse_int(meta.get("rating")) or 0,
        difficulty=meta.get("difficulty", ""),
        is_public=meta.get("is_public", False),
    )


def _format_ingredient(ing: Ingredient) -> str:
    """Format an ingredient for display in Markdown."""
    parts = []

    amount_str = format_amount(ing.amount)
    if amount_str:
        parts.append(amount_str)

    if ing.quantity_type and ing.quantity_type != "ITEM":
        unit = to_display(ing.quantity_type)
        if unit:
            parts.append(unit)

    parts.append(ing.name)
    return " ".join(parts)


def _parse_ingredient_line(text: str) -> Ingredient:
    """Parse a Markdown ingredient line like '2 lb chicken cutlets'."""
    text = text.strip()
    if not text:
        return Ingredient(name=text)

    # Try to extract amount and unit from the beginning
    amount = None
    quantity_type = None
    remaining = text

    # Match amount pattern: "2", "½", "1 ½", "1/3", "2.5"
    amount_pattern = r"^(\d+\s+[½¼¾⅓⅔⅛⅜⅝⅞]|\d+[½¼¾⅓⅔⅛⅜⅝⅞]|\d+/\d+|\d+\.?\d*|[½¼¾⅓⅔⅛⅜⅝⅞])\s+"
    match = re.match(amount_pattern, remaining)
    if match:
        amount_str = match.group(1)
        amount = parse_amount(amount_str)
        remaining = remaining[match.end() :]

        # Try to match a unit
        unit_pattern = r"^(\w+)\s+"
        unit_match = re.match(unit_pattern, remaining)
        if unit_match:
            potential_unit = unit_match.group(1)
            crouton_type = to_crouton_type(potential_unit)
            if crouton_type:
                quantity_type = crouton_type
                remaining = remaining[unit_match.end() :]

    # If we got an amount but no unit, it's probably an ITEM
    if amount is not None and quantity_type is None:
        quantity_type = "ITEM"

    return Ingredient(
        name=remaining.strip(),
        amount=amount,
        quantity_type=quantity_type,
    )


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split YAML frontmatter from body."""
    if not text.startswith("---"):
        return "", text

    end = text.find("---", 3)
    if end == -1:
        return "", text

    frontmatter = text[3:end].strip()
    body = text[end + 3 :].strip()
    return frontmatter, body


def _parse_yaml_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter using PyYAML."""
    if not text:
        return {}
    try:
        result = yaml.safe_load(text)
        return result if isinstance(result, dict) else {}
    except yaml.YAMLError:
        return {}


def _format_time(minutes: float) -> int | float:
    """Format time value, preferring int when possible."""
    return int(minutes) if minutes == int(minutes) else minutes


def _parse_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None
