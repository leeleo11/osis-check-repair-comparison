"""Protocol-compatible localization and repair scoring."""

from __future__ import annotations

import json
import re
from typing import Any, Sequence


_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _decode_localizations(blob: str) -> list[dict[str, str]] | None:
    decoder = json.JSONDecoder()
    found: list[dict[str, str]] = []
    offset = 0
    while offset < len(blob):
        if blob[offset] != "{":
            offset += 1
            continue
        try:
            value, end = decoder.raw_decode(blob, offset)
        except json.JSONDecodeError:
            offset += 1
            continue
        offset = max(end, offset + 1)
        if not isinstance(value, dict):
            continue
        localizations = value.get("localizations")
        if not isinstance(localizations, list):
            continue
        for item in localizations:
            if not isinstance(item, dict):
                continue
            found.append(
                {
                    "check_item": str(item.get("check_item") or "").strip(),
                    "reason_code": str(item.get("reason_code") or "").strip(),
                }
            )
    return [found[-1]] if found else None


def extract_localizations(text: str) -> list[dict[str, str]] | None:
    if not text or not str(text).strip():
        return None
    blob = str(text)
    stripped = _THINK.sub("", blob).strip()
    if stripped != blob:
        parsed = _decode_localizations(stripped)
        if parsed is not None:
            return parsed
    return _decode_localizations(blob)


def score_localization(text: str, expected_reason_code: str) -> dict[str, Any]:
    prediction = extract_localizations(text)
    expected = str(expected_reason_code).strip()
    hit = bool(expected and prediction and prediction[-1]["reason_code"] == expected)
    return {
        "parse_ok": prediction is not None,
        "pred": prediction or [],
        "localization_score": float(hit),
        "localization_hit": hit,
    }


def _norm_set(names: Sequence[str]) -> set[str]:
    return {str(name).strip() for name in names if str(name).strip()}


def score_repair(
    ng_after: Sequence[str],
    target_item: str,
    ng_seeded: Sequence[str],
) -> dict[str, Any]:
    target = str(target_item).strip()
    after = _norm_set(ng_after)
    seeded = _norm_set(ng_seeded)
    new_ng = sorted(after - seeded)
    target_ok = bool(target) and target not in after
    repair_pass = bool(target_ok and not new_ng)
    return {
        "repair_pass": repair_pass,
        "target_ok": target_ok,
        "target_item": target,
        "ng_after": sorted(after),
        "new_ng": new_ng,
    }
