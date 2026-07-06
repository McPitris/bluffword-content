# bluffword-content

Static content for BluffWord remote updates.

Published by GitHub Pages. The app reads `manifest.json`, downloads changed files, validates them, and keeps the last valid local content.

## Structure

```text
manifest.json
cs/categories.json
en/categories.json
assets/categories/*.png
assets/themes/<theme-id>/categories/*.png
assets/themes/<theme-id>/avatars/*.png
scripts/generate_manifest.py
.github/workflows/update-manifest.yml
```

## Updating content

1. Edit `cs/categories.json` and `en/categories.json`.
2. Increase `version` in both category JSON files to the same whole number.
3. Add or replace category images in `assets/categories/` when needed.
4. Add optional theme overrides in `assets/themes/<theme-id>/`.
5. Keep category `id` stable across locales.
6. Keep `imagePath` the same in both locale files, for example `assets/categories/food.png`.
7. Push changes to `master`.
8. GitHub Actions regenerates `manifest.json` from the category JSON version, hashes, and file sizes.
9. GitHub Pages publishes static files.

## Theme images

Theme ids must match app ids. Current ids:

- `lotr`

Category override files use the category id:

```text
assets/themes/lotr/categories/food.png
assets/themes/lotr/categories/movies.png
```

Avatar override files use the bundled avatar file name:

```text
assets/themes/lotr/avatars/user_1.png
assets/themes/lotr/avatars/user_2.png
```

If a theme image is missing, the app falls back to the default image.

## Special categories

Special categories are hidden by default in the app. The user can enable them in:

```text
Nastavení -> Speciální kategorie
```

Mark a category as special with:

```json
{
  "id": "lotr",
  "name": "Pán prstenů",
  "description": "Pán prstenů a Hobit.",
  "imagePath": "assets/categories/lotr.png",
  "isSpecial": true,
  "words": []
}
```

Rules:

- keep the same `id` and `isSpecial` value in `cs/categories.json` and `en/categories.json`
- add the image to `assets/categories/lotr.png`
- increase `version` in both locale files
- regenerate `manifest.json`

## Generate manifest locally

Regenerate hashes and `manifest.contentVersion` from `cs/categories.json` and `en/categories.json`:

```bash
python3 scripts/generate_manifest.py
```

Override `minimumAppVersion` when needed:

```bash
python3 scripts/generate_manifest.py --min-app-version 0.8.0
```

## Pages URL

```text
https://mcpitris.github.io/bluffword-content/manifest.json
```

## Version fields

`cs/categories.json` and `en/categories.json` are the source of truth. Their `version` must match and must be a non-negative integer. The generator copies that value into `manifest.contentVersion`.

The app displays `manifest.contentVersion`. Use `2`, `3`, `4`... for content releases, not `1.1`, because the manifest model in the app expects an integer. If content files change and the version stays the same, the generator fails so the app cannot miss the update.

`minimumAppVersion` is kept from the existing manifest unless you pass `--min-app-version`. The current app treats it as manifest metadata; enforcement must be added in the app if a future content schema requires a newer app.
