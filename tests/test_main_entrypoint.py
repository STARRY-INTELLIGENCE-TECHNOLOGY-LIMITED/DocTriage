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
