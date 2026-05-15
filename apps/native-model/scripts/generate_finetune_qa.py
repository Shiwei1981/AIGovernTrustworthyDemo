from __future__ import annotations

import argparse
import json
from math import ceil
from pathlib import Path
from typing import Any

from _common import (
    FINAL_JSONL_PATH,
    RAW_QA_PATH,
    ensure_archive_dir,
    get_aoai_client,
    get_credential,
    load_env,
    parse_pdf_pages,
    require_env,
)

load_env()

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "shared-observability"))

from shared_observability import log_llm_call  # noqa: E402

SERVICE_NAME = "AIGovernTrustworthyDemo.FineTuneQAGenerator"
TARGET_ID = "AIGovernTrustworthyDemoNativeModel"
TARGET_TYPE = "foundry_native_model"
SOURCE_TYPE = "test_script"

SYSTEM_PROMPT = (
    "You are generating high-quality fine-tuning Q&A pairs for an AI governance assistant. "
    "Use only the supplied source text. Cover distinct facts, definitions, obligations, risks, "
    "controls, lifecycle steps, examples, and exceptions from the text. Do not invent facts. "
    "Return compact but complete answers in plain English."
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate raw fine-tune Q&A from the 5 governance PDFs.")
    parser.add_argument(
        "--target-count",
        type=int,
        default=int(require_env("L4_FINETUNE_TOTAL_QA_PAIRS")),
        help="Total target Q&A count before dedupe/truncation.",
    )
    parser.add_argument(
        "--raw-output",
        type=Path,
        default=RAW_QA_PATH,
        help="Path to the raw page-level JSONL archive.",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=0,
        help="Optional limit for validation runs.",
    )
    return parser.parse_args()


def _load_seen_pages(raw_output: Path) -> set[str]:
    if not raw_output.exists():
        return set()
    seen: set[str] = set()
    for line in raw_output.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        seen.add(record["page_key"])
    return seen


def _build_messages(*, pdf_name: str, source: str, page_number: int, page_text: str, qa_count: int) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Source PDF: {pdf_name}\n"
                f"Source alias: {source}\n"
                f"Page number: {page_number}\n"
                f"Required Q&A count: {qa_count}\n\n"
                "Generate distinct question-answer pairs that collectively cover this page as broadly as possible. "
                "Questions should be specific and answerable from the text only. "
                "Return valid JSON in the form:\n"
                '{"items":[{"question":"...","answer":"..."}, ...]}\n\n'
                f"Page text:\n{page_text}"
            ),
        },
    ]


def _normalize_items(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    normalized: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        question = " ".join(str(item.get("question", "")).split()).strip()
        answer = " ".join(str(item.get("answer", "")).split()).strip()
        if question and answer:
            normalized.append({"question": question, "answer": answer})
    if not normalized:
        raise ValueError("no valid question/answer items returned")
    return normalized


def _generate_page_record(client, credential, page, qa_count: int) -> dict[str, Any]:
    messages = _build_messages(
        pdf_name=page.pdf_name,
        source=page.source,
        page_number=page.page_number,
        page_text=page.text,
        qa_count=qa_count,
    )
    target_endpoint = require_env("L4_FOUNDRY_NATIVE_MODEL_ENDPOINT")
    deployment = require_env("L4_FOUNDRY_NATIVE_MODEL_DEPLOYMENT")

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            completion = client.chat.completions.create(
                model=deployment,
                messages=messages,
                temperature=0.2,
                max_completion_tokens=min(max(qa_count * 220, 1200), 4096),
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content or ""
            payload = json.loads(content)
            items = _normalize_items(payload.get("items"))
            llm_input = {
                "model": deployment,
                "page_key": f"{page.pdf_name}:{page.page_number}",
                "messages": messages,
                "requested_qa_count": qa_count,
            }
            llm_output = {
                "items": items,
                "response_id": completion.id,
            }
            log_llm_call(
                service_name=SERVICE_NAME,
                target_type=TARGET_TYPE,
                source_type=SOURCE_TYPE,
                target_id=TARGET_ID,
                target_endpoint=target_endpoint,
                llm_input=llm_input,
                llm_output=llm_output,
                credential=credential,
                model_name=deployment,
                response_id=completion.id,
                extra_attributes={
                    "pdf_name": page.pdf_name,
                    "page_number": page.page_number,
                    "qa_count": len(items),
                },
            )
            return {
                "page_key": f"{page.pdf_name}:{page.page_number}",
                "source": page.source,
                "pdf_name": page.pdf_name,
                "page_number": page.page_number,
                "requested_qa_count": qa_count,
                "generated_qa_count": len(items),
                "response_id": completion.id,
                "items": items,
            }
        except Exception as exc:  # narrow retries around model/JSON/transient failures
            last_error = exc
            print(f"[WARN] {page.pdf_name} p{page.page_number} attempt {attempt}/3 failed: {exc}")
    raise RuntimeError(f"Failed to generate Q&A for {page.pdf_name} page {page.page_number}") from last_error


def main() -> None:
    args = _parse_args()
    ensure_archive_dir()

    pages = parse_pdf_pages()
    if args.page_limit > 0:
        pages = pages[: args.page_limit]
    qa_per_page = ceil(args.target_count / len(pages))
    seen = _load_seen_pages(args.raw_output)

    print(f"[INFO] Pages discovered     : {len(pages)}")
    print(f"[INFO] Target QA count     : {args.target_count}")
    print(f"[INFO] Requested/page      : {qa_per_page}")
    print(f"[INFO] Raw archive path    : {args.raw_output}")
    print(f"[INFO] Resume pages loaded : {len(seen)}")

    client = get_aoai_client()
    credential = get_credential()

    generated_pages = 0
    with args.raw_output.open("a", encoding="utf-8") as fh:
        for index, page in enumerate(pages, start=1):
            page_key = f"{page.pdf_name}:{page.page_number}"
            if page_key in seen:
                continue
            record = _generate_page_record(client, credential, page, qa_per_page)
            fh.write(json.dumps(record, ensure_ascii=True) + "\n")
            fh.flush()
            generated_pages += 1
            print(
                f"[INFO] {index}/{len(pages)} {page.pdf_name} p{page.page_number} -> "
                f"{record['generated_qa_count']} Q&A"
            )

    print(f"[RESULT] Generated page records written: {generated_pages}")
    print("[NEXT] Build final JSONL with: python3 apps/native-model/scripts/build_finetune_jsonl.py")


if __name__ == "__main__":
    main()
