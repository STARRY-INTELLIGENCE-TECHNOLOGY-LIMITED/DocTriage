from __future__ import annotations

import math
import re

TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def normalize_pair(left: int, right: int) -> tuple[int, int]:
    return (left, right) if left < right else (right, left)


def add_window_pairs(pairs: set[tuple[int, int]], ordered: list[int], window: int) -> None:
    for position, left in enumerate(ordered):
        for right in ordered[position + 1 : position + 1 + window]:
            pairs.add(normalize_pair(left, right))


def tokenize(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value.lower())


def normalize_citation_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\.[a-z0-9]{1,8}\b", " ", value)
    value = re.sub(r"[_\-—–:：|/\\]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
