"""Tests for recipe verification / validation."""

from crouton_sync.verify import validate_markdown


class TestValidateMarkdown:
    def test_valid_recipe(self):
        md = """---
crouton_uuid: TEST-UUID-1234
servings: 4
prep_time: 10
cook_time: 30
source_name: Test Kitchen
---

# Pasta Carbonara

## Ingredients

- 1 lb spaghetti
- 4 oz pancetta
- 3 eggs
- 1 cup parmesan

## Instructions

1. Cook pasta in salted boiling water.
2. Fry pancetta until crispy.
3. Whisk eggs with parmesan.
4. Toss everything together.
"""
        result = validate_markdown(md)
        assert result.ok
        assert result.recipe_name == "Pasta Carbonara"
        assert not result.errors

    def test_missing_title(self):
        md = """---
crouton_uuid: TEST
---

## Ingredients

- 1 cup flour

## Instructions

1. Mix.
"""
        result = validate_markdown(md)
        assert not result.ok
        assert any("title" in e.lower() for e in result.errors)

    def test_missing_ingredients(self):
        md = """---
crouton_uuid: TEST
---

# My Recipe

## Instructions

1. Do something.
"""
        result = validate_markdown(md)
        assert not result.ok
        assert any("ingredient" in e.lower() for e in result.errors)

    def test_missing_instructions(self):
        md = """---
crouton_uuid: TEST
---

# My Recipe

## Ingredients

- 1 cup flour
"""
        result = validate_markdown(md)
        assert not result.ok
        assert any("instruction" in e.lower() for e in result.errors)

    def test_warning_no_uuid(self):
        md = """---
servings: 4
---

# My Recipe

## Ingredients

- 1 cup flour

## Instructions

1. Mix well.
"""
        result = validate_markdown(md)
        assert result.ok  # warnings don't make it invalid
        assert any("uuid" in w.lower() for w in result.warnings)

    def test_warning_no_servings(self):
        md = """---
crouton_uuid: TEST-UUID
---

# My Recipe

## Ingredients

- 1 cup flour

## Instructions

1. Mix well.
"""
        result = validate_markdown(md)
        assert result.ok
        assert any("servings" in w.lower() for w in result.warnings)

    def test_completely_empty(self):
        result = validate_markdown("")
        assert not result.ok

    def test_minimal_valid(self):
        md = """# Quick Oats

## Ingredients

- 1 cup oats
- 2 cup water

## Instructions

1. Combine oats and water.
2. Microwave for 2 minutes.
"""
        result = validate_markdown(md)
        assert result.ok
        assert result.recipe_name == "Quick Oats"
        # Should warn about missing uuid, servings, times, source
        assert len(result.warnings) > 0

    def test_info_reports_counts(self):
        md = """---
crouton_uuid: TEST
tags:
  - breakfast
---

# Oatmeal

## Ingredients

- 1 cup oats
- 2 cup water
- 1 pinch salt

## Instructions

### Cooking:

1. Boil water.
2. Add oats.

### Serving:

3. Serve warm.
"""
        result = validate_markdown(md)
        assert result.ok
        assert any("Ingredients: 3" in i for i in result.info)
        assert any("Steps: 3" in i for i in result.info)
        assert any("Sections: 2" in i for i in result.info)
        assert any("breakfast" in i for i in result.info)
