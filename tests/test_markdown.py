"""Tests for Markdown export and import."""

from crouton_sync.markdown import (
    _format_ingredient,
    _parse_ingredient_line,
    markdown_to_recipe,
    recipe_to_markdown,
)
from crouton_sync.models import Ingredient, Recipe, Step


class TestFormatIngredient:
    def test_with_amount_and_unit(self):
        ing = Ingredient(name="chicken cutlets", amount=2.0, quantity_type="POUND")
        assert _format_ingredient(ing) == "2 lb chicken cutlets"

    def test_item_type(self):
        ing = Ingredient(name="large eggs", amount=2.0, quantity_type="ITEM")
        assert _format_ingredient(ing) == "2 large eggs"

    def test_no_amount(self):
        ing = Ingredient(name="salt")
        assert _format_ingredient(ing) == "salt"

    def test_fraction(self):
        ing = Ingredient(name="all-purpose flour", amount=0.5, quantity_type="CUP")
        assert _format_ingredient(ing) == "½ cup all-purpose flour"


class TestParseIngredientLine:
    def test_amount_unit_name(self):
        ing = _parse_ingredient_line("2 lb chicken cutlets")
        assert ing.amount == 2.0
        assert ing.quantity_type == "POUND"
        assert ing.name == "chicken cutlets"

    def test_amount_name_no_unit(self):
        ing = _parse_ingredient_line("2 large eggs")
        assert ing.amount == 2.0
        assert ing.quantity_type == "ITEM"
        assert ing.name == "large eggs"

    def test_name_only(self):
        ing = _parse_ingredient_line("salt")
        assert ing.name == "salt"
        assert ing.amount is None

    def test_fraction(self):
        ing = _parse_ingredient_line("½ cup all-purpose flour")
        assert ing.amount == 0.5
        assert ing.quantity_type == "CUP"
        assert ing.name == "all-purpose flour"


