# bh_tools.py — browser-harness compatible toolset
# Functions: HTTP, keyboard, tab protection, iframe, upload, download, dialog, self-healing

from __future__ import annotations

import os
import sys
import json
import time
import base64
import gzip
import shutil
import asyncio
import ast
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Internal ──────────────────────────────────────────────────────────────

def _load_env():
    p = Path(__file__).parent.parent / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_env()

# ── HTTP (browser-free) ───────────────────────────────────────────────────

def http_get(url: str, headers: Optional[Dict] = None, timeout: float = 20.0) -> str:
    if os.environ.get("BROWSER_USE_API_KEY"):
        try:
            from fetch_use import fetch_sync
            return fetch_sync(url, headers=headers, timeout_ms=int(timeout * 1000)).text
        except ImportError:
            pass
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Encoding": "gzip",
    }
    if headers:
        h.update(headers)
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=h), timeout=timeout
    ) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data.decode()


def http_get_batch(urls: List[str], max_workers: int = 10) -> Dict[str, str]:
    def fetch_one(url: str) -> tuple:
        try:
            return url, http_get(url)
        except Exception as e:
            return url, "[ERROR] " + str(e)
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, url): url for url in urls}
        for future in as_completed(futures):
            url, content = future.result()
            results[url] = content
    return results


# ── Keyboard events (DOM level) ─────────────────────────────────────────

_KC = {
    "Enter": 13, "Tab": 9, "Escape": 27, "Backspace": 8, " ": 32,
    "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40,
    "Home": 36, "End": 35, "PageUp": 33, "PageDown": 34, "Delete": 46,
}

def dispatch_key(selector: str, key: str = "Enter", event: str = "keypress"):
    kc = _KC.get(key, ord(key) if len(key) == 1 else 0)
    script = (
        "(function() {"
        "var el = document.querySelector(" + json.dumps(selector) + ");"
        "if (el) {"
        "el.focus();"
        "el.dispatchEvent(new KeyboardEvent(" + json.dumps(event) + ", {"
        "key: " + json.dumps(key) + ","
        "code: " + json.dumps(key) + ","
        "keyCode: " + str(kc) + ","
        "which: " + str(kc) + ","
        "bubbles: true"
        "}));"
        "}"
        "})()"
    )
    return script


# ── Real tab protection ─────────────────────────────────────────────────

INTERNAL_URLS = (
    "chrome://", "chrome-untrusted://", "devtools://",
    "chrome-extension://", "about:", "chrome-webstore://",
)

def is_internal_url(url: str) -> bool:
    return any(url.startswith(u) for u in INTERNAL_URLS)


# ── Tab info ────────────────────────────────────────────────────────────

def get_tab_info(page) -> dict:
    from playwright.sync_api import Page
    if not isinstance(page, Page):
        raise TypeError("Expected playwright Page, got " + str(type(page)))
    try:
        info = page.evaluate('''
            JSON.stringify({
                url: location.href,
                title: document.title,
                w: innerWidth, h: innerHeight,
                sx: scrollX, sy: scrollY,
                pw: document.documentElement.scrollWidth,
                ph: document.documentElement.scrollHeight
            })
        ''')
        return json.loads(info)
    except Exception:
        return {
            "url": page.url or "", "title": page.title() or "",
            "w": 0, "h": 0, "sx": 0, "sy": 0, "pw": 0, "ph": 0,
        }


# ── iframe switching ─────────────────────────────────────────────────────

def find_iframe_target(context, url_substr: str) -> Optional[str]:
    try:
        targets = context.browser.new_cdp_session(context.pages[0]).send("Target.getTargets")
        for t in targets.get("targetInfos", []):
            if t.get("type") == "iframe" and url_substr in t.get("url", ""):
                return t.get("targetId")
    except Exception:
        pass
    return None


# ── interaction-skills ──────────────────────────────────────────────────

def load_interaction_skill(skill_name: str) -> Optional[str]:
    base = Path(__file__).parent.parent / "interaction-skills"
    path = base / skill_name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None

def list_interaction_skills() -> List[str]:
    base = Path(__file__).parent.parent / "interaction-skills"
    if not base.exists():
        return []
    return sorted([p.name for p in base.glob("*.md")])


