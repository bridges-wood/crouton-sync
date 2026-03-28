Updated file with formatted Markdown tables:

````md
# Crouton App Internals

> Reverse-engineered reference for the **Crouton** recipe manager (macOS / iOS).
> Everything here was discovered by inspecting the app binary, its SQLite store,
> entitlements, and file-system artifacts. Use this so you never have to
> re-discover it.

---

## App Overview

| Key                | Value                                       |
| ------------------ | ------------------------------------------- |
| App name           | **Crouton**                                 |
| Bundle ID          | `com.meal.plan.ios`                         |
| Team ID            | `4MQ7FRMKBM`                                |
| macOS install path | `/Applications/Crouton.app`                |
| Sync backend       | CloudKit — container `iCloud.br.com.dinner.plan` |
| App groups         | `group.com.meals.ios`, `group.meal.plan.dev.ios` |

---

## File Locations

| What                   | Path                                                                |
| ---------------------- | ------------------------------------------------------------------- |
| Core Data SQLite store | `~/Library/Group Containers/group.com.meals.ios/Meals.sqlite`       |
| Recipe images (JPEG)   | `~/Library/Group Containers/group.com.meals.ios/MealImages/`        |
| App container          | `~/Library/Containers/com.meal.plan.ios/`                           |
| CloudKit cache DB      | `~/Library/Containers/com.meal.plan.ios/Data/CloudKit/cloudd_db/db` |
| App preferences plist  | `~/Library/Containers/com.meal.plan.ios/Data/Library/Preferences/com.meal.plan.ios.plist` |

### Image Naming Convention

Image files are stored as JPEG in the `MealImages/` directory.
The naming format is:

```text
{recipeUUID}-{randomNumber}
```

For example: `FC4017B5-1A2B-3C4D-5E6F-7890ABCDEF01-48271`

---

## Database Schema (Core Data / SQLite)

The store is a standard Core Data SQLite database. Core Data prefixes every
table with `Z` and tracks entity types in `Z_PRIMARYKEY`.

### Z_PRIMARYKEY — Entity Type IDs

| Z_ENT | Z_NAME               | Description                   |
| ----: | -------------------- | ----------------------------- |
|     1 | CDFeed               | Feed / collection             |
|     2 | CDFeedPost           | Feed posts                    |
|     3 | CDFolder             | Recipe folders                |
|     4 | CDHousehold          | Household sharing             |
|     5 | CDIngredient         | Ingredient names              |
|     6 | CDMeal               | **Recipes**                   |
|     7 | CDMealPlanItem       | Meal plan entries             |
|     8 | CDMealStep           | Recipe steps                  |
|     9 | CDMeasuredIngredient | Ingredients with quantities   |
|    10 | CDTag                | Tags                          |
|    11 | CDTimer              | Cooking timers                |
| 16001 | CHANGE               | CloudKit change tracking      |
| 16002 | TRANSACTION          | CloudKit transaction tracking |
| 16003 | TRANSACTIONSTRING    | Transaction strings           |

---

### ZCDMEAL — Recipes

The main recipes table. Each row is one recipe (`Z_ENT = 6`).

