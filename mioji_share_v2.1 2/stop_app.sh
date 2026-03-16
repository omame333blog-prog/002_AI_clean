#!/bin/bash
# Moji Booster アプリ停止スクリプト

lsof -ti :7860 | xargs kill -9 2>/dev/null
echo "✅ アプリを停止しました"