# ── File upload ─────────────────────────────────────────────────────────

def prepare_upload(page, selector: str, file_path: str) -> bool:
    try:
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            print("[upload] File not found: " + file_path)
            return False
        page.set_input_files(selector, file_path)
        return True
    except Exception as e:
        print("[upload] Set file failed (" + selector + "): " + str(e))
        return False


# ── File download ───────────────────────────────────────────────────────

def _infer_filename(url: str, suggested: str) -> str:
    if suggested and suggested.strip():
        return suggested.strip()
    parsed = urlparse(url)
    name = os.path.basename(parsed.path)
    if name and "." in name:
        return name
    return "download_" + str(int(time.time()))

def _unique_path(save_dir: str, filename: str) -> str:
    save_dir = os.path.abspath(save_dir)
    base, ext = os.path.splitext(filename)
    path = os.path.join(save_dir, filename)
    n = 1
    while os.path.exists(path):
        path = os.path.join(save_dir, base + "_" + str(n) + ext)
        n += 1
    return path

def handle_download(download, save_dir: str = None) -> Dict[str, Any]:
    if save_dir is None:
        save_dir = os.path.join(os.getcwd(), "downloads")
    os.makedirs(save_dir, exist_ok=True)

    filename = _infer_filename(download.url, download.suggested_filename)
    save_path = _unique_path(save_dir, filename)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(download.save_as(save_path))
        finally:
            loop.close()
    except Exception:
        try:
            dl_path = download.path()
            if dl_path and os.path.exists(dl_path):
                shutil.copy2(dl_path, save_path)
            else:
                raise RuntimeError("download.path() returned invalid result")
        except Exception as e2:
            raise RuntimeError("Download save failed: " + str(e2))

    return {
        "filename": os.path.basename(save_path),
        "saved_path": save_path,
        "size": os.path.getsize(save_path),
        "url": download.url,
    }

