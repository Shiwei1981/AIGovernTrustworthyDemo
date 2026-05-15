from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import FINAL_JSONL_PATH, RAW_QA_PATH, ensure_archive_dir, load_env, require_env

load_env()

SYSTEM_PROMPT = "You are an AI governance expert specializing in AI governance frameworks and controls."


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the final chat-completions JSONL for fine-tuning.")
    parser.add_argument("--raw-input", type=Path, default=RAW_QA_PATH)
    parser.add_argument("--output", type=Path, default=FINAL_JSONL_PATH)
    parser.add_argument(
        "--target-count",
        type=int,
        default=int(require_env("L4_FINETUNE_TOTAL_QA_PAIRS")),
    )
    return parser.parse_args()


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip()


def main() -> None:
    args = _parse_args()
    ensure_archive_dir()
    if not args.raw_input.exists():
        raise RuntimeError(f"Raw Q&A archive not found: {args.raw_input}")

    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    total_raw = 0

    for line in args.raw_input.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        for item in record.get("items", []):
            total_raw += 1
            question = _normalize(str(item.get("question", "")))
            answer = _normalize(str(item.get("answer", "")))
            key = (question.casefold(), answer.casefold())
            if not question or not answer or key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": answer},
                    ]
                }
            )
            if len(rows) == args.target_count:
                break
        if len(rows) == args.target_count:
            break

    if len(rows) < args.target_count:
        raise RuntimeError(
            f"Only built {len(rows)} unique Q&A rows from {total_raw} raw items; "
            f"need {args.target_count}."
        )

    with args.output.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    print(f"[INFO] Raw Q&A items scanned : {total_raw}")
    print(f"[INFO] Final rows written    : {len(rows)}")
    print(f"[RESULT] Final JSONL archive : {args.output}")


if __name__ == "__main__":
    main()
