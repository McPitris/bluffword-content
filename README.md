# bluffword-content

Static content for BluffWord remote updates.

Published by GitHub Pages. The app reads `manifest.json`, downloads changed files, validates them, and keeps the last valid local content.

## Structure

```text
manifest.json
cs/categories.json
en/categories.json
assets/categories/*.png
```

## Updating content

1. Edit `cs/categories.json` and `en/categories.json`.
2. Add or replace category images in `assets/categories/`.
3. Keep category `id` stable across locales.
4. Keep `imagePath` the same in both locale files, for example `assets/categories/food.png`.
5. Increase `contentVersion` in `manifest.json`.
6. Update each changed file `sha256` and `sizeBytes` in `manifest.json`.
7. Push changes. GitHub Pages will publish static files.

## Pages URL

```text
https://mcpitris.github.io/bluffword-content/manifest.json
```
