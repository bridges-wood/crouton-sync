"""Read and write recipes from Crouton's Core Data SQLite store."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from crouton_sync.models import Ingredient, Recipe, Step

DEFAULT_DB_PATH = Path.home() / "Library/Group Containers/group.com.meals.ios/Meals.sqlite"
DEFAULT_IMAGES_DIR = Path.home() / "Library/Group Containers/group.com.meals.ios/MealImages"

# Tables that are valid for PK lookups and Z_MAX updates
_VALID_TABLES = frozenset({
    "ZCDMEAL",
    "ZCDMEALSTEP",
    "ZCDMEASUREDINGREDIENT",
    "ZCDINGREDIENT",
    "ATRANSACTION",
    "ACHANGE",
})

_VALID_ENTITY_NAMES = frozenset({
    "CDMeal",
    "CDMealStep",
    "CDMeasuredIngredient",
    "CDIngredient",
    "TRANSACTION",
    "CHANGE",
})


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    if not path.exists():
        raise FileNotFoundError(f"Crouton database not found at {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _open_db(db_path: Path | None = None):
    """Context manager for database connections."""
    conn = _connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def _backup_database(db_path: Path | None = None) -> Path:
    """Create a backup of the database before writing. Returns backup path."""
    path = db_path or DEFAULT_DB_PATH
    backup_path = path.with_suffix(".sqlite.bak")
    shutil.copy2(path, backup_path)
    return backup_path


def _is_crouton_running() -> bool:
    """Check if the Crouton app is currently running."""
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(
            ["pgrep", "-x", "Crouton"],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def read_all_recipes(
    db_path: Path | None = None,
    include_deleted: bool = False,
) -> list[Recipe]:
    """Read all recipes from the Crouton database."""
    with _open_db(db_path) as conn:
        return _fetch_recipes(conn, include_deleted)


def read_recipe_by_uuid(
    uuid: str,
    db_path: Path | None = None,
) -> Recipe | None:
    """Read a single recipe by UUID."""
    with _open_db(db_path) as conn:
        recipes = _fetch_recipes(conn, include_deleted=False, uuid_filter=uuid)
        return recipes[0] if recipes else None


def _fetch_recipes(
    conn: sqlite3.Connection,
    include_deleted: bool = False,
    uuid_filter: str | None = None,
) -> list[Recipe]:
    """Fetch recipes with all related data."""
    where_clauses = []
    params: list[str] = []

    if not include_deleted:
        where_clauses.append("(m.ZDELETEDFROMDEVICE = 0 OR m.ZDELETEDFROMDEVICE IS NULL)")
    if uuid_filter:
        where_clauses.append("m.ZUUID = ?")
        params.append(uuid_filter)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    meals = conn.execute(
        f"""
        SELECT m.Z_PK, m.ZUUID, m.ZNAME, m.ZSERVES, m.ZDURATION, m.ZCOOKINGDURATION,
               m.ZDEFAULTSCALE, m.ZWEBLINK, m.ZSOURCENAME, m.ZNEUTRITIONALINFO,
               m.ZNOTES, m.ZMETHOD, m.ZFOLDERIDS, m.ZIMAGENAMES, m.ZSOURCEIMAGENAME,
               m.ZHEADERIMAGE, m.ZRATING, m.ZRAWDIFFICULTY, m.ZISPUBLICRECIPE,
               m.ZDATECREATED, m.ZDATEMODIFIED
        FROM ZCDMEAL m
        {where_sql}
        ORDER BY m.ZNAME
        """,
        params,
    ).fetchall()

    # Pre-fetch all tags and folders for efficient lookup
    tag_map = _build_tag_map(conn)
    folder_map = _build_folder_map(conn)
    recipe_tag_map = _build_recipe_tag_map(conn)

    recipes = []
    for meal in meals:
        pk = meal["Z_PK"]

        # Fetch steps
        steps = _fetch_steps(conn, pk)

        # Fetch ingredients
        ingredients = _fetch_ingredients(conn, pk)

        # Resolve tags
        tag_pks = recipe_tag_map.get(pk, [])
        tags = [tag_map[tpk] for tpk in tag_pks if tpk in tag_map]

        # Resolve folders from ZFOLDERIDS
        folder_id_str = meal["ZFOLDERIDS"] or ""
        folder_ids = [fid.strip() for fid in folder_id_str.split(",") if fid.strip()]
        folders = [folder_map.get(fid, fid) for fid in folder_ids]

        # Parse image filenames
        image_names_str = meal["ZIMAGENAMES"] or ""
        image_filenames = [n.strip() for n in image_names_str.split(",") if n.strip()]

        recipe = Recipe(
            name=(meal["ZNAME"] or "").strip(),
            uuid=meal["ZUUID"] or "",
            ingredients=ingredients,
            steps=steps,
            tags=tags,
            folders=folders,
            folder_ids=folder_ids,
            prep_time=meal["ZDURATION"],
            cook_time=meal["ZCOOKINGDURATION"],
            servings=meal["ZSERVES"],
            default_scale=meal["ZDEFAULTSCALE"] or 1.0,
            source_name=meal["ZSOURCENAME"] or "",
            source_url=meal["ZWEBLINK"] or "",
            image_filenames=image_filenames,
            source_image_filename=meal["ZSOURCEIMAGENAME"] or "",
            header_image_filename=meal["ZHEADERIMAGE"] or "",
            nutritional_info=meal["ZNEUTRITIONALINFO"] or "",
            notes=meal["ZNOTES"] or "",
            method=meal["ZMETHOD"] or "",
            rating=meal["ZRATING"] or 0,
            difficulty=meal["ZRAWDIFFICULTY"] or "",
            is_public=bool(meal["ZISPUBLICRECIPE"]),
            date_created=meal["ZDATECREATED"],
            date_modified=meal["ZDATEMODIFIED"],
        )
        recipes.append(recipe)

    return recipes


def _fetch_steps(conn: sqlite3.Connection, meal_pk: int) -> list[Step]:
    rows = conn.execute(
        """
        SELECT ZORDER, ZSTEP, ZISSECTION, ZUUID
        FROM ZCDMEALSTEP
        WHERE ZMEAL = ?
        ORDER BY ZORDER
        """,
        (meal_pk,),
    ).fetchall()
    return [
        Step(
            text=row["ZSTEP"] or "",
            order=row["ZORDER"] or 0,
            is_section=bool(row["ZISSECTION"]),
            uuid=row["ZUUID"] or "",
        )
        for row in rows
    ]


def _fetch_ingredients(conn: sqlite3.Connection, meal_pk: int) -> list[Ingredient]:
    rows = conn.execute(
        """
        SELECT mi.ZAMOUNT, mi.ZSECONDARYAMOUNT, mi.ZQUANTITYTYPE, mi.ZORDER, mi.ZUUID,
               i.ZNAME
        FROM ZCDMEASUREDINGREDIENT mi
        LEFT JOIN ZCDINGREDIENT i ON mi.ZINGREDIENT = i.Z_PK
        WHERE mi.ZMEAL = ?
        ORDER BY mi.ZORDER
        """,
        (meal_pk,),
    ).fetchall()
    return [
        Ingredient(
            name=row["ZNAME"] or "",
            amount=row["ZAMOUNT"],
            secondary_amount=row["ZSECONDARYAMOUNT"],
            quantity_type=row["ZQUANTITYTYPE"],
            order=row["ZORDER"] or 0,
            uuid=row["ZUUID"] or "",
        )
        for row in rows
    ]


def _build_tag_map(conn: sqlite3.Connection) -> dict[int, str]:
    """Map tag Z_PK → tag name."""
    rows = conn.execute(
        "SELECT Z_PK, ZNAME FROM ZCDTAG WHERE ZDELETEDFROMDEVICE = 0 OR ZDELETEDFROMDEVICE IS NULL"
    ).fetchall()
    return {row["Z_PK"]: row["ZNAME"] for row in rows}


def _build_folder_map(conn: sqlite3.Connection) -> dict[str, str]:
    """Map folder UUID → folder name."""
    rows = conn.execute(
        "SELECT ZUUID, ZNAME FROM ZCDFOLDER"
        " WHERE ZDELETEDFROMDEVICE = 0 OR ZDELETEDFROMDEVICE IS NULL"
    ).fetchall()
    return {row["ZUUID"]: row["ZNAME"] for row in rows}


def _build_recipe_tag_map(conn: sqlite3.Connection) -> dict[int, list[int]]:
    """Map recipe Z_PK → list of tag Z_PKs."""
    rows = conn.execute("SELECT Z_6RECIPES, Z_10TAGS1 FROM Z_6TAGS").fetchall()
    result: dict[int, list[int]] = {}
    for row in rows:
        result.setdefault(row["Z_6RECIPES"], []).append(row["Z_10TAGS1"])
    return result


# ── Write support ──────────────────────────────────────────────────────────


def _get_next_pk(conn: sqlite3.Connection, table: str) -> int:
    """Get the next available primary key for a Core Data table."""
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    row = conn.execute(f"SELECT MAX(Z_PK) as max_pk FROM {table}").fetchone()
    return (row["max_pk"] or 0) + 1


def _update_z_max(conn: sqlite3.Connection, entity_name: str, new_max: int) -> None:
    """Update Z_PRIMARYKEY.Z_MAX for the given entity."""
    if entity_name not in _VALID_ENTITY_NAMES:
        raise ValueError(f"Invalid entity name: {entity_name}")
    conn.execute(
        "UPDATE Z_PRIMARYKEY SET Z_MAX = ? WHERE Z_NAME = ? AND Z_MAX < ?",
        (new_max, entity_name, new_max),
    )


def _create_transaction(conn: sqlite3.Connection) -> int:
    """Create a new ATRANSACTION record and return its PK."""
    import time

    # Core Data timestamps are seconds since 2001-01-01
    core_data_epoch = 978307200  # Unix timestamp for 2001-01-01
    timestamp = time.time() - core_data_epoch

    next_pk = _get_next_pk(conn, "ATRANSACTION")
    conn.execute(
        """
        INSERT INTO ATRANSACTION (Z_PK, Z_ENT, Z_OPT, ZTIMESTAMP)
        VALUES (?, 16002, 1, ?)
        """,
        (next_pk, timestamp),
    )
    _update_z_max(conn, "TRANSACTION", next_pk)
    return next_pk


def _record_change(
    conn: sqlite3.Connection,
    transaction_id: int,
    entity_type: int,
    entity_pk: int,
    change_type: int = 0,
) -> None:
    """Record a change in ACHANGE for CloudKit sync. change_type: 0=insert, 2=update."""
    next_pk = _get_next_pk(conn, "ACHANGE")
    conn.execute(
        """
        INSERT INTO ACHANGE (Z_PK, Z_ENT, Z_OPT, ZCHANGETYPE, ZENTITY, ZENTITYPK, ZTRANSACTIONID)
        VALUES (?, 16001, 1, ?, ?, ?, ?)
        """,
        (next_pk, change_type, entity_type, entity_pk, transaction_id),
    )
    _update_z_max(conn, "CHANGE", next_pk)


def _find_or_create_ingredient(conn: sqlite3.Connection, name: str) -> int:
    """Find an existing ingredient by name or create a new one. Returns Z_PK."""
    import uuid as uuid_mod

    row = conn.execute("SELECT Z_PK FROM ZCDINGREDIENT WHERE ZNAME = ?", (name,)).fetchone()
    if row:
        return row["Z_PK"]

    pk = _get_next_pk(conn, "ZCDINGREDIENT")
    conn.execute(
        """
        INSERT INTO ZCDINGREDIENT (Z_PK, Z_ENT, Z_OPT, ZNAME, ZUUID)
        VALUES (?, 5, 1, ?, ?)
        """,
        (pk, name, str(uuid_mod.uuid4()).upper()),
    )
    _update_z_max(conn, "CDIngredient", pk)
    return pk


def write_recipe(
    recipe: Recipe,
    db_path: Path | None = None,
    images_dir: Path | None = None,
    image_data: dict[str, bytes] | None = None,
) -> str:
    """Write a recipe to the Crouton database. Returns the recipe UUID.

    Args:
        recipe: The recipe to write.
        db_path: Path to Meals.sqlite.
        images_dir: Path to MealImages directory.
        image_data: Optional dict of filename → image bytes to write.

    Raises:
        RuntimeError: If Crouton is running or recipe UUID already exists.
    """
    import uuid as uuid_mod

    if _is_crouton_running():
        raise RuntimeError(
            "Crouton is currently running. Quit Crouton before writing to the database "
            "to avoid data corruption."
        )

    backup_path = _backup_database(db_path)
    img_dir = images_dir or DEFAULT_IMAGES_DIR

    with _open_db(db_path) as conn:
        try:
            recipe_uuid = recipe.uuid or str(uuid_mod.uuid4()).upper()

            # Check for duplicate UUID
            existing = conn.execute(
                "SELECT Z_PK FROM ZCDMEAL WHERE ZUUID = ?", (recipe_uuid,)
            ).fetchone()
            if existing:
                raise RuntimeError(
                    f"Recipe with UUID {recipe_uuid} already exists in the database. "
                    "Use update_recipe_field to modify existing recipes."
                )

            transaction_id = _create_transaction(conn)

            # Insert meal
            meal_pk = _get_next_pk(conn, "ZCDMEAL")
            conn.execute(
                """
                INSERT INTO ZCDMEAL (
                    Z_PK, Z_ENT, Z_OPT, ZNAME, ZUUID, ZSERVES, ZDURATION, ZCOOKINGDURATION,
                    ZDEFAULTSCALE, ZWEBLINK, ZSOURCENAME, ZNEUTRITIONALINFO, ZNOTES, ZMETHOD,
                    ZFOLDERIDS, ZIMAGENAMES, ZSOURCEIMAGENAME, ZHEADERIMAGE, ZRATING,
                    ZRAWDIFFICULTY, ZISPUBLICRECIPE, ZDELETEDFROMDEVICE, ZUPLOADED,
                    ZDATECREATED, ZDATEMODIFIED, ZRECORDID
                ) VALUES (
                    ?, 6, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?
                )
                """,
                (
                    meal_pk,
                    recipe.name,
                    recipe_uuid,
                    recipe.servings,
                    recipe.prep_time,
                    recipe.cook_time,
                    recipe.default_scale,
                    recipe.source_url or None,
                    recipe.source_name or None,
                    recipe.nutritional_info or None,
                    recipe.notes or None,
                    recipe.method or None,
                    ",".join(recipe.folder_ids) if recipe.folder_ids else None,
                    ",".join(recipe.image_filenames) if recipe.image_filenames else None,
                    recipe.source_image_filename or None,
                    recipe.header_image_filename or None,
                    recipe.rating,
                    recipe.difficulty or None,
                    1 if recipe.is_public else 0,
                    recipe.date_created,
                    recipe.date_modified,
                    recipe_uuid,
                ),
            )
            _update_z_max(conn, "CDMeal", meal_pk)
            _record_change(conn, transaction_id, 6, meal_pk, change_type=0)

            # Insert steps
            for step in recipe.steps:
                step_pk = _get_next_pk(conn, "ZCDMEALSTEP")
                step_uuid = step.uuid or str(uuid_mod.uuid4()).upper()
                conn.execute(
                    """
                    INSERT INTO ZCDMEALSTEP
                        (Z_PK, Z_ENT, Z_OPT, ZMEAL, ZORDER, ZSTEP, ZISSECTION, ZUUID)
                    VALUES (?, 8, 1, ?, ?, ?, ?, ?)
                    """,
                    (step_pk, meal_pk, step.order, step.text,
                     1 if step.is_section else 0, step_uuid),
                )
                _update_z_max(conn, "CDMealStep", step_pk)
                _record_change(conn, transaction_id, 8, step_pk, change_type=0)

            # Insert ingredients
            for ing in recipe.ingredients:
                ing_pk = _find_or_create_ingredient(conn, ing.name)
                mi_pk = _get_next_pk(conn, "ZCDMEASUREDINGREDIENT")
                mi_uuid = ing.uuid or str(uuid_mod.uuid4()).upper()
                conn.execute(
                    """
                    INSERT INTO ZCDMEASUREDINGREDIENT (
                        Z_PK, Z_ENT, Z_OPT, ZMEAL, ZINGREDIENT, ZAMOUNT, ZSECONDARYAMOUNT,
                        ZQUANTITYTYPE, ZORDER, ZUUID
                    ) VALUES (?, 9, 1, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        mi_pk,
                        meal_pk,
                        ing_pk,
                        ing.amount,
                        ing.secondary_amount,
                        ing.quantity_type,
                        ing.order,
                        mi_uuid,
                    ),
                )
                _update_z_max(conn, "CDMeasuredIngredient", mi_pk)
                _record_change(conn, transaction_id, 9, mi_pk, change_type=0)

            # Write image files
            if image_data:
                for filename, data in image_data.items():
                    img_path = img_dir / filename
                    img_path.write_bytes(data)

            conn.commit()
            print(f"  Database backed up to {backup_path}")
            return recipe_uuid

        except Exception:
            conn.rollback()
            raise


