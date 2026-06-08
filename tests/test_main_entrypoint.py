import json
from io import BytesIO
from pathlib import Path

import main


def test_main_without_args_prints_help_and_launches_ui(monkeypatch, capsys) -> None:
    launched = {"value": False}

    def fake_launch_default_ui() -> None:
        launched["value"] = True

    monkeypatch.setattr(main, "launch_default_ui", fake_launch_default_ui)

    main.main([])

    captured = capsys.readouterr()
    assert "--source-dir" in captured.out
    assert "--output-root" in captured.out
    assert launched["value"] is True


def test_is_doctriage_ui_running_detects_config_endpoint(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps({"capabilities": {}}).encode("utf-8")

    monkeypatch.setattr(main.urllib.request, "urlopen", lambda url, timeout: FakeResponse())

    assert main.is_doctriage_ui_running("http://127.0.0.1:8765/") is True


def test_is_doctriage_ui_running_rejects_other_service(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return BytesIO(b'{"status":"ok"}').read()

    monkeypatch.setattr(main.urllib.request, "urlopen", lambda url, timeout: FakeResponse())

    assert main.is_doctriage_ui_running("http://127.0.0.1:8765/") is False


def test_stale_run_lock_is_ignored_when_process_is_gone(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    settings = main.Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        SOURCE_DIR=tmp_path / "source",
        OUTPUT_ROOT=output_root,
    )
    settings.SOURCE_DIR.mkdir()
    output_root.mkdir()
    settings.state_dir.mkdir(parents=True)
    settings.log_dir.mkdir(parents=True)
    settings.application_log_path.write_text("", encoding="utf-8")
    settings.progress_path.write_text("{}", encoding="utf-8")
    (settings.state_dir / "run.lock").write_text(
        json.dumps({"pid": 999999, "token": "stale"}, ensure_ascii=False),
        encoding="utf-8",
    )

    with main.OutputRunLock(settings):
        assert settings.state_dir.joinpath("run.lock").exists()


def test_is_process_alive_handles_non_utf8_tasklist_output(monkeypatch) -> None:
    class FakeCompletedProcess:
        stdout = b"\xd0\xce\xcf\xb5,999999\r\n"

    monkeypatch.setattr(main.os, "name", "nt")
    monkeypatch.setattr(
        main.subprocess,
        "run",
        lambda *args, **kwargs: FakeCompletedProcess(),
    )

    assert main.is_process_alive(12345) is False


def test_is_process_alive_handles_missing_stdout(monkeypatch) -> None:
    class FakeCompletedProcess:
        stdout = None

    monkeypatch.setattr(main.os, "name", "nt")
    monkeypatch.setattr(
        main.subprocess,
        "run",
        lambda *args, **kwargs: FakeCompletedProcess(),
    )

    assert main.is_process_alive(12345) is False


def test_build_local_summary_removes_page_and_ui_chrome() -> None:
    summary = main.build_local_summary(
        "<!-- page 1 --> · \ue6fd 文 架构文章 创作中心 朗读文章 "
        "Powered by 通义语音合成 摘要：本文介绍订单链路的隔离设计，"
        "通过缓存分层、限流和故障演练降低大促风险。",
        max_chars=300,
    )

    assert "<!-- page" not in summary
    assert "\ue6fd" not in summary
    assert "创作中心" not in summary
    assert "Powered by" not in summary
    assert "订单链路" in summary


def test_configure_logging_skips_stream_when_stdio_is_log_file(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    settings = main.Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )
    output_root.mkdir()
    settings.log_dir.mkdir(parents=True)
    settings.application_log_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        main,
        "stream_points_to_path",
        lambda stream, path: stream is main.sys.stderr,
    )

    main.configure_logging(settings)

    handlers = main.logging.getLogger().handlers
    assert any(isinstance(handler, main.logging.FileHandler) for handler in handlers)
    assert not any(
        type(handler) is main.logging.StreamHandler for handler in handlers
    )
