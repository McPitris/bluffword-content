#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://mcpitris.github.io/bluffword-content"
SCHEMA_VERSION = 1
DEFAULT_CONTENT_VERSION = 1
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


def next_content_version(manifest: dict, args: argparse.Namespace) -> int:
    if args.version is not None:
        return args.version
    current = manifest.get("contentVersion", DEFAULT_CONTENT_VERSION)
    if args.bump:
        return current + 1
    return current


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


def validate_content_files(root: Path, paths: list[str]) -> None:
    for path in paths:
        if not (root / path).exists():
            raise FileNotFoundError(f"Missing file: {path}")

    categories_by_locale = {}
    for locale in ("cs", "en"):
        data = json.loads((root / locale / "categories.json").read_text(encoding="utf-8"))
        if data.get("locale") != locale:
            raise ValueError(f"{locale}/categories.json has invalid locale")
        categories = data.get("categories")
        if not isinstance(categories, list) or not categories:
            raise ValueError(f"{locale}/categories.json must contain categories")
        categories_by_locale[locale] = categories

    cs_ids = [category.get("id") for category in categories_by_locale["cs"]]
    en_ids = [category.get("id") for category in categories_by_locale["en"]]
    if cs_ids != en_ids:
        raise ValueError("CS and EN category ids must match in the same order")

    for category in categories_by_locale["cs"] + categories_by_locale["en"]:
        image_path = category.get("imagePath")
        if image_path and not (root / image_path).exists():
            raise FileNotFoundError(f"Missing category image: {image_path}")


def build_manifest(root: Path, args: argparse.Namespace) -> dict:
    existing = current_manifest(root)
    paths = collected_paths(root)
    validate_content_files(root, paths)

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
        "contentVersion": next_content_version(existing, args),
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minimumAppVersion": args.min_app_version,
        "files": files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate BluffWord remote content manifest.")
    parser.add_argument("--version", type=int, help="Set an explicit contentVersion.")
    parser.add_argument("--bump", action="store_true", help="Increment contentVersion from manifest.json.")
    parser.add_argument("--min-app-version", default=DEFAULT_MIN_APP_VERSION)
    args = parser.parse_args()

    if args.version is not None and args.version < 0:
        parser.error("--version must be non-negative")

    root = Path.cwd()
    manifest = build_manifest(root, args)
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated manifest.json with contentVersion {manifest['contentVersion']}")


if __name__ == "__main__":
    main()
