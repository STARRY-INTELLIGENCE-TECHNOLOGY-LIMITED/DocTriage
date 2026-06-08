import runtime_encoding


def test_utf8_subprocess_env_sets_python_utf8_flags(monkeypatch) -> None:
    monkeypatch.setenv("PYTHONUTF8", "0")
    monkeypatch.setenv("PYTHONIOENCODING", "latin-1")

    env = runtime_encoding.utf8_subprocess_env()

    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_decode_process_output_accepts_non_utf8_bytes() -> None:
    assert "\u4e2d\u6587" in runtime_encoding.decode_process_output(
        bytes.fromhex("d6d0cec4")
    )


def test_decode_process_output_handles_missing_output() -> None:
    assert runtime_encoding.decode_process_output(None) == ""


def test_decode_process_output_accepts_utf16_shell_output() -> None:
    assert "C:\\Docs" in runtime_encoding.decode_process_output(
        "C:\\Docs\r\n".encode("utf-16-le")
    )


def test_configure_utf8_runtime_overrides_python_encoding_env(monkeypatch) -> None:
    monkeypatch.setenv("PYTHONUTF8", "0")
    monkeypatch.setenv("PYTHONIOENCODING", "latin-1")

    runtime_encoding.configure_utf8_runtime()

    assert runtime_encoding.os.environ["PYTHONUTF8"] == "1"
    assert runtime_encoding.os.environ["PYTHONIOENCODING"] == "utf-8"
