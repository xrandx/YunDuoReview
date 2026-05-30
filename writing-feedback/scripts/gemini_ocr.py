#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCR helper for the writing-feedback skill using Gemini's OpenAI API format."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit


DEFAULT_CONFIG_PATH = Path.home() / ".writing-feedback" / "gemini_ocr.json"
FALLBACK_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
FALLBACK_MODEL = "gemini-2.5-flash"
DEFAULT_BASE_URL = (
    os.environ.get("GEMINI_OPENAI_BASE_URL")
    or os.environ.get("GEMINI_BASE_URL")
    or FALLBACK_BASE_URL
)
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL") or FALLBACK_MODEL

IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
}


class OcrError(RuntimeError):
    """User-facing OCR error."""


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Use Gemini OpenAI-compatible API to OCR Chinese student writing."
    )
    parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        help="One or more image or scanned PDF paths. Multiple images are treated as one essay in the given order.",
    )
    parser.add_argument(
        "--output",
        help="Optional output JSON path. Prints to stdout when omitted.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Override model name. Default comes from config, GEMINI_MODEL, "
            f"then {FALLBACK_MODEL}."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=(
            "Override OpenAI-compatible base URL. Default comes from config, "
            "GEMINI_OPENAI_BASE_URL or GEMINI_BASE_URL, "
            f"then {FALLBACK_BASE_URL}."
        ),
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help=f"Local config JSON path. Default: {DEFAULT_CONFIG_PATH}",
    )
    parser.add_argument(
        "--api-key-env",
        default="GEMINI_API_KEY",
        help="Fallback environment variable for the Gemini API key. Default: GEMINI_API_KEY.",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=20,
        help="Maximum pages to process from a PDF. Default: 20.",
    )
    return parser.parse_args(argv)


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    if not path.is_file():
        raise OcrError(f"配置路径不是文件：{path}")

    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OcrError(f"配置文件不是合法 JSON：{path}。原因：{exc}") from exc

    if not isinstance(parsed, dict):
        raise OcrError(f"配置文件顶层必须是 JSON 对象：{path}")

    return parsed


