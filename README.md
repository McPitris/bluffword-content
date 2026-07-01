# bluffword-content

Static content for BluffWord remote updates.

Published by GitHub Pages. The app reads `manifest.json`, downloads changed files, validates them, and keeps the last valid local content.

## Structure

```text
manifest.json
cs/categories.json
en/categories.json
assets/categories/*.png
scripts/generate_manifest.py
.github/workflows/update-manifest.yml
```

## Updating content

1. Edit `cs/categories.json` and `en/categories.json`.
2. Add or replace category images in `assets/categories/`.
3. Keep category `id` stable across locales.
4. Keep `imagePath` the same in both locale files, for example `assets/categories/food.png`.
5. Push changes to `master`.
6. GitHub Actions regenerates `manifest.json`, bumps `contentVersion`, and commits the manifest.
7. GitHub Pages publishes static files.

## Generate manifest locally

Regenerate hashes without changing the current version:

```bash
python3 scripts/generate_manifest.py
```

Bump the version manually:

```bash
python3 scripts/generate_manifest.py --bump
```

Set an explicit version:

```bash
python3 scripts/generate_manifest.py --version 3
```

## Pages URL

```text
https://mcpitris.github.io/bluffword-content/manifest.json
```
