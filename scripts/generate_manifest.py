#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://mcpitris.github.io/bluffword-content"
SCHEMA_VERSION = 1
DEFAULT_MIN_APP_VERSION = "0.9.0"
DEFAULT_CONTENT_EPOCH = 1

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
    "assets/themes",
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
    if path.startswith("assets/themes/"):
        parts = Path(path).parts
        if len(parts) >= 5 and parts[3] == "categories":
            return f"theme-{parts[2]}-category-{Path(path).stem}-image"
        if len(parts) >= 5 and parts[3] == "avatars":
            return f"theme-{parts[2]}-avatar-{Path(path).stem}-image"
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
        for file in sorted(directory.rglob("*")):
            if file.is_file() and not file.name.startswith("."):
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


def content_epoch(existing_manifest: dict, value: int | None) -> int:
    epoch = value or existing_manifest.get("contentEpoch") or DEFAULT_CONTENT_EPOCH
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch <= 0:
        raise ValueError("contentEpoch must be a positive integer")
    return epoch


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

    for cs_category, en_category in zip(cs_categories, en_categories):
        if bool(cs_category.get("isSpecial", False)) != bool(en_category.get("isSpecial", False)):
            raise ValueError(
                f"CS and EN category isSpecial must match for {cs_category.get('id')}"
            )

    for category in cs_categories + en_categories:
        is_special = category.get("isSpecial")
        if is_special is not None and not isinstance(is_special, bool):
            raise ValueError(f"Category isSpecial must be boolean: {category.get('id')}")
        image_path = category.get("imagePath")
        if image_path and not (root / image_path).exists():
            raise FileNotFoundError(f"Missing category image: {image_path}")

    category_ids = set(cs_ids)
    for path in paths:
        parts = Path(path).parts
        if len(parts) >= 5 and parts[0:2] == ("assets", "themes") and parts[3] == "categories":
            category_id = Path(path).stem
            if category_id not in category_ids:
                raise ValueError(f"Theme category image has no matching category id: {path}")


def manifest_file_entry(root: Path, path_str: str) -> dict:
    path = root / path_str
    return {
        "id": file_id_for(path_str),
        "path": path_str,
        "url": f"{BASE_URL}/{path_str}",
        "sha256": sha256_file(path),
        "contentType": content_type_for(path),
        "sizeBytes": path.stat().st_size,
    }


def validate_version_bump(
    existing_manifest: dict,
    content_epoch: int,
    content_version: int,
    files: list[dict],
) -> None:
    if existing_manifest.get("contentEpoch", DEFAULT_CONTENT_EPOCH) != content_epoch:
        return
    if existing_manifest.get("contentVersion") != content_version:
        return

    existing_files = {file.get("path"): file for file in existing_manifest.get("files", [])}
    changed_paths = []
    for file in files:
        existing = existing_files.get(file["path"])
        if (
            existing is None
            or existing.get("sha256") != file["sha256"]
            or existing.get("sizeBytes") != file["sizeBytes"]
        ):
            changed_paths.append(file["path"])

    if changed_paths:
        changed = ", ".join(changed_paths)
        raise ValueError(
            f"Content changed but version is still {content_version}. "
            "Increase version in both cs/categories.json and en/categories.json. "
            f"Changed files: {changed}"
        )


def build_manifest(root: Path, args: argparse.Namespace) -> dict:
    existing = current_manifest(root)
    categories_by_locale = read_category_files(root)
    epoch = content_epoch(existing, args.content_epoch)
    content_version = content_version_from_categories(categories_by_locale)
    paths = collected_paths(root)
    validate_content_files(root, paths, categories_by_locale)

    files = [manifest_file_entry(root, path_str) for path_str in paths]
    validate_version_bump(existing, epoch, content_version, files)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "contentEpoch": epoch,
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
    parser.add_argument(
        "--content-epoch",
        type=int,
        help="Override contentEpoch. Increase this when contentVersion should restart from 1.",
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
