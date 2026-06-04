from pathlib import Path

from config import Settings
from meta_profiler import MetadataProfiler


def test_profile_document_computes_ratios(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.md"
    file_path.write_text("# Title\n\nBody text\n\n```python\nprint('hi')\n```\n", encoding="utf-8")

    profile = MetadataProfiler().profile_document(
        file_path=file_path,
        clean_markdown=file_path.read_text(encoding="utf-8"),
    )

    assert profile.header_count == 1
    assert profile.header_density > 0
    assert profile.code_to_text_ratio > 0
    assert profile.file_suffix == ".md"


def test_pdf_metadata_extraction_can_be_disabled(tmp_path: Path, monkeypatch) -> None:
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"%PDF-1.4\nnot a complete pdf")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("PdfReader should not be called")

    monkeypatch.setattr("meta_profiler.PdfReader", fail_if_called)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=tmp_path,
        OUTPUT_ROOT=tmp_path / "output",
        PDF_METADSample_ENABLED=False,
    )

    profile = MetadataProfiler(settings=settings).profile_document(
        file_path=file_path,
        clean_markdown="# Title\n\nBody",
    )

    assert profile.pdf_author is None
    assert profile.pdf_producer is None
    assert profile.extraction_notes == []
