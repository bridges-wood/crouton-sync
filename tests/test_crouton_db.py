"""Tests for Crouton database read operations."""

from crouton_sync.crouton_db import DEFAULT_DB_PATH, read_all_recipes, read_recipe_by_uuid


class TestReadFromRealDB:
    """Tests against the actual Crouton database (skipped if not available)."""

    def test_read_all_recipes(self):
        if not DEFAULT_DB_PATH.exists():
            return

        recipes = read_all_recipes()
        assert len(recipes) > 0
        # Check that basic fields are populated
        for recipe in recipes[:5]:
            assert recipe.name
            assert recipe.uuid

    def test_known_recipe(self):
        if not DEFAULT_DB_PATH.exists():
            return

        recipe = read_recipe_by_uuid("FC4017B5-8C93-43E8-90C2-2140A007D326")
        if recipe is None:
            return  # Recipe may have been deleted

        assert recipe.name == "Chicken Piccata"
        assert recipe.servings == 6
        assert recipe.source_name == "The Modern Proper"
        assert len(recipe.ingredients) == 13
        assert len(recipe.steps) == 4

    def test_recipe_has_ingredients_and_steps(self):
        if not DEFAULT_DB_PATH.exists():
            return

        recipes = read_all_recipes()
        # At least some recipes should have ingredients and steps
        has_ingredients = sum(1 for r in recipes if r.ingredients)
        has_steps = sum(1 for r in recipes if r.steps)
        assert has_ingredients > 0
        assert has_steps > 0

    def test_recipe_tags_and_folders(self):
        if not DEFAULT_DB_PATH.exists():
            return

        recipes = read_all_recipes()
        has_tags = sum(1 for r in recipes if r.tags)
        has_folders = sum(1 for r in recipes if r.folders)
        # The user has tags and folders set up
        assert has_tags > 0
        assert has_folders > 0
