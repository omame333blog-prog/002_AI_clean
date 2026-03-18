---
name: 日報リマインド
description: 日報の2週間以上未提出者をサマリーから集計し、週1回Discordにリマインド投稿する。卒業生・休会中は対象外。
argument-hint: "[任意] --dry-run（投稿せず表示）"
user-invocable: true
---

# 日報リマインド（.claude 運用メモ）

## 目的

- **2週間（14日）以上未提出**のメンバーを洗い出し、週1回Discordでリマインドする
- 対象はサマリーの「**未提出者（休会中を除く）**」と、ログ上で最終提出が14日より前の人（卒業生・休会中は除外）

## データの場所

- サマリー: `nippou_logs/{チャンネル名}_サマリー.txt`
  - 見出し `## 未提出者（休会中を除く）` 以下をリマインド対象として参照
- 卒業生: `nippou_logs/卒業生リスト.txt`
- 休会中: `nippou_logs/休会中リスト.txt`

## スクリプト

- **`post_weekly_remind.py`**
  - 全サマリーを自動検出し、要リマインドを1通にまとめてDiscordに投稿
  - トークン: 環境変数 `DISCORD_TOKEN`（直書き禁止）
  - 送信先: `REMIND_CHANNEL_ID = 1482931158714155008`（`#🤖おまめ使用中`）

## 実行例

```bash
cd /Users/kasaimami/002_AI_
source venv/bin/activate
set -a && source .discord_token && set +a
python post_weekly_remind.py           # 投稿する
python post_weekly_remind.py --dry-run # 投稿せず内容のみ表示
```

## cron（毎週月曜 9:30・自動設定済み）

```cron
30 9 * * 1 cd /Users/kasaimami/002_AI_ && /bin/bash -c 'source venv/bin/activate && set -a && source .discord_token && set +a && python post_weekly_remind.py'
```

## 注意

- ログ・サマリーが古いと対象がずれる。先に `export_logs.py` で最新化する（月曜9:00のcronで自動実行）。
- ログ取得は `export_logs.py`、リマインド投稿は `post_weekly_remind.py` を使用。
