from __future__ import annotations

import os
import sys
from collections.abc import MutableMapping

UTF8_ENV = {
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
}
OUTPUT_DECODINGS = ("utf-8", "gbk", "cp936")


def configure_utf8_runtime() -> None:
    os.environ.update(UTF8_ENV)
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


def utf8_subprocess_env(
    env: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    payload = dict(os.environ if env is None else env)
    payload.update(UTF8_ENV)
    return payload


def decode_process_output(output: bytes | str | None) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    utf16_text = decode_utf16_if_likely(output)
    if utf16_text is not None:
        return utf16_text
    for encoding in OUTPUT_DECODINGS:
        try:
            return output.decode(encoding)
        except UnicodeDecodeError:
            continue
    return output.decode("utf-8", errors="replace")


def decode_utf16_if_likely(output: bytes) -> str | None:
    if output.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return output.decode("utf-16")
        except UnicodeDecodeError:
            return None
    if len(output) < 4:
        return None
    sample = output[: min(len(output), 200)]
    odd_nuls = sample[1::2].count(0)
    even_nuls = sample[0::2].count(0)
    if odd_nuls >= max(2, len(sample[1::2]) // 3):
        try:
            return output.decode("utf-16-le")
        except UnicodeDecodeError:
            return None
    if even_nuls >= max(2, len(sample[0::2]) // 3):
        try:
            return output.decode("utf-16-be")
        except UnicodeDecodeError:
            return None
    return None
