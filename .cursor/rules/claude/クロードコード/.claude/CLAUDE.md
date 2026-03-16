# クロードコード プロジェクト設定

## プロジェクト概要
Discordの日報ログを解析して、メンバーの提出状況を可視化・リマインドするツール群。

## ディレクトリ構成
```
クロードコード/
├── Discord/
│   ├── 3月投稿分              # Discordエクスポートログ（テキスト）
│   ├── analyze_reports.py     # 提出状況ヒートマップ生成
│   ├── generate_reminder.py   # リマインドHTML生成
│   ├── 日報提出率_スキル図.png # 出力チャート
│   └── リマインド一覧.html    # 出力リマインドページ
└── .claude/
    ├── CLAUDE.md
    ├── commands/              # スラッシュコマンド（スキル）
    ├── agents/                # サブエージェント
    └── rules/                 # ルール
```

## Python実行環境
- Python 3.14（`/opt/homebrew/bin/python3`）
- `distutils` 削除済み → `japanize_matplotlib` 使用不可
- パッケージインストール：`pip3 install --break-system-packages`
- 日本語フォント：`plt.rcParams['font.family'] = 'Hiragino Sans'`

## スクリプト実行方法
```bash
# ヒートマップ生成
cd '/Users/kasaimami/Documents/アンチグラビティ/クロードコード/Discord3月/'
python3 analyze_reports.py

# リマインドHTML生成
python3 generate_reminder.py
```

## コミュニケーション規約
- 日本語で回答する
- 専門用語を使わず、わかりやすく説明する
- 結論から先に伝える