def first_config_value(config: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for key in keys:
        value = config.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def resolve_runtime_options(args: argparse.Namespace) -> Tuple[str, str, str]:
    config_path = Path(args.config).expanduser()
    config = load_config(config_path)

    model = (
        args.model
        or first_config_value(config, ["model", "model_name", "modelname"])
        or os.environ.get("GEMINI_MODEL")
        or DEFAULT_MODEL
    )
    base_url = (
        args.base_url
        or first_config_value(config, ["base_url", "baseurl"])
        or os.environ.get("GEMINI_OPENAI_BASE_URL")
        or os.environ.get("GEMINI_BASE_URL")
        or DEFAULT_BASE_URL
    )
    api_key = (
        first_config_value(config, ["api_key", "key"])
        or os.environ.get(args.api_key_env)
        or ""
    )

    if not api_key:
        raise OcrError(
            f"缺少 API Key：请在配置文件 {config_path} 中填写 api_key，"
            f"或设置环境变量 {args.api_key_env}。"
        )

    return model, base_url, api_key


def encode_data_url(image_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def normalize_openai_base_url(url: str) -> str:
    stripped_url = url.strip()
    parsed = urlsplit(stripped_url)
    path = parsed.path.rstrip("/")

    if path.endswith("/chat/completions"):
        path = path[: -len("/chat/completions")]

    if not path.endswith("/"):
        path = f"{path}/"

    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def load_image(path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    suffix = path.suffix.lower()
    mime_type = IMAGE_MIME_TYPES.get(suffix)
    if not mime_type:
        supported = ", ".join(sorted([*IMAGE_MIME_TYPES.keys(), ".pdf"]))
        raise OcrError(f"不支持的输入格式：{suffix or '(无扩展名)'}。支持：{supported}")

    return (
        [
            {
                "page": 1,
                "mime_type": mime_type,
                "data_url": encode_data_url(path.read_bytes(), mime_type),
            }
        ],
        [],
    )


def load_pdf(path: Path, page_limit: int) -> Tuple[List[Dict[str, Any]], List[str]]:
    if page_limit < 1:
        raise OcrError("--page-limit 必须大于等于 1。")

    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise OcrError(
            "处理 PDF 需要 PyMuPDF。请先安装：python3 -m pip install pymupdf"
        ) from exc

    warnings: List[str] = []
    pages: List[Dict[str, Any]] = []

    try:
        document = fitz.open(path)
    except Exception as exc:  # pragma: no cover - depends on fitz internals
        raise OcrError(f"无法打开 PDF：{path}。原因：{exc}") from exc

    try:
        total_pages = document.page_count
        if total_pages == 0:
            raise OcrError(f"PDF 没有可处理页面：{path}")

        if total_pages > page_limit:
            warnings.append(
                f"{path.name} 共 {total_pages} 页，已按 --page-limit={page_limit} 只处理前 {page_limit} 页。"
            )

        pages_to_process = min(total_pages, page_limit)
        matrix = fitz.Matrix(2, 2)
        for index in range(pages_to_process):
            page = document.load_page(index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pages.append(
                {
                    "page": index + 1,
                    "mime_type": "image/png",
                    "data_url": encode_data_url(pixmap.tobytes("png"), "image/png"),
                }
            )
    finally:
        document.close()

    return pages, warnings


def load_input(path: Path, page_limit: int) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not path.exists():
        raise OcrError(f"输入文件不存在：{path}")
    if not path.is_file():
        raise OcrError(f"输入路径不是文件：{path}")

    if path.suffix.lower() == ".pdf":
        return load_pdf(path, page_limit)

    return load_image(path)


def load_inputs(paths: List[Path], page_limit: int) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not paths:
        raise OcrError("请至少提供一个 --input 文件。")

    pages: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for path in paths:
        loaded_pages, loaded_warnings = load_input(path, page_limit)
        warnings.extend(loaded_warnings)
        for loaded_page in loaded_pages:
            loaded_page["sequence"] = len(pages) + 1
            loaded_page["source_file"] = str(path)
            loaded_page["source_name"] = path.name
            pages.append(loaded_page)

    return pages, warnings


def build_prompt(source_names: List[str], pages: List[Dict[str, Any]]) -> str:
    image_count = len(pages)
    source_summary = "、".join(source_names)
    return f"""你是中文中小学作文扫描件 OCR 和客观识别助手。

请按输入顺序识别这些图像/页面：{source_summary}。它们共同组成同一篇作文，共 {image_count} 张图像/页面。只输出一个合法 JSON 对象，不要输出 Markdown、解释或代码块。

核心要求：
1. 尽量保留学生原文的换行、段首空格、标点、错别字、漏字、多字、重复字、涂改痕迹和无法确认的字。
2. 不要把不通顺或疑似错别字自动改成通顺文本。
3. 所有错别字、漏字、多字、重复字、标点、格式、疑似教师批注、疑似 OCR/手写识别错误、无法确认内容，都只在 `raw_text` 正文中用 `【】` 紧跟原文片段做内联批注，不要单独列问题清单。
4. 批注必须客观、简短，不做作文整体评价，不扩写，不润色，不代写。
5. 如果原文字词可辨但疑似有问题，保留原文字词并在后面批注，例如：`以经【错别字，疑为“已经”】`、`的的【重复字】`、`，。【标点疑似多余】`。
6. 如果字词无法确认，在对应位置写 `【无法确认】`；如果只是可能识别错，写 `原识别内容【疑似OCR/手写识别错误，可能是“...”】`。
7. 如果识别到疑似教师批注、分数、修改符号等非学生正文，保留可见内容并标注 `【疑似教师批注】`。
8. 不确定时标注“疑似”或“需要人工确认”，不要把推测当作事实。

JSON 顶层结构必须包含这些字段：
{{
  "raw_text": "尽量保留版式的学生作文正文；多图或多页时用明确图像/页标记分隔；错别字或其他问题必须在正文内用【】紧跟原文片段批注",
  "metadata": {{
    "class_name": null,
    "grade": null,
    "student_name": null,
    "title": null,
    "topic_description": null
  }},
  "warnings": [
    "低清晰度、遮挡、裁切、页数限制、无法识别区域等提示；没有则为空数组"
  ]
}}
"""


def build_messages(pages: List[Dict[str, Any]], source_names: List[str]) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = [
        {"type": "text", "text": build_prompt(source_names, pages)}
    ]
    for page in pages:
        content.append(
            {
                "type": "text",
                "text": (
                    f"图像 {page['sequence']}，来源文件：{page['source_name']}，"
                    f"文件内页码/顺序：{page['page']}。"
                ),
            }
        )
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": page["data_url"],
                },
            }
        )

    return [
        {
            "role": "system",
            "content": (
                "你只输出合法 JSON。识别中文手写作文时必须保留原貌，"
                "不要擅自纠错；问题只允许用 raw_text 内的【】批注表达，不要输出 issues 字段。"
            ),
        },
        {
            "role": "user",
            "content": content,
        },
    ]


def extract_message_text(message_content: Any) -> str:
    if isinstance(message_content, str):
        return message_content
    if isinstance(message_content, list):
        parts = []
        for item in message_content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif hasattr(item, "text"):
                parts.append(str(item.text))
        return "\n".join(part for part in parts if part)
    return str(message_content)


def strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]

    return stripped


