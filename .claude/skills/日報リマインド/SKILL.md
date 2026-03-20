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
  - 部屋の表示順: `CHANNEL_ORDER` で定義（`export_logs.py` の `CHANNEL_IDS` と同順）

## Discord メッセージフォーマット

```
## ❤️日報：レッド（要リマインド 3名）
🚨 名前A: 未提出
🚨 名前B: 最終 2026-02-01（46日経過）
名前C: 最終 2026-03-05（14日経過）
```

- チャンネルヘッダー: `## チャンネル名（要リマインド N名）`
- 未提出 or 30日以上: 先頭に `🚨`
- メンバー行はインデントなし（フラット）

## ランクサフィックス（_R/_P/_S/_G/_B）の扱い

メンバーのランクは途中で変わることがある（例: `_R` → `_P`）。
ログ上の名前とサマリー上の名前が一致しなくなるため、**ベース名（`_` より前）で突き合わせる**。

- 実装: `key_to_last` インデックス（ベース名→最新日付）でフォールバック照合
- 誤判定例: `つかちゃん_R`（ログ）と `つかちゃん_P`（サマリー）→ ベース名 `つかちゃん` で一致

## 卒業生リストの @username 形式

`post_weekly_remind.py` の `load_graduate_list()` は **半角 `@` / 全角 `＠` の両方**に対応。
`表示名 @username` または `表示名 ＠username` と書かれた行は、表示名部分のみ卒業セットに追加する。

## 実行例

```bash
cd /Users/kasaimami/002_AI_
source venv/bin/activate
set -a && source .discord_token && set +a
python post_weekly_remind.py           # 投稿する
python post_weekly_remind.py --dry-run # 投稿せず内容のみ表示
```

## GitHub Actions（毎週月曜 9:30 JST・自動設定済み）

`.github/workflows/weekly-remind.yml` で自動実行。Macのスリープ・電源オフ中でも動作する。

## 注意

- ログ・サマリーが古いと対象がずれる。先に `export_logs.py` で最新化する（月曜9:00のActionsで自動実行）。
- ログ取得は `export_logs.py`、リマインド投稿は `post_weekly_remind.py` を使用。