| Column                    | Type    | Notes                                           |
| ------------------------- | ------- | ----------------------------------------------- |
| Z_PK                      | INTEGER | Primary key                                     |
| Z_ENT                     | INTEGER | Always `6`                                      |
| Z_OPT                     | INTEGER | Version / optimistic-lock counter               |
| ZDELETEDFROMDEVICE        | INTEGER | Boolean — soft delete flag                      |
| ZISPUBLICRECIPE           | INTEGER | Boolean                                         |
| ZRATING                   | INTEGER | Star rating                                     |
| ZSERVES                   | INTEGER | Number of servings                              |
| ZTEMPORARY                | INTEGER | Boolean                                         |
| ZUPLOADED                 | INTEGER | Boolean — synced to CloudKit                    |
| ZFEED                     | INTEGER | FK → `ZCDFEED.Z_PK`                             |
| ZCOOKINGDURATION          | FLOAT   | Cook time in **minutes**                        |
| ZDATECREATED              | FLOAT   | Core Data timestamp (seconds since 2001-01-01)  |
| ZDATEMODIFIED             | FLOAT   | Core Data timestamp                             |
| ZDEFAULTSCALE             | FLOAT   | Default ingredient scale multiplier             |
| ZDURATION                 | FLOAT   | Prep time in **minutes**                        |
| ZCREATORID                | VARCHAR | CloudKit creator                                |
| ZDUPLICATEDFROMRECIPEUUID | VARCHAR | Source recipe UUID if duplicated                |
| ZFOLDERIDS                | VARCHAR | Comma-separated folder UUIDs                    |
| ZHEADERIMAGE              | VARCHAR | Image file name                                 |
| ZHOUSEHOLDID              | VARCHAR | Typically empty / NULL                          |
| ZIMAGENAMES               | VARCHAR | Image file name                                 |
| ZMETHOD                   | VARCHAR | Free-form method text                           |
| ZNAME                     | VARCHAR | Recipe title                                    |
| ZNEUTRITIONALINFO         | VARCHAR | Newline-separated `key: value` pairs            |
| ZNOTES                    | VARCHAR | User notes                                      |
| ZRAWDIFFICULTY            | VARCHAR | Difficulty level string                         |
| ZRECORDID                 | VARCHAR | CloudKit record ID (same value as UUID)         |
| ZSHAREDBY                 | VARCHAR | Shared-by attribution                           |
| ZSOURCEIMAGENAME          | VARCHAR | Source/origin image file name                   |
| ZSOURCENAME               | VARCHAR | Source / attribution name                       |
| ZUUID                     | VARCHAR | Recipe UUID                                     |
| ZWEBLINK                  | VARCHAR | Original recipe URL                             |
| ZRECORDDATA               | BLOB    | Serialized CloudKit metadata                    |

---

### ZCDMEALSTEP — Recipe Steps

| Column      | Type    | Notes                                                  |
| ----------- | ------- | ------------------------------------------------------ |
| Z_PK        | INTEGER | Primary key                                            |
| Z_ENT       | INTEGER | Always `8`                                             |
| Z_OPT       | INTEGER | Version counter                                        |
| ZISSECTION  | INTEGER | Boolean — `1` = section header, `0` = regular step     |
| ZORDER      | INTEGER | Display order (0-based)                                |
| ZMEAL       | INTEGER | FK → `ZCDMEAL.Z_PK`                                    |
| ZCREATORID  | VARCHAR |                                                        |
| ZRECORDID   | VARCHAR |                                                        |
| ZSTEP       | VARCHAR | Step text                                              |
| ZUUID       | VARCHAR |                                                        |
| ZRECORDDATA | BLOB    |                                                        |

---

### ZCDMEASUREDINGREDIENT — Recipe Ingredients

