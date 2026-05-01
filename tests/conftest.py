# conftest.py — pytest 全局配置
import sys
import os
from pathlib import Path

# 确保 scripts/ 在 sys.path 中（bh_tools 等模块依赖这个路径）
_scripts = Path(__file__).parent.parent / "scripts"
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))
