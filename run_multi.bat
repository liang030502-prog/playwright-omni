@echo off
REM Multi-task launcher for Playwright-Omni
setlocal enabledelayedexpansion

set "PYTHON=D:\python312\python.exe"
set "SCRIPT_DIR=%~dp0"

cd /d "%SCRIPT_DIR%scripts"

echo ========================================================
echo  赛题5: 宠物友好工作环境
echo ========================================================
"%PYTHON%" -X utf8 cli.py --url "https://duckduckgo.com/?q=Nestl%C3%A9+pet+friendly+workplace+policy+office+2025" --goal "找到雀巢宠物友好型工作环境相关信息，包括政策、员工福利、办公室设计等" --max-steps 5 --headless --verbose

echo ========================================================
echo  赛题5-2: 雀巢Purina
echo ========================================================
"%PYTHON%" -X utf8 cli.py --url "https://duckduckgo.com/?q=Nestl%C3%A9+Purina+pet+care+strategy+2025+2026" --goal "找到Purina宠物护理品牌相关信息，包括市场策略、产品创新、企业社会责任等" --max-steps 5 --headless --verbose

echo ========================================================
echo  赛题6: Health Science
echo ========================================================
"%PYTHON%" -X utf8 cli.py --url "https://duckduckgo.com/?q=Nestl%C3%A9+Health+Science+nutrition+strategy+2025+2026" --goal "找到Nestl%C3%A9 Health Science营养改善相关信息，包括战略规划、产品线、市场动态等" --max-steps 5 --headless --verbose

echo ========================================================
echo  赛题6-2: 特医食品
echo ========================================================
"%PYTHON%" -X utf8 cli.py --url "https://duckduckgo.com/?q=Nestl%C3%A9+Health+Science+medical+nutrition+supplements+2025" --goal "找到雀巢特医食品和营养补充剂相关信息，包括特殊医学食品、营养保健品、市场准入等" --max-steps 5 --headless --verbose

endlocal