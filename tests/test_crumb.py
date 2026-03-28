"""Tests for .crumb file handling."""

import json
import tempfile
from pathlib import Path

from crouton_sync.crumb import read_crumb, recipe_to_crumb_dict, write_crumb
from crouton_sync.models import Ingredient, Recipe, Step

SAMPLE_CRUMB_JSON = {
    "uuid": "2F96A839-4A89-4EAA-AEBA-AA9DE17C7C25",
    "name": "Oven-Roasted Asparagus",
    "steps": [
        {
            "isSection": False,
            "step": "Preheat oven to 450\u00baF. Toss asparagus with olive oil.",
            "order": 0,
            "uuid": "C53F8A18-1EF6-47D2-BD3B-D45C67DFE2E2",
        },
        {
            "isSection": False,
            "step": "Roast until tender and slightly charred, 12-15 minutes.",
            "order": 1,
            "uuid": "B7EBA7C6-27A6-4E79-8DD4-F37EA0CF9C96",
        },
    ],
    "webLink": "https://www.delish.com/cooking/recipe-ideas/a58375/oven-roasted-asparagus-recipe/",
    "sourceName": "Delish",
    "ingredients": [
        {
            "ingredient": {"name": "asparagus, stalks trimmed", "uuid": "DC815E2B-1"},
            "uuid": "3C84A6C0-1",
            "quantity": {"amount": 2, "quantityType": "POUND"},
            "order": 0,
        },
        {
            "ingredient": {"name": "extra-virgin olive oil", "uuid": "DEEBACFA-1"},
            "uuid": "6FB42FE2-1",
            "quantity": {"quantityType": "TABLESPOON", "amount": 3},
            "order": 1,
        },
        {
            "ingredient": {"name": "Kosher salt", "uuid": "73B0C84E-1"},
            "uuid": "FB3C6358-1",
            "order": 2,
        },
        {
            "ingredient": {"name": "Freshly ground black pepper", "uuid": "F4B4F0ED-1"},
            "uuid": "95F435F8-1",
            "order": 3,
        },
    ],
    "images": [],
    "duration": 5,
    "tags": [],
    "folderIDs": [],
    "isPublicRecipe": False,
    "serves": 4,
    "defaultScale": 1,
}


def _write_sample_crumb(tmp_path: Path) -> Path:
    """Write the sample crumb JSON to a temp file and return its path."""
    path = tmp_path / "sample.crumb"
    path.write_text(json.dumps(SAMPLE_CRUMB_JSON))
    return path


class TestReadCrumb:
    def test_read_sample_crumb(self, tmp_path):
        """Test reading a .crumb file."""
        path = _write_sample_crumb(tmp_path)
        recipe = read_crumb(path)
        assert recipe.name == "Oven-Roasted Asparagus"
        assert recipe.uuid == "2F96A839-4A89-4EAA-AEBA-AA9DE17C7C25"
        assert recipe.servings == 4
        assert recipe.source_name == "Delish"
        assert len(recipe.ingredients) == 4
        assert len(recipe.steps) == 2

    def test_read_parses_ingredients(self, tmp_path):
        """Test that ingredient details are parsed correctly."""
        path = _write_sample_crumb(tmp_path)
        recipe = read_crumb(path)
        ing = recipe.ingredients[0]
        assert ing.name == "asparagus, stalks trimmed"
        assert ing.amount == 2
        assert ing.quantity_type == "POUND"

    def test_read_ingredient_without_quantity(self, tmp_path):
        """Test that ingredients without a quantity still parse."""
        path = _write_sample_crumb(tmp_path)
        recipe = read_crumb(path)
        salt = recipe.ingredients[2]
        assert salt.name == "Kosher salt"
        assert salt.amount is None


class TestWriteCrumb:
    def test_write_and_read_back(self):
        recipe = Recipe(
            name="Test Recipe",
            uuid="TEST-UUID",
            ingredients=[
                Ingredient(name="flour", amount=2.0, quantity_type="CUP", order=0),
            ],
            steps=[
                Step(text="Mix.", order=0),
            ],
            servings=4,
            prep_time=5,
        )

        with tempfile.NamedTemporaryFile(suffix=".crumb", delete=False) as f:
            path = Path(f.name)

        try:
            write_crumb(recipe, path)
            parsed = read_crumb(path)
            assert parsed.name == "Test Recipe"
            assert parsed.uuid == "TEST-UUID"
            assert len(parsed.ingredients) == 1
            assert parsed.ingredients[0].name == "flour"
            assert parsed.ingredients[0].amount == 2.0
            assert parsed.ingredients[0].quantity_type == "CUP"
        finally:
            path.unlink(missing_ok=True)


class TestRecipeToCrumbDict:
    def test_structure(self):
        recipe = Recipe(
            name="Test",
            uuid="UUID-1",
            ingredients=[
                Ingredient(name="sugar", amount=1.0, quantity_type="CUP", order=0),
            ],
            steps=[
                Step(text="Stir.", order=0),
                Step(text="Topping:", order=1, is_section=True),
                Step(text="Add topping.", order=2),
            ],
            servings=2,
            prep_time=5,
            cook_time=10,
            source_name="Kitchen",
            source_url="https://example.com",
        )

        d = recipe_to_crumb_dict(recipe)
        assert d["uuid"] == "UUID-1"
        assert d["name"] == "Test"
        assert d["serves"] == 2
        assert d["duration"] == 5
        assert d["cookingDuration"] == 10
        assert d["sourceName"] == "Kitchen"
        assert d["webLink"] == "https://example.com"
        assert len(d["steps"]) == 3
        assert d["steps"][1]["isSection"] is True
        assert len(d["ingredients"]) == 1
        assert d["ingredients"][0]["ingredient"]["name"] == "sugar"
        assert d["ingredients"][0]["quantity"]["amount"] == 1.0
        assert d["ingredients"][0]["quantity"]["quantityType"] == "CUP"