def update_recipe_field(
    uuid: str,
    field: str,
    value: str | int | float | None,
    db_path: Path | None = None,
) -> bool:
    """Update a single field on a recipe by UUID. Returns True if updated."""
    allowed = {
        "ZNAME",
        "ZNOTES",
        "ZMETHOD",
        "ZNEUTRITIONALINFO",
        "ZSOURCENAME",
        "ZWEBLINK",
        "ZSERVES",
        "ZDURATION",
        "ZCOOKINGDURATION",
        "ZRATING",
        "ZRAWDIFFICULTY",
        "ZDEFAULTSCALE",
    }
    col = field.upper()
    if col not in allowed:
        raise ValueError(f"Field {field} is not allowed for direct update")

    if _is_crouton_running():
        raise RuntimeError(
            "Crouton is currently running. Quit Crouton before writing to the database "
            "to avoid data corruption."
        )

    _backup_database(db_path)

    with _open_db(db_path) as conn:
        try:
            row = conn.execute(
                "SELECT Z_PK, Z_OPT FROM ZCDMEAL WHERE ZUUID = ?", (uuid,)
            ).fetchone()
            if not row:
                return False

            pk = row["Z_PK"]
            new_opt = (row["Z_OPT"] or 0) + 1

            transaction_id = _create_transaction(conn)

            conn.execute(
                f"UPDATE ZCDMEAL SET {col} = ?, Z_OPT = ? WHERE Z_PK = ?",
                (value, new_opt, pk),
            )
            _record_change(conn, transaction_id, 6, pk, change_type=2)

            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise


def get_image_path(filename: str, images_dir: Path | None = None) -> Path | None:
    """Get the full path to a recipe image file, or None if not found."""
    img_dir = images_dir or DEFAULT_IMAGES_DIR
    path = img_dir / filename
    return path if path.exists() else None
