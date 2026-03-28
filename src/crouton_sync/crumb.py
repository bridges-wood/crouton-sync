"""Parse and serialize Crouton .crumb files (JSON format)."""

from __future__ import annotations

import base64
import json
import uuid as uuid_mod
from pathlib import Path

from crouton_sync.models import Ingredient, Recipe, Step


def read_crumb(path: Path) -> Recipe:
    """Parse a .crumb file into a Recipe model."""
    with open(path) as f:
        data = json.load(f)

    ingredients = []
    for item in data.get("ingredients", []):
        ing_data = item.get("ingredient", {})
        qty = item.get("quantity", {})
        ingredients.append(
            Ingredient(
                name=ing_data.get("name", ""),
                amount=qty.get("amount"),
                quantity_type=qty.get("quantityType"),
                order=item.get("order", 0),
                uuid=item.get("uuid", ""),
            )
        )

    steps = []
    for item in data.get("steps", []):
        steps.append(
            Step(
                text=item.get("step", ""),
                order=item.get("order", 0),
                is_section=item.get("isSection", False),
                uuid=item.get("uuid", ""),
            )
        )

    return Recipe(
        name=data.get("name", ""),
        uuid=data.get("uuid", ""),
        ingredients=ingredients,
        steps=steps,
        tags=data.get("tags", []),
        folders=[],
        folder_ids=data.get("folderIDs", []),
        prep_time=data.get("duration"),
        cook_time=data.get("cookingDuration"),
        servings=data.get("serves"),
        default_scale=data.get("defaultScale", 1.0),
        source_name=data.get("sourceName", ""),
        source_url=data.get("webLink", ""),
        nutritional_info=data.get("neutritionalInfo", ""),
        notes="",
        rating=0,
        is_public=data.get("isPublicRecipe", False),
    )


def write_crumb(recipe: Recipe, path: Path, image_data: list[bytes] | None = None) -> None:
    """Serialize a Recipe model to a .crumb JSON file."""
    data = recipe_to_crumb_dict(recipe, image_data)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def recipe_to_crumb_dict(
    recipe: Recipe,
    image_data: list[bytes] | None = None,
) -> dict:
    """Convert a Recipe to a .crumb-compatible dictionary."""
    recipe_uuid = recipe.uuid or str(uuid_mod.uuid4()).upper()

    ingredients = []
    for ing in sorted(recipe.ingredients, key=lambda i: i.order):
        ing_uuid = ing.uuid or str(uuid_mod.uuid4()).upper()
        item_uuid = str(uuid_mod.uuid4()).upper()

        ing_dict: dict = {
            "ingredient": {
                "name": ing.name,
                "uuid": ing_uuid,
            },
            "uuid": item_uuid,
            "order": int(ing.order),
        }

        if ing.amount is not None or ing.quantity_type:
            qty: dict = {}
            if ing.amount is not None:
                qty["amount"] = ing.amount
            if ing.quantity_type:
                qty["quantityType"] = ing.quantity_type
            ing_dict["quantity"] = qty

        ingredients.append(ing_dict)

    steps = []
    for step in sorted(recipe.steps, key=lambda s: s.order):
        step_uuid = step.uuid or str(uuid_mod.uuid4()).upper()
        steps.append(
            {
                "order": step.order,
                "step": step.text,
                "isSection": step.is_section,
                "uuid": step_uuid,
            }
        )

    # Build images list
    images: list[str] = []
    if image_data:
        for data in image_data:
            images.append(base64.b64encode(data).decode("ascii"))

    result: dict = {
        "uuid": recipe_uuid,
        "name": recipe.name,
        "steps": steps,
        "ingredients": ingredients,
        "images": images,
        "duration": recipe.prep_time or 0,
        "tags": recipe.tags,
        "folderIDs": recipe.folder_ids,
        "isPublicRecipe": recipe.is_public,
        "serves": recipe.servings or 0,
        "defaultScale": recipe.default_scale,
    }

    if recipe.cook_time is not None:
        result["cookingDuration"] = recipe.cook_time

    if recipe.source_url:
        result["webLink"] = recipe.source_url
    if recipe.source_name:
        result["sourceName"] = recipe.source_name
    if recipe.nutritional_info:
        result["neutritionalInfo"] = recipe.nutritional_info

    return result