class TestRoundtrip:
    def test_basic_roundtrip(self):
        recipe = Recipe(
            name="Test Recipe",
            uuid="TEST-UUID-1234",
            ingredients=[
                Ingredient(name="butter", amount=1.0, quantity_type="CUP", order=0),
                Ingredient(name="eggs", amount=2.0, quantity_type="ITEM", order=1),
            ],
            steps=[
                Step(text="Preheat oven.", order=0),
                Step(text="Mix ingredients.", order=1),
                Step(text="Assembly:", order=2, is_section=True),
                Step(text="Combine everything.", order=3),
            ],
            prep_time=10,
            cook_time=30,
            servings=4,
            source_name="Test Kitchen",
            source_url="https://example.com/recipe",
            tags=["Baking", "Easy"],
            folders=["Dinner"],
            notes="Great recipe!",
        )

        # Export to markdown
        md = recipe_to_markdown(recipe, include_images=False)

        # Import back
        parsed = markdown_to_recipe(md)

        assert parsed.name == "Test Recipe"
        assert parsed.uuid == "TEST-UUID-1234"
        assert parsed.prep_time == 10
        assert parsed.cook_time == 30
        assert parsed.servings == 4
        assert parsed.source_name == "Test Kitchen"
        assert parsed.source_url == "https://example.com/recipe"
        assert parsed.tags == ["Baking", "Easy"]
        assert parsed.folders == ["Dinner"]
        assert parsed.notes == "Great recipe!"

        # Check ingredients
        assert len(parsed.ingredients) == 2
        assert parsed.ingredients[0].name == "butter"
        assert parsed.ingredients[0].amount == 1.0
        assert parsed.ingredients[0].quantity_type == "CUP"
        assert parsed.ingredients[1].name == "eggs"
        assert parsed.ingredients[1].amount == 2.0

        # Check steps
        assert len(parsed.steps) == 4
        assert parsed.steps[0].text == "Preheat oven."
        assert not parsed.steps[0].is_section
        assert parsed.steps[2].text == "Assembly"
        assert parsed.steps[2].is_section

    def test_nutritional_info_roundtrip(self):
        recipe = Recipe(
            name="Nutrient Test",
            uuid="NUTR-1234",
            nutritional_info="Calories: 200\nProtein: 10g",
        )
        md = recipe_to_markdown(recipe, include_images=False)
        parsed = markdown_to_recipe(md)
        assert "Calories: 200" in parsed.nutritional_info
        assert "Protein: 10g" in parsed.nutritional_info

    def test_image_file_references(self):
        """recipe_to_markdown emits standard file references when requested."""
        recipe = Recipe(
            name="Image Test",
            uuid="IMG-1234",
            image_filenames=["photo1.jpg", "photo2.jpg"],
        )
        md = recipe_to_markdown(recipe, include_images=True, image_format="standard")
        assert "![recipe-image](images/photo1.jpg)" in md
        assert "![recipe-image](images/photo2.jpg)" in md
        assert "base64" not in md

    def test_image_obsidian_format(self):
        """recipe_to_markdown uses Obsidian wiki-links by default."""
        recipe = Recipe(
            name="Obsidian Test",
            uuid="OBS-1234",
            image_filenames=["photo1.jpg", "photo2.jpg"],
        )
        md = recipe_to_markdown(recipe, include_images=True)
        assert "![[images/photo1.jpg]]" in md
        assert "![[images/photo2.jpg]]" in md
        assert "![recipe-image]" not in md

    def test_image_file_references_no_images_flag(self):
        """include_images=False suppresses image references."""
        recipe = Recipe(
            name="No Image Test",
            uuid="NOIMG-1234",
            image_filenames=["photo.jpg"],
        )
        md = recipe_to_markdown(recipe, include_images=False)
        assert "photo.jpg" not in md

    def test_parse_image_file_references(self):
        """markdown_to_recipe extracts image filenames from standard file refs."""
        md = (
            "---\ncrouton_uuid: X\n---\n\n"
            "# Test\n\n"
            "![recipe-image](images/photo1.jpg)\n\n"
            "![recipe-image](images/photo2.jpg)\n\n"
            "## Ingredients\n\n- 1 cup flour\n\n"
            "## Instructions\n\n1. Mix.\n"
        )
        recipe = markdown_to_recipe(md)
        assert recipe.image_filenames == ["photo1.jpg", "photo2.jpg"]

    def test_parse_obsidian_image_references(self):
        """markdown_to_recipe extracts image filenames from Obsidian wiki-links."""
        md = (
            "---\ncrouton_uuid: X\n---\n\n"
            "# Test\n\n"
            "![[images/photo1.jpg]]\n\n"
            "![[images/photo2.jpg]]\n\n"
            "## Ingredients\n\n- 1 cup flour\n\n"
            "## Instructions\n\n1. Mix.\n"
        )
        recipe = markdown_to_recipe(md)
        assert recipe.image_filenames == ["photo1.jpg", "photo2.jpg"]

    def test_image_uuid_filenames_get_jpg_extension(self):
        """UUID-style filenames without extensions get .jpg appended."""
        recipe = Recipe(
            name="UUID Image Test",
            uuid="UUID-1234",
            image_filenames=["C5B6EF24-0601-4C8B-9EA9-8B149844EFD7"],
        )
        md = recipe_to_markdown(recipe, include_images=True)
        assert "C5B6EF24-0601-4C8B-9EA9-8B149844EFD7.jpg" in md

    def test_image_existing_extension_preserved(self):
        """Filenames that already have an extension are not double-suffixed."""
        recipe = Recipe(
            name="Ext Test",
            uuid="EXT-1234",
            image_filenames=["photo.png"],
        )
        md = recipe_to_markdown(recipe, include_images=True, image_format="standard")
        assert "images/photo.png)" in md
        assert ".png.jpg" not in md

    def test_parse_legacy_base64_backward_compat(self):
        """markdown_to_recipe still handles old base64 data URIs gracefully."""
        md = (
            "---\ncrouton_uuid: X\n---\n\n"
            "# Test\n\n"
            "![recipe-image](data:image/jpeg;base64,AAAA)\n\n"
            "## Ingredients\n\n- 1 cup flour\n\n"
            "## Instructions\n\n1. Mix.\n"
        )
        recipe = markdown_to_recipe(md)
        # Base64 images don't produce filenames (no filename to extract)
        assert recipe.image_filenames == []
        # But parsing doesn't crash
        assert recipe.name == "Test"
