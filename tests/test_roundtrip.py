"""End-to-end roundtrip tests: SQLite → Markdown → .crumb."""

import tempfile
from pathlib import Path

import pytest

from crouton_sync.crouton_db import DEFAULT_DB_PATH, read_all_recipes
from crouton_sync.crumb import read_crumb, recipe_to_crumb_dict, write_crumb
from crouton_sync.markdown import markdown_to_recipe, recipe_to_markdown

_skip_no_db = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(), reason="Crouton database not available"
)


@_skip_no_db
class TestSQLiteToMarkdownRoundtrip:
    """Test reading from SQLite, exporting to Markdown, and re-importing."""

    def test_roundtrip_preserves_fields(self):
        recipes = read_all_recipes()
        for recipe in recipes[:5]:
            md = recipe_to_markdown(recipe, include_images=False)
            parsed = markdown_to_recipe(md)

            assert parsed.name == recipe.name, f"Name mismatch for {recipe.name}"
            assert parsed.uuid == recipe.uuid
            assert parsed.servings == recipe.servings
            assert parsed.source_name == recipe.source_name
            assert parsed.source_url == recipe.source_url

            assert len(parsed.ingredients) == len(recipe.ingredients), (
                f"Ingredient count mismatch for {recipe.name}: "
                f"{len(parsed.ingredients)} vs {len(recipe.ingredients)}"
            )

            assert len(parsed.steps) == len(recipe.steps), (
                f"Step count mismatch for {recipe.name}: "
                f"{len(parsed.steps)} vs {len(recipe.steps)}"
            )


@_skip_no_db
class TestSQLiteToCrumbComparison:
    """Compare .crumb output structure against expected format."""

    def test_crumb_dict_has_required_fields(self):
        recipes = read_all_recipes()
        for recipe in recipes[:5]:
            d = recipe_to_crumb_dict(recipe)
            assert "uuid" in d
            assert "name" in d
            assert "steps" in d
            assert "ingredients" in d
            assert "serves" in d
            assert "duration" in d
            assert d["name"] == recipe.name
            assert d["uuid"] == recipe.uuid


@_skip_no_db
class TestFullPipeline:
    """Test the complete pipeline: SQLite → Markdown → .crumb file."""

    def test_full_pipeline(self):
        recipes = read_all_recipes()
        if not recipes:
            pytest.skip("No recipes in database")

        recipe = recipes[0]

        # SQLite → Markdown
        md = recipe_to_markdown(recipe, include_images=False)

        # Markdown → Recipe
        parsed = markdown_to_recipe(md)

        # Recipe → .crumb
        with tempfile.NamedTemporaryFile(suffix=".crumb", delete=False) as f:
            path = Path(f.name)

        try:
            write_crumb(parsed, path)

            # Read back .crumb
            final = read_crumb(path)
            assert final.name == recipe.name
            assert final.uuid == recipe.uuid
        finally:
            path.unlink(missing_ok=True)
