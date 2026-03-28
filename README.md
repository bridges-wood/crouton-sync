# crouton-sync

Bidirectional sync between the [Crouton](https://crouton.app) recipe app and Obsidian Markdown.

## Features

- **Export** all recipes from Crouton to Obsidian-compatible Markdown (reads directly from the local database — no manual export needed)
- **Import** Markdown recipes back into Crouton via `.crumb` files or direct database writes
- **Verify** Markdown recipe files before importing — check structure, ingredients, and metadata
- **Sync** — compare Crouton and Markdown recipe sets, detect new/modified recipes

## Installation

```bash
# Install as a global CLI tool (available from any directory)
uv tool install .

# Or for development (editable install in a local venv)
uv sync
```

## Usage

### Export recipes to Markdown

```bash
# Export all recipes
crouton-sync export ~/obsidian-vault/Recipes/

# Export without images (faster, smaller files)
crouton-sync export ~/obsidian-vault/Recipes/ --no-images

# Export a single recipe by name
crouton-sync export ~/obsidian-vault/Recipes/ --recipe "Oven-Roasted Asparagus"
```

### Import Markdown recipes into Crouton

```bash
# Generate .crumb files (safe — uses Crouton's native import)
crouton-sync import ~/obsidian-vault/Recipes/ --mode crumb

# Generate and auto-open in Crouton
crouton-sync import ~/obsidian-vault/Recipes/ --mode crumb --open

# Direct database write (faster, syncs via CloudKit on next app launch)
crouton-sync import ~/obsidian-vault/Recipes/ --mode direct
```

### Sync comparison

```bash
# See what's new/missing on each side
crouton-sync sync ~/obsidian-vault/Recipes/

# Auto-export new Crouton recipes to Markdown
crouton-sync sync ~/obsidian-vault/Recipes/ --export-new
```

### Verify Markdown recipes

```bash
# Validate a single recipe file
crouton-sync verify my-recipe.md

# Validate all recipes in a directory
crouton-sync verify ~/obsidian-vault/Recipes/

# Treat warnings as errors (useful in CI or for strict formatting)
crouton-sync verify --strict my-recipe.md
```

The verify command checks that recipes have a title, ingredients section, instructions section, and valid frontmatter. It reports warnings for missing optional fields like `crouton_uuid`, `servings`, and `source_name`. This is useful when having an AI agent format an unstructured recipe — run `verify` to confirm it parsed correctly before importing.

### Advanced options

```bash
# Use a custom database path
crouton-sync --db-path /path/to/Meals.sqlite export ./output/

# Use a custom images directory
crouton-sync --images-dir /path/to/MealImages/ export ./output/
```

## Markdown Format

Exported recipes use YAML frontmatter for metadata and standard Markdown for content:

```markdown
---
crouton_uuid: 2F96A839-4A89-4EAA-AEBA-AA9DE17C7C25
source_name: Delish
source_url: https://www.delish.com/cooking/...
prep_time: 5
servings: 4
folders:
  - Sides
tags:
  - Vegetarian
nutritional_info: |
  Calories: 137
  Protein: 5g
---

# Oven-Roasted Asparagus

## Ingredients

- 2 lb asparagus, stalks trimmed
- 3 tbsp extra-virgin olive oil
- Kosher salt
- Freshly ground black pepper

## Instructions

1. Preheat oven to 450ºF. Toss asparagus with olive oil...
2. Roast until tender and slightly charred, 12-15 minutes.

## Notes

Optional notes here.
```

## How It Works

Crouton stores recipes in a Core Data SQLite database at:
```
~/Library/Group Containers/group.com.meals.ios/Meals.sqlite
```

Recipe images are stored as JPEGs in:
```
~/Library/Group Containers/group.com.meals.ios/MealImages/
```

This tool reads directly from (and optionally writes to) these files. See [`docs/CROUTON_INTERNALS.md`](docs/CROUTON_INTERNALS.md) for full reverse engineering documentation.

## Development

```bash
uv sync                    # Install dependencies
uv run pytest -v           # Run tests
uv run ruff check src/     # Lint
uv run ruff format src/    # Format
```