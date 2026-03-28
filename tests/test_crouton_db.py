"""Tests for Crouton database read operations."""

import pytest

from crouton_sync.crouton_db import DEFAULT_DB_PATH, read_all_recipes, read_recipe_by_uuid

_skip_no_db = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(), reason="Crouton database not available"
)


@_skip_no_db
class TestReadFromRealDB:
    """Tests against the actual Crouton database (skipped if not available)."""

    def test_read_all_recipes(self):
        recipes = read_all_recipes()
        assert len(recipes) > 0
        for recipe in recipes[:5]:
            assert recipe.name
            assert recipe.uuid

    def test_known_recipe(self):
        recipe = read_recipe_by_uuid("FC4017B5-8C93-43E8-90C2-2140A007D326")
        if recipe is None:
            pytest.skip("Recipe may have been deleted")

        assert recipe.name == "Chicken Piccata"
        assert recipe.servings == 6
        assert recipe.source_name == "The Modern Proper"
        assert len(recipe.ingredients) == 13
        assert len(recipe.steps) == 4

    def test_recipe_has_ingredients_and_steps(self):
        recipes = read_all_recipes()
        has_ingredients = sum(1 for r in recipes if r.ingredients)
        has_steps = sum(1 for r in recipes if r.steps)
        assert has_ingredients > 0
        assert has_steps > 0

    def test_recipe_tags_and_folders(self):
        recipes = read_all_recipes()
        has_tags = sum(1 for r in recipes if r.tags)
        has_folders = sum(1 for r in recipes if r.folders)
        assert has_tags > 0
        assert has_folders > 0