def coerce_metadata(value: Any) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {
        "class_name": None,
        "grade": None,
        "student_name": None,
        "title": None,
        "topic_description": None,
    }
    if isinstance(value, dict):
        defaults.update(value)
    return defaults


def text_or_empty(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def parse_model_json(model_output: str, warnings: List[str]) -> Dict[str, Any]:
    try:
        parsed = json.loads(strip_json_fence(model_output))
    except json.JSONDecodeError:
        return {
            "raw_text": "",
            "metadata": coerce_metadata({}),
            "warnings": [
                *warnings,
                "模型输出不是合法 JSON，已保留原始输出到 raw_model_output。",
            ],
            "raw_model_output": model_output,
        }

    if not isinstance(parsed, dict):
        return {
            "raw_text": "",
            "metadata": coerce_metadata({}),
            "warnings": [
                *warnings,
                "模型输出的 JSON 顶层不是对象，已保留原始输出到 raw_model_output。",
            ],
            "raw_model_output": model_output,
        }

    parsed_warnings = parsed.get("warnings") or []
    if not isinstance(parsed_warnings, list):
        parsed_warnings = [str(parsed_warnings)]

    return {
        "raw_text": text_or_empty(parsed.get("raw_text")),
        "metadata": coerce_metadata(parsed.get("metadata")),
        "warnings": [*warnings, *[str(item) for item in parsed_warnings]],
    }


def run_ocr(
    *,
    input_paths: List[Path],
    model: str,
    base_url: str,
    api_key: str,
    page_limit: int,
) -> Dict[str, Any]:
    pages, warnings = load_inputs(input_paths, page_limit)
    source_names = [path.name for path in input_paths]

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise OcrError(
            "缺少 Python 依赖 openai。请先安装：python3 -m pip install -r writing-feedback/requirements.txt"
        ) from exc

    client = OpenAI(api_key=api_key, base_url=normalize_openai_base_url(base_url))

    try:
        response = client.chat.completions.create(
            model=model,
            messages=build_messages(pages, source_names),
            temperature=0,
        )
    except Exception as exc:  # pragma: no cover - depends on remote SDK/API
        raise OcrError(f"Gemini OCR 请求失败：{exc}") from exc

    if not response.choices:
        raise OcrError("Gemini OCR 没有返回候选结果。")

    model_output = extract_message_text(response.choices[0].message.content)
    result = parse_model_json(model_output, warnings)
    result.update(
        {
            "source_files": [str(path) for path in input_paths],
            "model": model,
            "image_count": len(pages),
        }
    )
    return result


def write_result(result: Dict[str, Any], output_path: Optional[Path]) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
        return
    print(text)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    input_paths = [Path(item).expanduser() for item in args.input]
    output_path = Path(args.output).expanduser() if args.output else None

    try:
        model, base_url, api_key = resolve_runtime_options(args)
        result = run_ocr(
            input_paths=input_paths,
            model=model,
            base_url=base_url,
            api_key=api_key,
            page_limit=args.page_limit,
        )
        write_result(result, output_path)
    except OcrError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
