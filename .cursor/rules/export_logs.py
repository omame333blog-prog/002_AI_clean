"""
→ 002_AI_/export_logs.py を実行してください。

このファイルは互換用。本番は 002_AI_ 直下の export_logs.py を使用。
"""
import os
import sys
import subprocess

# .cursor/rules/export_logs.py → 002_AI_ を取得（3段階上）
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MAIN = os.path.join(_ROOT, "export_logs.py")
if os.path.exists(_MAIN):
    os.chdir(_ROOT)
    env = os.environ.copy()
    env["PYTHONPATH"] = _ROOT
    sys.exit(subprocess.call([sys.executable, _MAIN], env=env))
else:
    print("エラー: 002_AI_/export_logs.py が見つかりません")
    sys.exit(1)
