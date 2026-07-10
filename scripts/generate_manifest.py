#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://mcpitris.github.io/bluffword-content"
SCHEMA_VERSION = 1
DEFAULT_MIN_APP_VERSION = "1.0.0"
DEFAULT_CONTENT_EPOCH = 1
CONFIG_FILE = "content_config.json"
RELEASES_DIR = "releases"
DEFAULT_LEGACY_MANIFEST_APP_VERSION = "1.0.0"

CONTENT_TYPES = {
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

FILES = [
    "themes.json",
    "cs/categories.json",
    "en/categories.json",
]

ASSET_DIRS = [
    "assets/categories",
    "assets/themes",
]

THEME_COLOR_KEYS = {
    "backgroundTop",
    "backgroundBottom",
    "darkBackground",
    "darkSurface",
    "darkSurfacePressed",
    "darkOverlaySoft",
    "darkOverlayStrong",
    "primary",
    "primaryDark",
    "primaryLight",
    "primarySoft",
    "secondaryButtonFill",
    "accent",
    "textPrimary",
    "textSecondary",
    "textMuted",
    "disabledFill",
    "disabledText",
    "gridLine",
    "shadow",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_type_for(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def file_id_for(path: str) -> str:
    if path == "themes.json":
        return "themes-catalog"
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


def release_manifests(root: Path) -> list[tuple[dict, Path]]:
    manifests = []
    for path in sorted((root / RELEASES_DIR).glob("e*/v*/manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifests.append((manifest, path.relative_to(root)))

    return sorted(
        manifests,
        key=lambda entry: (
            entry[0].get("contentEpoch", DEFAULT_CONTENT_EPOCH),
            entry[0].get("contentVersion", 0),
        ),
        reverse=True,
    )


def current_manifest(root: Path) -> dict:
    manifests = release_manifests(root)
    if manifests:
        return manifests[0][0]

    path = root / "manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def content_config(root: Path) -> dict:
    path = root / CONFIG_FILE
    if not path.exists():
        return {}
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"{CONFIG_FILE} must contain an object")
    return config


def legacy_manifest_app_version(config: dict) -> str:
    configured = config.get("legacyManifestAppVersion")
    if configured is not None and not isinstance(configured, str):
        raise ValueError("content_config.legacyManifestAppVersion must be a string")
    return configured or DEFAULT_LEGACY_MANIFEST_APP_VERSION


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


def read_theme_catalog(root: Path) -> dict:
    path = root / "themes.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != 1:
        raise ValueError("themes.schemaVersion must be 1")
    themes = data.get("themes")
    if not isinstance(themes, list) or not themes:
        raise ValueError("themes must contain at least one theme")

    theme_ids = set()
    for theme in themes:
        if not isinstance(theme, dict):
            raise ValueError("Each theme must be an object")
        theme_id = theme.get("id")
        if (
            not isinstance(theme_id, str)
            or re.fullmatch(r"[a-z0-9][a-z0-9_-]*", theme_id) is None
        ):
            raise ValueError(f"Invalid theme id: {theme_id}")
        if theme_id in theme_ids:
            raise ValueError(f"Duplicate theme id: {theme_id}")
        theme_ids.add(theme_id)

        names = theme.get("names")
        if not isinstance(names, dict) or not names:
            raise ValueError(f"theme.names must not be empty: {theme_id}")
        if any(
            not isinstance(value, str) or not value
            for value in names.values()
        ):
            raise ValueError(f"theme.names values must be strings: {theme_id}")

        icon = theme.get("icon")
        if icon is not None and (not isinstance(icon, str) or not icon):
            raise ValueError(f"theme.icon must be a non-empty string: {theme_id}")

        colors = theme.get("colors")
        if not isinstance(colors, dict) or set(colors) != THEME_COLOR_KEYS:
            raise ValueError(f"theme.colors has invalid keys: {theme_id}")
        for key, value in colors.items():
            if (
                not isinstance(value, str)
                or not value.startswith("#")
                or len(value) not in (7, 9)
                or any(
                    character not in "0123456789abcdefABCDEF"
                    for character in value[1:]
                )
            ):
                raise ValueError(f"Invalid theme color {theme_id}.{key}: {value}")

        asset_path = theme.get("assetPath")
        if asset_path is not None:
            if (
                not isinstance(asset_path, str)
                or not asset_path
                or asset_path.startswith("/")
                or ".." in Path(asset_path).parts
            ):
                raise ValueError(f"Invalid theme assetPath: {theme_id}")
            if not (root / asset_path).is_dir():
                raise FileNotFoundError(f"Missing theme asset directory: {asset_path}")

    if "classic" not in theme_ids:
        raise ValueError("themes must contain the classic fallback theme")
    return data


def category_version(categories_by_locale: dict[str, dict]) -> int:
    versions = {locale: data.get("version") for locale, data in categories_by_locale.items()}
    if versions["cs"] != versions["en"]:
        raise ValueError("cs/categories.json and en/categories.json must have the same version")

    version = versions["cs"]
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        raise ValueError(
            "Category version must be the same non-negative integer in cs/categories.json and en/categories.json"
        )
    return version


def minimum_app_version(
    existing_manifest: dict,
    config: dict,
    value: str | None,
) -> str:
    configured = config.get("minimumAppVersion")
    if configured is not None and not isinstance(configured, str):
        raise ValueError("content_config.minimumAppVersion must be a string")
    return value or configured or existing_manifest.get("minimumAppVersion") or DEFAULT_MIN_APP_VERSION


def content_epoch(existing_manifest: dict, config: dict, value: int | None) -> int:
    configured = config.get("contentEpoch")
    if configured is not None and (isinstance(configured, bool) or not isinstance(configured, int)):
        raise ValueError("content_config.contentEpoch must be an integer")
    epoch = value or configured or existing_manifest.get("contentEpoch") or DEFAULT_CONTENT_EPOCH
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch <= 0:
        raise ValueError("contentEpoch must be a positive integer")
    return epoch


def parse_app_version(version: str) -> tuple[int, int, int]:
    parts = version.split("+", 1)[0].split("-", 1)[0].split(".")
    if not parts or len(parts) > 3:
        raise ValueError(f"Invalid app version: {version}")

    parsed = []
    for part in parts:
        if not part.isdigit():
            raise ValueError(f"Invalid app version: {version}")
        parsed.append(int(part))
    while len(parsed) < 3:
        parsed.append(0)

    return tuple(parsed)


def is_app_version_compatible(app_version: str, minimum_app_version: str) -> bool:
    return parse_app_version(app_version) >= parse_app_version(minimum_app_version)


def write_category_versions(root: Path, categories_by_locale: dict[str, dict], version: int) -> None:
    for locale, data in categories_by_locale.items():
        data["version"] = version
        path = root / locale / "categories.json"
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def source_file_entries(root: Path, paths: list[str]) -> list[dict]:
    entries = []
    for path_str in paths:
        path = root / path_str
        entries.append(
            {
                "path": path_str,
                "sha256": sha256_file(path),
                "sizeBytes": path.stat().st_size,
            }
        )
    return entries


def source_changed(existing_manifest: dict, content_epoch: int, source_files: list[dict]) -> bool:
    if not existing_manifest:
        return True
    if existing_manifest.get("contentEpoch", DEFAULT_CONTENT_EPOCH) != content_epoch:
        return True

    existing_files = {file.get("path"): file for file in existing_manifest.get("files", [])}
    for file in source_files:
        existing = existing_files.get(file["path"])
        if (
            existing is None
            or existing.get("sha256") != file["sha256"]
            or existing.get("sizeBytes") != file["sizeBytes"]
        ):
            return True

    return False


def next_content_version(
    existing_manifest: dict,
    categories_by_locale: dict[str, dict],
    content_epoch: int,
    source_files: list[dict],
    min_app_version: str,
) -> int:
    existing_version = existing_manifest.get("contentVersion")
    if isinstance(existing_version, bool) or not isinstance(existing_version, int):
        return category_version(categories_by_locale)

    existing_min_app_version = existing_manifest.get("minimumAppVersion")
    if (
        source_changed(existing_manifest, content_epoch, source_files)
        or existing_min_app_version != min_app_version
    ):
        if existing_manifest.get("contentEpoch", DEFAULT_CONTENT_EPOCH) != content_epoch:
            return 1
        return existing_version + 1

    return existing_version


def validate_content_files(
    root: Path,
    paths: list[str],
    categories_by_locale: dict[str, dict],
    theme_catalog: dict,
) -> None:
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
        cs_word_ids = [word.get("id") for word in cs_category.get("words", [])]
        en_word_ids = [word.get("id") for word in en_category.get("words", [])]
        if cs_word_ids != en_word_ids:
            raise ValueError(
                f"CS and EN word ids must match for category {cs_category.get('id')}"
            )

    for locale, categories in (("cs", cs_categories), ("en", en_categories)):
        word_category_by_id = {}
        for category in categories:
            for word in category.get("words", []):
                word_id = word.get("id")
                if word_id in word_category_by_id:
                    raise ValueError(
                        f"Duplicate word id in {locale}: {word_id} "
                        f"({word_category_by_id[word_id]} and {category.get('id')})"
                    )
                word_category_by_id[word_id] = category.get("id")

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

    collected_path_set = set(paths)
    for theme in theme_catalog["themes"]:
        asset_path = theme.get("assetPath")
        if asset_path and not any(
            path.startswith(f"{asset_path}/") for path in collected_path_set
        ):
            raise ValueError(
                f"Theme assetPath has no files in release: {theme['id']}"
            )


def release_directory(epoch: int, version: int) -> Path:
    return Path(RELEASES_DIR) / f"e{epoch}" / f"v{version}"


def release_manifest_path(epoch: int, version: int) -> Path:
    return release_directory(epoch, version) / "manifest.json"


def manifest_file_entry(root: Path, path_str: str, release_dir: Path) -> dict:
    path = root / path_str
    return {
        "id": file_id_for(path_str),
        "path": path_str,
        "url": f"{BASE_URL}/{release_dir.as_posix()}/{path_str}",
        "sha256": sha256_file(path),
        "contentType": content_type_for(path),
        "sizeBytes": path.stat().st_size,
    }


def copy_release_files(root: Path, release_dir: Path, paths: list[str]) -> None:
    destination_root = root / release_dir
    if destination_root.exists():
        shutil.rmtree(destination_root)

    for path_str in paths:
        source = root / path_str
        destination = destination_root / path_str
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def manifest_index_entry(manifest: dict, manifest_path: Path) -> dict:
    return {
        "url": f"{BASE_URL}/{manifest_path.as_posix()}",
        "contentEpoch": manifest["contentEpoch"],
        "contentVersion": manifest["contentVersion"],
        "minimumAppVersion": manifest["minimumAppVersion"],
    }


def manifest_index(manifests: list[tuple[dict, Path]]) -> dict:
    return {
        "manifests": [
            manifest_index_entry(manifest, path) for manifest, path in manifests
        ]
    }


def legacy_root_manifest(manifests: list[tuple[dict, Path]], app_version: str) -> dict:
    for manifest, _ in manifests:
        if is_app_version_compatible(app_version, manifest["minimumAppVersion"]):
            return manifest

    if not manifests:
        raise ValueError("Cannot write manifest.json without any release manifests")
    return manifests[-1][0]


def build_manifest(root: Path, args: argparse.Namespace) -> dict:
    existing = current_manifest(root)
    config = content_config(root)
    categories_by_locale = read_category_files(root)
    theme_catalog = read_theme_catalog(root)
    epoch = content_epoch(existing, config, args.content_epoch)
    min_app_version = minimum_app_version(existing, config, args.min_app_version)
    paths = collected_paths(root)
    validate_content_files(root, paths, categories_by_locale, theme_catalog)
    content_version = next_content_version(
        existing,
        categories_by_locale,
        epoch,
        source_file_entries(root, paths),
        min_app_version,
    )
    write_category_versions(root, categories_by_locale, content_version)
    categories_by_locale = read_category_files(root)

    release_dir = release_directory(epoch, content_version)
    files = [manifest_file_entry(root, path_str, release_dir) for path_str in paths]

    return {
        "schemaVersion": SCHEMA_VERSION,
        "contentEpoch": epoch,
        "contentVersion": content_version,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minimumAppVersion": min_app_version,
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
    config = content_config(root)
    manifest = build_manifest(root, args)
    release_dir = release_directory(manifest["contentEpoch"], manifest["contentVersion"])
    paths = [file["path"] for file in manifest["files"]]
    copy_release_files(root, release_dir, paths)
    release_path = release_manifest_path(
        manifest["contentEpoch"],
        manifest["contentVersion"],
    )
    write_manifest(root / release_path, manifest)
    manifests = release_manifests(root)
    write_manifest(root / "manifest_index.json", manifest_index(manifests))
    write_manifest(
        root / "manifest.json",
        legacy_root_manifest(manifests, legacy_manifest_app_version(config)),
    )
    print(
        "Generated manifest.json, manifest_index.json, "
        f"and {release_path.as_posix()}"
    )


if __name__ == "__main__":
    main()
