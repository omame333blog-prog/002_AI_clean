#!/bin/bash
# Moji Booster アプリ起動スクリプト
# Cursorを終了してもアプリが動き続きます

cd "$(dirname "$0")"
source venv/bin/activate

# 既存のプロセスを停止
lsof -ti :7860 | xargs kill -9 2>/dev/null

# アプリを起動（nohupでデタッチ）
nohup python -m app.main > app.log 2>&1 &

echo "✅ アプリを起動しました！"
echo "📋 ログファイル: $(pwd)/app.log"
echo "🌐 アクセスURL: http://127.0.0.1:7860"
echo ""
echo "アプリを停止するには:"
echo "  lsof -ti :7860 | xargs kill -9"
echo ""













