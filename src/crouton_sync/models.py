"""Data models for Crouton recipe representation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Ingredient:
    """A measured ingredient in a recipe."""

    name: str
    amount: float | None = None
    secondary_amount: float | None = None
    quantity_type: str | None = None
    order: float = 0  # Float to match Crouton's ZCDMEASUREDINGREDIENT.ZORDER schema
    uuid: str = ""


@dataclass
class Step:
    """A recipe step or section header."""

    text: str
    order: int = 0
    is_section: bool = False
    uuid: str = ""


@dataclass
class Recipe:
    """Complete recipe representation."""

    name: str
    uuid: str = ""
    ingredients: list[Ingredient] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    folders: list[str] = field(default_factory=list)
    folder_ids: list[str] = field(default_factory=list)

    # Timing
    prep_time: float | None = None
    cook_time: float | None = None

    # Serving
    servings: int | None = None
    default_scale: float = 1.0

    # Source
    source_name: str = ""
    source_url: str = ""

    # Media
    image_filenames: list[str] = field(default_factory=list)
    source_image_filename: str = ""
    header_image_filename: str = ""

    # Metadata
    nutritional_info: str = ""
    notes: str = ""
    method: str = ""
    rating: int = 0
    difficulty: str = ""
    is_public: bool = False

    # Dates
    date_created: float | None = None
    date_modified: float | None = None
