# bluffword-content

Static content for BluffWord remote updates.

Published by GitHub Pages. The app reads `manifest_index.json`, picks the newest manifest compatible with the current app version, downloads changed files, validates them, and keeps the last valid local content. Older app versions fall back to the newest release whose `minimumAppVersion` they support.

## Structure

```text
manifest.json
manifest_index.json
content_config.json
cs/categories.json
en/categories.json
assets/categories/*.png
assets/themes/<theme-id>/categories/*.png
assets/themes/<theme-id>/avatars/*.png
releases/e<epoch>/v<version>/manifest.json
releases/e<epoch>/v<version>/cs/categories.json
releases/e<epoch>/v<version>/en/categories.json
releases/e<epoch>/v<version>/assets/**
scripts/generate_manifest.py
.github/workflows/update-manifest.yml
```

## Updating content

1. Edit `cs/categories.json` and `en/categories.json`.
2. Add or replace category images in `assets/categories/` when needed.
3. Add optional theme overrides in `assets/themes/<theme-id>/`.
4. Keep category `id` stable across locales.
5. Keep `imagePath` the same in both locale files, for example `assets/categories/food.png`.
6. If the content needs a newer app, update `minimumAppVersion` in `content_config.json`.
7. Push changes to `master`.
8. GitHub Actions regenerates category `version`, `manifest.json`, `manifest_index.json`, and a release snapshot under `releases/e<epoch>/v<version>/`.
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
- push to `master`; GitHub Actions updates the generated files

## Generate manifest locally

Regenerate category `version`, hashes, `manifest.contentVersion`, `manifest_index.json`, and the immutable release snapshot from `cs/categories.json`, `en/categories.json`, and assets:

```bash
python3 scripts/generate_manifest.py
```

Override `minimumAppVersion` for local testing when needed:

```bash
python3 scripts/generate_manifest.py --min-app-version 0.8.0
```

Reset content version numbering with a new epoch:

```bash
python3 scripts/generate_manifest.py --content-epoch 2
```

## Pages URL

```text
https://mcpitris.github.io/bluffword-content/manifest.json
https://mcpitris.github.io/bluffword-content/manifest_index.json
```

## Version fields

`content_config.json` stores release-level settings:

```json
{
  "minimumAppVersion": "1.0.0",
  "contentEpoch": 1,
  "legacyManifestAppVersion": "1.0.0"
}
```

`cs/categories.json` and `en/categories.json` keep a generated `version` field for the app validator. Do not bump it by hand. The generator compares current source files with the latest manifest and increments `manifest.contentVersion` when content or `minimumAppVersion` changed.

The app displays `manifest.contentVersion`. It is always a whole number: `2`, `3`, `4`...

`manifest.contentEpoch` lets you restart content version numbering. The app compares `contentEpoch` first, then `contentVersion`. If published content should start again from version `1`, increase `contentEpoch` in `content_config.json`.

`minimumAppVersion` is read from `content_config.json` unless you pass `--min-app-version` locally. The app uses `manifest_index.json` to choose the newest release where `minimumAppVersion` is less than or equal to the current app version. For example, app `1.0.0` will skip a release with `minimumAppVersion: "1.0.1"` and use the newest release still marked for `1.0.0`.

The root `manifest.json` is kept for older app builds that do not know `manifest_index.json`. It points to the newest release compatible with `legacyManifestAppVersion`. New app builds use `manifest_index.json`. Older compatible releases must remain available under `releases/e<epoch>/v<version>/`, because archived manifests point at those immutable release files instead of the mutable top-level `cs/`, `en/`, and `assets/` files.