class DownloadHandler:
    def __init__(self, page, save_dir: str = None):
        self.page = page
        self.save_dir = save_dir or os.path.join(os.getcwd(), "downloads")
        self.results = []
        os.makedirs(self.save_dir, exist_ok=True)

    def _on_download(self, download):
        try:
            result = handle_download(download, save_dir=self.save_dir)
            self.results.append(result)
        except Exception as e:
            print("[DownloadHandler] Save failed: " + str(e))

    def setup(self):
        self.page.on("download", self._on_download)
        return self

    def wait_done(self, timeout=30.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.results:
                return self.results
            time.sleep(0.1)
        return self.results

    @property
    def download_path(self):
        return self.save_dir

class DownloadContext:
    def __init__(self, page, save_dir=None):
        self.page = page
        self.handler = DownloadHandler(page, save_dir)

    def __enter__(self):
        self.handler.setup()
        return self

    def __exit__(self, *args):
        pass

    @property
    def results(self):
        return self.handler.results

    def wait_done(self, timeout=30.0):
        return self.handler.wait_done(timeout)

def setup_download_listener(page, save_dir=None):
    handler = DownloadHandler(page, save_dir)
    handler.setup()
    return handler


# ── Dialog auto-handling ────────────────────────────────────────────────

class DialogHandler:
    def __init__(self, page, accept=True, dismiss_prompt=False, prompt_text=""):
        self.page = page
        self.accept = accept
        self.dismiss_prompt = dismiss_prompt
        self.prompt_text = prompt_text
        self._dialog_handled = 0
        self._last_dialog_message = ""

    def _on_dialog(self, dialog):
        self._dialog_handled += 1
        self._last_dialog_message = dialog.message
        try:
            if dialog.type == "beforeunload":
                dialog.dismiss()
                return
            if dialog.type == "prompt" and self.dismiss_prompt:
                dialog.dismiss()
            elif self.accept:
                if dialog.type == "prompt":
                    dialog.accept(self.prompt_text)
                else:
                    dialog.accept()
            else:
                dialog.dismiss()
        except Exception as e:
            print("[DialogHandler] Handle dialog failed: " + str(e))

    def setup(self):
        self.page.on("dialog", self._on_dialog)
        return self

    def close(self):
        try:
            self.page.remove_listener("dialog", self._on_dialog)
        except Exception:
            pass

    @property
    def dialogs_handled(self):
        return self._dialog_handled

    @property
    def last_message(self):
        return self._last_dialog_message

def setup_dialog_listener(page, accept=True, dismiss_prompt=False, prompt_text=""):
    handler = DialogHandler(page, accept=accept,
                            dismiss_prompt=dismiss_prompt,
                            prompt_text=prompt_text)
    return handler.setup()


# ── Self-Healing ────────────────────────────────────────────────────────

class SelfHealingToolWriter:
    BH_TOOLS_PATH = Path(__file__).resolve()

    def __init__(self):
        self._written_tools = []

    def validate_tool_name(self, name: str) -> bool:
        return name.isidentifier() and not name.startswith("_")

    def validate_code(self, code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def generate_function_code(self, name: str, params, body: str, doc: str = "") -> str:
        params_str = ", ".join(params)
        doc_str = "    " + chr(34)*3 + doc + chr(34)*3 + chr(10) if doc else ""
        body_lines = [("    " + line) for line in body.split("\n")]
        body_str = "\n".join(body_lines)
        return "\n\ndef " + name + "(" + params_str + "):\n" + doc_str + "\n" + body_str + "\n"

    def write_tool(self, tool_def) -> tuple:
        name = tool_def.get("name", "")
        params = tool_def.get("params", [])
        body = tool_def.get("body", "")
        doc = tool_def.get("doc", "")

        if not self.validate_tool_name(name):
            return False, "Invalid function name: " + name
        if not body.strip():
            return False, "Function body cannot be empty"

        func_code = self.generate_function_code(name, params, body, doc)

        if not self.validate_code(func_code):
            return False, "Generated code has syntax error"

        try:
            content = self.BH_TOOLS_PATH.read_text(encoding="utf-8")

            # Find LAST occurrence of __all__ = [ (not docstrings)
            all_start = content.rfind("__all__ = [")
            if all_start == -1:
                return False, "Cannot find __all__ block"

            # Find matching ] using bracket counting
            list_start = content.find("[", all_start)
            bracket_count = 0
            i = list_start
            while i < len(content):
                c = content[i]
                if c == "[":
                    bracket_count += 1
                elif c == "]":
                    bracket_count -= 1
                    if bracket_count == 0:
                        break
                i += 1
            list_end = i

            # Build new __all__ list with tool appended
            old_list = content[list_start + 1:list_end]
            trimmed = old_list.rstrip().rstrip(",").rstrip()
            new_list = trimmed + ',\n    "' + name + '",\n]'

            # Assemble: before __all__ + new func + __all__=[new list]
            new_content = content[:all_start] + func_code + "__all__ = [" + new_list + "\n"

            self.BH_TOOLS_PATH.write_text(new_content, encoding="utf-8")
            self._written_tools.append(tool_def)
            return True, "Tool '" + name + "' written to bh_tools.py"

        except Exception as e:
            return False, "Write failed: " + str(e)

    def reload_bh_tools(self) -> tuple:
        import importlib
        try:
            mod = sys.modules.get("bh_tools")
            if mod:
                importlib.reload(mod)
            return True, "bh_tools.py reloaded (full effect needs session restart)"
        except Exception as e:
            return False, "Reload failed: " + str(e)

    def list_written_tools(self):
        return list(self._written_tools)


# ── Exports ─────────────────────────────────────────────────────────────



def test_fetch_placeholder_v3(url: str):
    """Test placeholder tool"""

    return f'Fetched: {url}'






def test_fetch_placeholder_v3(url: str):
    """Test placeholder tool"""

    return f'Fetched: {url}'


def test_list_tool_v3():

    pass


def test_append_tool_v7():

    pass
__all__ = [
    "http_get",
    "http_get_batch",
    "dispatch_key",
    "is_internal_url",
    "get_tab_info",
    "find_iframe_target",
    "load_interaction_skill",
    "list_interaction_skills",
    "prepare_upload",
    "handle_download",
    "DownloadContext",
    "DownloadHandler",
    "setup_download_listener",
    "DialogHandler",
    "setup_dialog_listener",
    "SelfHealingToolWriter",
    "test_fetch_placeholder_v3",
    "test_list_tool_v3",
    "test_append_tool_v7",
]
