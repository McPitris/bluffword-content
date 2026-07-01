#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://mcpitris.github.io/bluffword-content"
SCHEMA_VERSION = 1
DEFAULT_MIN_APP_VERSION = "0.7.0"

CONTENT_TYPES = {
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

FILES = [
    "cs/categories.json",
    "en/categories.json",
]

ASSET_DIRS = [
    "assets/categories",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_type_for(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def file_id_for(path: str) -> str:
    if path == "cs/categories.json":
        return "categories-cs"
    if path == "en/categories.json":
        return "categories-en"
    if path.startswith("assets/categories/"):
        return f"category-{Path(path).stem}-image"
    return path.replace("/", "-").replace(".", "-")


def current_manifest(root: Path) -> dict:
    path = root / "manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def collected_paths(root: Path) -> list[str]:
    paths = list(FILES)
    for asset_dir in ASSET_DIRS:
        directory = root / asset_dir
        if not directory.exists():
            continue
        for file in sorted(directory.iterdir()):
            if file.is_file():
                paths.append(file.relative_to(root).as_posix())
    return paths


def read_category_files(root: Path) -> dict[str, dict]:
    categories_by_locale = {}
    for locale in ("cs", "en"):
        path = root / locale / "categories.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("locale") != locale:
            raise ValueError(f"{locale}/categories.json has invalid locale")
        categories = data.get("categories")
        if not isinstance(categories, list) or not categories:
            raise ValueError(f"{locale}/categories.json must contain categories")
        categories_by_locale[locale] = data
    return categories_by_locale


def content_version_from_categories(categories_by_locale: dict[str, dict]) -> int:
    versions = {locale: data.get("version") for locale, data in categories_by_locale.items()}
    if versions["cs"] != versions["en"]:
        raise ValueError("cs/categories.json and en/categories.json must have the same version")

    version = versions["cs"]
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        raise ValueError(
            "Category version must be the same non-negative integer in cs/categories.json and en/categories.json"
        )
    return version


def minimum_app_version(existing_manifest: dict, value: str | None) -> str:
    return value or existing_manifest.get("minimumAppVersion") or DEFAULT_MIN_APP_VERSION


def validate_content_files(root: Path, paths: list[str], categories_by_locale: dict[str, dict]) -> None:
    for path in paths:
        if not (root / path).exists():
            raise FileNotFoundError(f"Missing file: {path}")

    cs_categories = categories_by_locale["cs"]["categories"]
    en_categories = categories_by_locale["en"]["categories"]
    cs_ids = [category.get("id") for category in cs_categories]
    en_ids = [category.get("id") for category in en_categories]
    if cs_ids != en_ids:
        raise ValueError("CS and EN category ids must match in the same order")

    for category in cs_categories + en_categories:
        image_path = category.get("imagePath")
        if image_path and not (root / image_path).exists():
            raise FileNotFoundError(f"Missing category image: {image_path}")


def build_manifest(root: Path, args: argparse.Namespace) -> dict:
    existing = current_manifest(root)
    categories_by_locale = read_category_files(root)
    content_version = content_version_from_categories(categories_by_locale)
    paths = collected_paths(root)
    validate_content_files(root, paths, categories_by_locale)

    files = []
    for path_str in paths:
        path = root / path_str
        files.append(
            {
                "id": file_id_for(path_str),
                "path": path_str,
                "url": f"{BASE_URL}/{path_str}",
                "sha256": sha256_file(path),
                "contentType": content_type_for(path),
                "sizeBytes": path.stat().st_size,
            }
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "contentVersion": content_version,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minimumAppVersion": minimum_app_version(existing, args.min_app_version),
        "files": files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate BluffWord remote content manifest.")
    parser.add_argument(
        "--min-app-version",
        help="Override minimumAppVersion. Without this, the existing manifest value is kept.",
    )
    args = parser.parse_args()

    root = Path.cwd()
    manifest = build_manifest(root, args)
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated manifest.json with contentVersion {manifest['contentVersion']}")


if __name__ == "__main__":
    main()