| Column           | Type    | Notes                                       |
| ---------------- | ------- | ------------------------------------------- |
| Z_PK             | INTEGER | Primary key                                 |
| Z_ENT            | INTEGER | Always `9`                                  |
| Z_OPT            | INTEGER | Version counter                             |
| ZINGREDIENT      | INTEGER | FK → `ZCDINGREDIENT.Z_PK`                   |
| ZMEAL            | INTEGER | FK → `ZCDMEAL.Z_PK`                         |
| ZAMOUNT          | FLOAT   | Primary quantity                            |
| ZORDER           | FLOAT   | Display order                               |
| ZSECONDARYAMOUNT | FLOAT   | Secondary quantity (e.g. range end)         |
| ZCREATORID       | VARCHAR |                                             |
| ZQUANTITYTYPE    | VARCHAR | Unit — see [Quantity Types](#quantity-types) |
| ZRECORDID        | VARCHAR |                                             |
| ZUUID            | VARCHAR |                                             |
| ZRECORDDATA      | BLOB    |                                             |

---

### ZCDINGREDIENT — Ingredient Names

| Column      | Type    | Notes                   |
| ----------- | ------- | ----------------------- |
| Z_PK        | INTEGER | Primary key             |
| Z_ENT       | INTEGER | Always `5`              |
| Z_OPT       | INTEGER |                         |
| ZCREATORID  | VARCHAR |                         |
| ZNAME       | VARCHAR | Ingredient display name |
| ZRECORDID   | VARCHAR |                         |
| ZUUID       | VARCHAR |                         |
| ZRECORDDATA | BLOB    |                         |

---

### ZCDTAG — Tags

| Column             | Type    | Notes       |
| ------------------ | ------- | ----------- |
| Z_PK               | INTEGER | Primary key |
| Z_ENT              | INTEGER | Always `10` |
| Z_OPT              | INTEGER |             |
| ZDELETEDFROMDEVICE | INTEGER |             |
| ZUPLOADED          | INTEGER |             |
| ZCOLOR             | VARCHAR |             |
| ZCREATORID         | VARCHAR |             |
| ZHOUSEHOLDID       | VARCHAR |             |
| ZNAME              | VARCHAR | Tag name    |
| ZRECORDID          | VARCHAR |             |
| ZUUID              | VARCHAR |             |
| ZRECORDDATA        | BLOB    |             |

---

### ZCDFOLDER — Folders

| Column             | Type    | Notes       |
| ------------------ | ------- | ----------- |
| Z_PK               | INTEGER | Primary key |
| Z_ENT              | INTEGER | Always `3`  |
| Z_OPT              | INTEGER |             |
| ZDELETEDFROMDEVICE | INTEGER |             |
| ZINCLUSIVE         | INTEGER |             |
| ZUPLOADED          | INTEGER |             |
| ZCREATORID         | VARCHAR |             |
| ZHOUSEHOLDID       | VARCHAR |             |
| ZNAME              | VARCHAR | Folder name |
| ZRECORDID          | VARCHAR |             |
| ZUUID              | VARCHAR |             |
| ZRECORDDATA        | BLOB    |             |

---

### Join Tables

| Table           | Column A                        | Column B                     | Relationship       |
| --------------- | ------------------------------- | ---------------------------- | ------------------ |
| `Z_6TAGS`       | `Z_6RECIPES` → `ZCDMEAL.Z_PK`   | `Z_10TAGS1` → `ZCDTAG.Z_PK`  | Recipe ↔ Tag       |
| `Z_3TAGS`       | `Z_3FOLDERS` → `ZCDFOLDER.Z_PK` | `Z_10TAGS` → `ZCDTAG.Z_PK`   | Folder ↔ Tag       |
| `Z_6MEALPLANS`  | `Z_6MEALS`                      | `Z_7MEALPLANS`               | Recipe ↔ Meal Plan |

---

### CloudKit Sync Tables

These tables are managed by `NSPersistentCloudKitContainer` for change tracking.

#### ACHANGE

| Column         | Type    | Notes                               |
| -------------- | ------- | ----------------------------------- |
| Z_PK           | INTEGER | Primary key                         |
| ZCHANGETYPE    | INTEGER | `0` = insert, `2` = update          |
| ZENTITY        | INTEGER | Entity type ID (from `Z_PRIMARYKEY`) |
| ZENTITYPK      | INTEGER | PK of the changed entity            |
| ZTRANSACTIONID | INTEGER | FK → `ATRANSACTION.Z_PK`            |
| ZCOLUMNS       | BLOB    | Changed columns                     |

#### ATRANSACTION

| Column       | Type    | Notes                 |
| ------------ | ------- | --------------------- |
| Z_PK         | INTEGER | Primary key           |
| ZTIMESTAMP   | FLOAT   | Transaction timestamp |
| ZAUTHOR      | VARCHAR |                       |
| ZBUNDLEID    | VARCHAR |                       |
| ZCONTEXTNAME | VARCHAR |                       |
| ZPROCESSID   | VARCHAR |                       |
| ZQUERYGEN    | INTEGER |                       |

#### ATRANSACTIONSTRING

| Column | Type    | Notes       |
| ------ | ------- | ----------- |
| Z_PK   | INTEGER | Primary key |
| ZNAME  | VARCHAR |             |

---

## Quantity Types

There are **17 known** quantity type strings used in `ZQUANTITYTYPE`:

| Type       | Type     | Type    |
| ---------- | -------- | ------- |
| BOTTLE     | BUNCH    | CAN     |
| CENTILITER | CUP      | GRAMS   |
| ITEM       | KGS      | LITRES  |
| MILLS      | OUNCE    | PACKET  |
| PINCH      | POUND    | SECTION |
| TABLESPOON | TEASPOON |         |

---

## .crumb File Format

Crouton uses `.crumb` files for recipe import/export.

| Property       | Value                                                   |
| -------------- | ------------------------------------------------------- |
| Extension      | `.crumb`                                                |
| UTI            | `com.meal.plan.ios.crumb` (conforms to `public.text`)   |
| Content type   | **JSON**                                                |
| Import command | `open -a Crouton file.crumb`                            |
| URL scheme     | `crouton://viewRecipe?id={uuid}`                        |

### JSON Schema

```json
{
  "uuid": "FC4017B5-...",
  "name": "Chicken Piccata",
  "steps": [
    {
      "order": 0,
      "step": "Step text...",
      "isSection": false,
      "uuid": "A69FD909-..."
    }
  ],
  "ingredients": [
    {
      "ingredient": {
        "name": "chicken cutlets",
        "uuid": "9DC4CEE0-..."
      },
      "quantity": {
        "quantityType": "POUND",
        "amount": 2
      },
      "uuid": "CB5FC070-...",
      "order": 0
    }
  ],
  "images": ["base64-encoded-jpeg..."],
  "sourceImage": "base64-encoded-jpeg...",
  "webLink": "https://...",
  "sourceName": "The Modern Proper",
  "duration": 10,
  "cookingDuration": 30,
  "serves": 6,
  "defaultScale": 1,
  "tags": [],
  "folderIDs": [],
  "isPublicRecipe": false,
  "neutritionalInfo": "Sugar: 2g\nCalories: 457"
}
```

---

## Writing to the Database

When inserting records directly into `Meals.sqlite`, follow these steps to keep
Core Data and CloudKit happy:

1. **Set `Z_ENT`** correctly for every row (see the entity ID table above).
2. **Set `Z_OPT = 1`** for new records.
3. **Update `Z_PRIMARYKEY.Z_MAX`** for each entity type you inserted into — Core
   Data uses this to allocate the next primary key.
4. **Insert an `ACHANGE` record** with `ZCHANGETYPE = 0` (insert), referencing
   the new entity's PK and a transaction ID.
5. **Insert an `ATRANSACTION` record** with the current timestamp.
6. **`ZRECORDDATA` and `ZRECORDID` can be `NULL`** — CloudKit will populate them
   on the next sync cycle.
7. **`ZHOUSEHOLDID`** is empty or `NULL` for all single-user recipes.
8. **Place image files** in `MealImages/` using the naming format
   `{recipeUUID}-{randomNumber}`.
9. **Quit and relaunch Crouton** after any direct database changes so the app
   picks up the modifications and triggers CloudKit sync.

---

## CloudKit Details

| Property           | Value                                                         |
| ------------------ | ------------------------------------------------------------- |
| Container ID       | `iCloud.br.com.dinner.plan`                                   |
| Sync framework     | `NSPersistentCloudKitContainer` (Core Data ↔ CloudKit auto-sync) |
| Record type prefix | `CD_` (e.g. recipes → `CD_CDMeal`)                            |
| Required signing   | Developer certificate for team `4MQ7FRMKBM`                   |

> **Note:** Direct CloudKit API access requires the original developer's signing
> certificate. Ad-hoc signed binaries are killed by macOS security
> (`amfid` / Gatekeeper) when they attempt to access the container.

---

## App Entitlements

```xml
<!-- iCloud -->
com.apple.developer.icloud-container-identifiers
  → ["iCloud.br.com.dinner.plan"]

com.apple.developer.icloud-services
  → ["CloudKit"]

<!-- App Groups -->
com.apple.security.application-groups
  → ["group.com.meals.ios", "group.meal.plan.dev.ios"]

<!-- KVS -->
com.apple.developer.ubiquity-kvstore-identifier
  → EB8VPKS2W5.com.meal.plan.ios

<!-- Associated Domains -->
com.apple.developer.associated-domains
  → webcredentials:account.crouton.app
  → applinks:recipes.crouton.app
```

---

## Internal App Classes (from binary strings)

These class names were extracted from the Crouton binary and reveal internal
architecture:

| Category             | Classes                                                                          |
| -------------------- | -------------------------------------------------------------------------------- |
| **Import**           | `DataImporter`, `ShareImportHandler`, `SmartImporter`                            |
| **Export**           | `ExportHelper`, `RecipeExportHandler`, `PDFExportHandler`, `ExportPreferences`   |
| **CloudKit**         | `CloudKitHelper`                                                                 |
| **Classification**   | `RecipeClassifier`, `RecipeTagger`                                               |
| **AI**               | `OpenAlConnector` (OpenAI integration)                                           |
````

If wanted, I can also collapse overly wide tables for better preview in VS Code.
