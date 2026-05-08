# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-05-08

### Added
- **SelfHealingToolWriter** (`bh_tools.py`): Context-aware playwright action generator that reads actual function signatures and generates valid `page.*` calls. Eliminates hardcoded action strings.
- **preflight_check.py** 8-item check: Import resolution, CDP availability, UserDataDir mode, device forced to CPU, `local_files_only=True`, cache_dir path, executable path output, preflight state persistence.
- **README**: Full architecture diagram, feature list, directory structure.

### Fixed
- **bh_tools.py**: `doc_str` generation uses tuple wrap for multi-line docs; `__all__` update uses `rfind` + parenthesis counting to avoid regex matching function body `]`.
- **preflight_check.py**: `r"""` raw string docstring for Windows Python 3.13 compatibility (`\U` unicode escape sequence issue).

### Changed
- **orchestrator.py**: Updated to use SelfHealingToolWriter for all playwright action generation.
- **bh_tools.py**: `COORD_CLICK` now accepts explicit `button` param (`left`/`right`/`middle`).

## [1.0.0] - 2026-04-28

### Added
- Initial release: Playwright + OmniParser (YOLO + BLIP2) + VisionDecision (LLM) + BrowserAgent
- Full test suite: 147 tests across 15 test files
- Interaction skills: dialog, download, tab, connection handlers
- CLI support: single task and multi-task batch mode
- Device selector: CPU/GPU auto-recommendation based on URL complexity
