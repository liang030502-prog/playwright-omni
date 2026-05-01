# RED Test: 文件下载处理
# test_bh_download.py
# 状态：GREEN（实现完成后应全部通过）

import pytest
import os
import tempfile
import shutil
from unittest.mock import MagicMock


class MockDownload:
    """模拟 Playwright Download 对象"""
    def __init__(self, url: str, suggested_filename: str, content: bytes = b"mock content"):
        self.url = url
        self.suggested_filename = suggested_filename
        self._content = content
        self._source_path = None

    def _ensure_source(self, save_dir: str) -> str:
        if self._source_path is None:
            self._source_path = os.path.join(save_dir, ".dl_src_" + self.suggested_filename)
            with open(self._source_path, "wb") as f:
                f.write(self._content)
        return self._source_path

    def path(self) -> str:
        return self._ensure_source(os.environ.get("TEMP", "/tmp"))

    async def save_as(self, path: str):
        src = self._ensure_source(os.path.dirname(path) or ".")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copy2(src, path)


# ── 测试：bh_tools.handle_download ──────────────────────

def test_download_init_accepts_download():
    from bh_tools import handle_download
    with tempfile.TemporaryDirectory() as tmpdir:
        dl = MockDownload("https://example.com/report.pdf", "report.pdf", b"fake file content")
        result = handle_download(dl, save_dir=tmpdir)
        assert result is not None
        assert os.path.exists(result["saved_path"])
        assert os.path.getsize(result["saved_path"]) == len(b"fake file content")
        assert result["filename"] == "report.pdf"


def test_download_filename_from_url():
    from bh_tools import handle_download
    with tempfile.TemporaryDirectory() as tmpdir:
        dl = MockDownload("https://example.com/api/export", "", b"data")
        result = handle_download(dl, save_dir=tmpdir)
        assert result is not None
        assert result["filename"] != ""
        assert result["saved_path"].endswith(result["filename"])


def test_download_auto_creates_dir():
    from bh_tools import handle_download
    with tempfile.TemporaryDirectory() as tmpdir:
        nested = os.path.join(tmpdir, "sub", "deep", "dir")
        dl = MockDownload("https://example.com/file.txt", "file.txt", b"hello")
        result = handle_download(dl, save_dir=nested)
        assert os.path.exists(nested)
        assert os.path.exists(result["saved_path"])


def test_download_duplicate_naming():
    from bh_tools import handle_download
    with tempfile.TemporaryDirectory() as tmpdir:
        dl1 = MockDownload("https://example.com/report.pdf", "report.pdf", b"v1")
        dl2 = MockDownload("https://example.com/report.pdf", "report.pdf", b"v2")
        r1 = handle_download(dl1, save_dir=tmpdir)
        r2 = handle_download(dl2, save_dir=tmpdir)
        assert os.path.exists(r1["saved_path"])
        assert os.path.exists(r2["saved_path"])
        assert os.path.getsize(r1["saved_path"]) == 2
        assert os.path.getsize(r2["saved_path"]) == 2
        assert r1["filename"] == "report.pdf"
        assert r2["filename"] == "report_1.pdf"


def test_download_returns_metadata():
    from bh_tools import handle_download
    with tempfile.TemporaryDirectory() as tmpdir:
        dl = MockDownload("https://example.com/doc.pdf", "doc.pdf", b"pdf data")
        result = handle_download(dl, save_dir=tmpdir)
        required_keys = {"filename", "saved_path", "size", "url"}
        assert set(result.keys()) == required_keys
        assert result["size"] == 8  # len(b"pdf data") = 8


def test_download_context_manager():
    from bh_tools import DownloadContext
    mock_page = MagicMock()
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = DownloadContext(mock_page, save_dir=tmpdir)
        ctx.handler.results.append({
            "filename": "test.pdf",
            "saved_path": os.path.join(tmpdir, "test.pdf"),
            "size": 4,
            "url": "https://example.com/test.pdf"
        })
        result = ctx.wait_done(timeout=0.5)
        assert len(result) == 1
        assert result[0]["filename"] == "test.pdf"


def test_setup_download_listener_registers():
    from bh_tools import setup_download_listener
    mock_page = MagicMock()
    handler = setup_download_listener(mock_page, save_dir="/tmp/downloads")
    mock_page.on.assert_called_once()
    assert handler.save_dir == "/tmp/downloads"


def test_setup_download_listener_returns_handler():
    from bh_tools import setup_download_listener
    mock_page = MagicMock()
    handler = setup_download_listener(mock_page, save_dir="/tmp/dl")
    assert hasattr(handler, "save_dir")
    assert hasattr(handler, "results")
    assert hasattr(handler, "wait_done")
    assert handler.save_dir == "/tmp/dl"
    assert handler.results == []
