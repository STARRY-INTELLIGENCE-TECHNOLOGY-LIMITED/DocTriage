import re
import subprocess

import pytest

import cleaner
from cleaner import DocumentWashError, DocumentWasher
from config import DEFAULT_NOISE_PATTERNS


def test_clean_content_removes_toc_and_noise() -> None:
    washer = DocumentWasher.__new__(DocumentWasher)
    washer._compiled_noise_patterns = [
        re.compile(pattern) for pattern in DEFAULT_NOISE_PATTERNS
    ]

    raw_markdown = """
Captured by FireShot

# Table of Contents
1 Overview ........ 1
2 Design .......... 2

# Overview
This is the first useful paragraph.
Copyright 2025 Example
Page 1 of 3
"""

    cleaned = washer.clean_content(raw_markdown)

    assert "Captured by FireShot" not in cleaned
    assert "Table of Contents" not in cleaned
    assert "Overview ........ 1" not in cleaned
    assert "Copyright" not in cleaned
    assert "This is the first useful paragraph." in cleaned


def test_clean_content_keeps_short_technical_tokens() -> None:
    washer = DocumentWasher.__new__(DocumentWasher)
    washer._compiled_noise_patterns = [
        re.compile(pattern) for pattern in DEFAULT_NOISE_PATTERNS
    ]

    raw_markdown = """
# Acronyms
API
JWT
RAG
1
Page 2 of 9
"""

    cleaned = washer.clean_content(raw_markdown)

    assert "API" in cleaned
    assert "JWT" in cleaned
    assert "RAG" in cleaned
    assert "\n1\n" not in f"\n{cleaned}\n"
    assert "Page 2 of 9" not in cleaned


def test_wash_rejects_empty_file_before_docling(tmp_path, monkeypatch) -> None:
    empty_docx = tmp_path / "empty.docx"
    empty_docx.write_bytes(b"")
    washer = DocumentWasher.__new__(DocumentWasher)

    def fail_if_called(path):
        raise AssertionError("docling should not be called for empty files")

    monkeypatch.setattr(washer, "_convert_with_docling", fail_if_called)

    with pytest.raises(DocumentWashError, match="Input document is empty"):
        washer.wash(empty_docx)


def test_legacy_ppt_conversion_decodes_non_utf8_error(tmp_path, monkeypatch) -> None:
    ppt = tmp_path / "deck.ppt"
    ppt.write_bytes(b"ppt")
    washer = DocumentWasher.__new__(DocumentWasher)

    monkeypatch.setattr(cleaner.shutil, "which", lambda command: "soffice")

    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=args[0],
            stderr="转换失败".encode("gbk"),
            output=b"",
        )

    monkeypatch.setattr(cleaner.subprocess, "run", fake_run)

    with pytest.raises(DocumentWashError, match="转换失败"):
        washer._convert_legacy_ppt(ppt)
