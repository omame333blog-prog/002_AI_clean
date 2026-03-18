---
name: 週次提出率
description: 日報の週次提出率（各週で提出対象者の80%以上が1回以上投稿）を集計し、月次でアナウンスする。卒業生・休会中を正しく除外し、複数部屋に対応する。
argument-hint: "[任意] YYYY-MM（指定月確認） / チャンネルID（1部屋取得）"
user-invocable: true
---

# 週次提出率（運用メモ）

## 目的

- 各お部屋ごとに「週次提出率80%以上」を達成しているかを確認
- 毎月1日に前月分をまとめてアナウンス

## ファイルと役割

- `export_logs.py`
  - Discordからログ取得
  - `nippou_logs/{チャンネル名}.txt` と `nippou_logs/{チャンネル名}_サマリー.txt` を生成
  - 卒業生・休会中を反映して提出率を計算
- `post_monthly_report.py`
  - `nippou_logs/*_サマリー.txt` を自動検出し、前月の週次提出率を集計してDiscordに投稿
- `report_feb_weekly.py`
  - 手動確認用の週次提出率レポート

## ルール（卒業生・休会中）

- 卒業生（提出義務なし）: `nippou_logs/卒業生リスト.txt`
- 休会中（提出義務なし）: `nippou_logs/休会中リスト.txt`
- サマリーでは必ず区分する
  - `未提出者（休会中を除く）`
  - `未提出者のうち休会中（リマインド対象外）`
  - `卒業生（対象外）`

## 1部屋ずつログ取得（推奨）

環境によっては全チャンネル一括取得が不安定なため、`TARGET_CHANNEL_ID` で1部屋ずつ取得できる。

```bash
cd /Users/kasaimami/002_AI_
source venv/bin/activate
TARGET_CHANNEL_ID=<チャンネルID> python export_logs.py
```

例:
- ホワイト: `1366955220420006070`
- パープル: `1366955268855955569`

## 月次アナウンス（毎月1日9:00・自動設定済み）

cron（自動設定済み）:

```cron
0 9 1 * * cd /Users/kasaimami/002_AI_ && /bin/bash -c 'source venv/bin/activate && set -a && source .discord_token && set +a && python post_monthly_report.py'
```

投稿先: `MONTHLY_ANNOUNCE_CHANNEL_ID = 1482931158714155008`（`#🤖おまめ使用中`）

## 提出率の集計仕様

- **当月のみ**で集計（累計ではない）
- `export_logs.py` が実行時の年月に一致するログ行のみを対象にする
- 月次レポートの分母は **サマリーの「提出対象者（休会中除く）」** の値を使用

## メンバー数の注意（月をまたぐ場合）

- 翌月の新メンバーがロールに追加される前（月中旬）にサマリーを確定しておく
- **毎月15日 9:00** に `export_logs.py` を自動実行（月中旬スナップショット）
- 月末に翌月メンバーを追加してもサマリーは上書きされないため、月次レポートは正確な分母で計算できる

## 全チャンネルID（export_logs.py の CHANNEL_IDS と同期）

その他は `export_logs.py` の `CHANNEL_IDS` を参照。全部屋分のログ・サマリーは `nippou_logs/` に保存済み。

## 注意

- Botトークンは `.discord_token`（gitignore済み）に保存。手動実行時は `set -a && source .discord_token && set +a` で読み込む。

