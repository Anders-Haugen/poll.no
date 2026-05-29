#!/usr/bin/env python3
"""Sync 3D product JSON files from folder contents.

Scans each product folder listed in data/3d-products/index.json and updates:
- images: all files in images/ with known image extensions
- stl.file: first .stl file found in models/ (alphabetical)
- stl.units: defaults to "mm" when missing

This avoids relying on runtime directory listing support on the web host.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data" / "3d-products" / "index.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def to_posix_relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sync_product(product_path: Path) -> tuple[int, bool]:
    product = read_json(product_path)
    product_dir = product_path.parent
    changed = False

    images_dir = product_dir / "images"
    image_paths: list[str] = []
    if images_dir.exists() and images_dir.is_dir():
        image_files = [
            file_path
            for file_path in sorted(images_dir.iterdir(), key=lambda p: p.name.lower())
            if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS
        ]
        image_paths = [to_posix_relative(file_path) for file_path in image_files]

    if product.get("images") != image_paths:
        product["images"] = image_paths
        changed = True

    models_dir = product_dir / "models"
    stl_file = ""
    if models_dir.exists() and models_dir.is_dir():
        stl_candidates = [
            file_path
            for file_path in sorted(models_dir.iterdir(), key=lambda p: p.name.lower())
            if file_path.is_file() and file_path.suffix.lower() == ".stl"
        ]
        if stl_candidates:
            stl_file = to_posix_relative(stl_candidates[0])

    stl = product.get("stl")
    if not isinstance(stl, dict):
        stl = {}

    if stl.get("file") != stl_file:
        stl["file"] = stl_file
        changed = True

    if not stl.get("units"):
        stl["units"] = "mm"
        changed = True

    product["stl"] = stl

    if changed:
        write_json(product_path, product)

    return len(image_paths), bool(stl_file)


def main() -> int:
    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"Missing index file: {INDEX_PATH}")

    index_data = read_json(INDEX_PATH)
    products = index_data.get("products", [])

    updated_count = 0
    summary_lines: list[str] = []

    for entry in products:
        meta = entry.get("meta")
        if not meta:
            continue

        product_path = ROOT / Path(meta)
        if not product_path.exists():
            summary_lines.append(f"- SKIP {meta} (missing)")
            continue

        before = read_json(product_path)
        image_count, has_stl = sync_product(product_path)
        after = read_json(product_path)

        changed = before != after
        if changed:
            updated_count += 1

        status = "UPDATED" if changed else "OK"
        summary_lines.append(
            f"- {status} {meta} | images={image_count} | stl={'yes' if has_stl else 'no'}"
        )

    index_data["updatedAt"] = date.today().isoformat()
    write_json(INDEX_PATH, index_data)

    print("Sync complete")
    print(f"Products changed: {updated_count}")
    print("Details:")
    for line in summary_lines:
        print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
