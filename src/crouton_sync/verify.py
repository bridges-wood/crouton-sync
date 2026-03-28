"""Validate a Markdown recipe and report issues."""

from __future__ import annotations

from dataclasses import dataclass, field

from crouton_sync.markdown import markdown_to_recipe


@dataclass
class ValidationResult:
    """Result of validating a Markdown recipe."""

    file_path: str = ""
    recipe_name: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def validate_markdown(text: str, file_path: str = "") -> ValidationResult:
    """Validate a Markdown recipe file and report issues.

    Checks for:
    - Parseable YAML frontmatter
    - Recipe title (# heading)
    - ## Ingredients section with parseable ingredient lines
    - ## Instructions section with numbered steps
    - Ingredient quantity types that map to Crouton types
    - Missing optional but recommended fields
    """
    result = ValidationResult(file_path=file_path)

    # Try parsing
    try:
        recipe = markdown_to_recipe(text)
    except Exception as e:
        result.errors.append(f"Failed to parse: {e}")
        return result

    result.recipe_name = recipe.name

    # ── Errors (will prevent usable import) ──

    if not recipe.name:
        result.errors.append("No recipe title found (expected `# Recipe Name`)")

    if not recipe.ingredients:
        result.errors.append(
            "No ingredients found (expected `## Ingredients` with `- ` list items)"
        )

    if not recipe.steps:
        result.errors.append(
            "No instructions found (expected `## Instructions` with numbered steps)"
        )

    # Check ingredient parsing quality
    for i, ing in enumerate(recipe.ingredients):
        if not ing.name:
            result.errors.append(f"Ingredient {i + 1}: empty name")
        if ing.amount is not None and ing.quantity_type is None:
            result.warnings.append(
                f"Ingredient {i + 1} ({ing.name}): has amount but no recognized unit"
            )

    # ── Warnings (recipe will import but data may be incomplete) ──

    if not recipe.uuid:
        result.warnings.append(
            "No `crouton_uuid` in frontmatter — a new UUID will be generated on import"
        )

    if recipe.servings is None:
        result.warnings.append("No `servings` specified in frontmatter")

    if recipe.prep_time is None and recipe.cook_time is None:
        result.warnings.append("No `prep_time` or `cook_time` specified in frontmatter")

    if not recipe.source_name and not recipe.source_url:
        result.warnings.append("No source attribution (`source_name` / `source_url`)")

    # Check for sections without steps after them
    for i, step in enumerate(recipe.steps):
        if step.is_section:
            remaining = recipe.steps[i + 1 :]
            if not remaining or remaining[0].is_section:
                result.warnings.append(f"Section header '{step.text}' has no steps after it")

    # ── Info (summary) ──

    result.info.append(f"Title: {recipe.name}")
    result.info.append(f"Ingredients: {len(recipe.ingredients)}")
    result.info.append(f"Steps: {sum(1 for s in recipe.steps if not s.is_section)}")
    sections = sum(1 for s in recipe.steps if s.is_section)
    if sections:
        result.info.append(f"Sections: {sections}")
    if recipe.tags:
        result.info.append(f"Tags: {', '.join(recipe.tags)}")
    if recipe.folders:
        result.info.append(f"Folders: {', '.join(recipe.folders)}")

    return result


def format_result(result: ValidationResult) -> str:
    """Format a ValidationResult as a human-readable string."""
    lines: list[str] = []

    header = result.file_path or result.recipe_name or "Recipe"
    if result.ok:
        lines.append(f"✓ {header}")
    else:
        lines.append(f"✗ {header}")

    for msg in result.info:
        lines.append(f"  {msg}")

    if result.errors:
        lines.append("")
        for msg in result.errors:
            lines.append(f"  ✗ {msg}")

    if result.warnings:
        lines.append("")
        for msg in result.warnings:
            lines.append(f"  ⚠ {msg}")

    if result.ok and not result.warnings:
        lines.append("  Ready for import.")

    return "\n".join(lines)
