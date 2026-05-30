#!/usr/bin/env python3
"""Render selected PDF pages to image files for OCR workflows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render selected 1-based PDF pages to PNG/JPEG images."
    )
    parser.add_argument("pdf", type=Path, help="Path to the source PDF file.")
    parser.add_argument(
        "--pages",
        required=True,
        help="1-based page list or ranges, such as '1', '2,4-6', or 'all'.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Directory for generated image files.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Render resolution. Use 220-300 for OCR; default: 300.",
    )
    parser.add_argument(
        "--format",
        choices=("png", "jpg", "jpeg"),
        default="png",
        help="Output image format; default: png.",
    )
    parser.add_argument(
        "--prefix",
        help="Output filename prefix; default: source PDF stem.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON array of generated absolute file paths.",
    )
    return parser.parse_args()


def parse_pages(spec: str, page_count: int) -> list[int]:
    normalized = spec.strip().lower()
    if normalized == "all":
        return list(range(1, page_count + 1))

    pages: list[int] = []
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            continue

        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = parse_page_number(start_text)
            end = parse_page_number(end_text)
            if start > end:
                raise ValueError(f"Invalid descending page range: {part}")
            pages.extend(range(start, end + 1))
        else:
            pages.append(parse_page_number(part))

    unique_pages = list(dict.fromkeys(pages))
    if not unique_pages:
        raise ValueError("No pages were selected.")

    out_of_bounds = [page for page in unique_pages if page < 1 or page > page_count]
    if out_of_bounds:
        raise ValueError(
            f"Page(s) out of range for a {page_count}-page PDF: "
            + ", ".join(str(page) for page in out_of_bounds)
        )

    return unique_pages


def parse_page_number(value: str) -> int:
    text = value.strip()
    if not text.isdigit():
        raise ValueError(f"Invalid page number: {value!r}")
    return int(text)


def render_pages(
    pdf_path: Path,
    pages: list[int],
    out_dir: Path,
    dpi: int,
    image_format: str,
    prefix: str,
    overwrite: bool,
) -> list[Path]:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency PyMuPDF. Install it with: python3 -m pip install PyMuPDF"
        ) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    extension = "jpg" if image_format == "jpeg" else image_format

    generated: list[Path] = []
    try:
        for page_number in pages:
            output_path = out_dir / f"{prefix}_page_{page_number:04d}.{extension}"
            if output_path.exists() and not overwrite:
                raise FileExistsError(
                    f"Output already exists: {output_path}. Use --overwrite to replace it."
                )

            page = doc.load_page(page_number - 1)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pixmap.save(output_path)
            generated.append(output_path.resolve())
    finally:
        doc.close()

    return generated


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf.expanduser().resolve()
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 2
    if not pdf_path.is_file():
        print(f"PDF path is not a file: {pdf_path}", file=sys.stderr)
        return 2
    if args.dpi <= 0:
        print("--dpi must be a positive integer.", file=sys.stderr)
        return 2

    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError:
        print(
            "Missing dependency PyMuPDF. Install it with: python3 -m pip install PyMuPDF",
            file=sys.stderr,
        )
        return 3

    try:
        with fitz.open(pdf_path) as doc:
            page_count = doc.page_count
        pages = parse_pages(args.pages, page_count)
        prefix = args.prefix or pdf_path.stem
        generated = render_pages(
            pdf_path=pdf_path,
            pages=pages,
            out_dir=args.out_dir.expanduser(),
            dpi=args.dpi,
            image_format=args.format,
            prefix=prefix,
            overwrite=args.overwrite,
        )
    except (FileExistsError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps([str(path) for path in generated], ensure_ascii=False, indent=2))
    else:
        for path in generated:
            print(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())