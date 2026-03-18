# 002_AI_ / Claude Code Guide

このリポジトリは **Discord日報ログの取得・集計・リマインド**を扱います。14部屋分のログ・サマリーを `nippou_logs/` に保存し、週次提出率・月次アナウンス・2週間未提出リマインドに利用する。

## 重要な前提（必ず守る）

- **秘密情報をコミットしない**
  - Discord Bot Token は **ファイル直書き禁止**
  - `export_logs.py` は `DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")` のみ使用
  - ローカル手動実行: `set -a && source .discord_token && set +a && python export_logs.py`
  - GitHub Actions では `DISCORD_TOKEN` を Repository Secret に登録して使用
- **提出義務の判定はファイルが正**
  - 卒業生（提出義務なし）: `nippou_logs/卒業生リスト.txt`
  - 休会中（提出義務なし）: `nippou_logs/休会中リスト.txt`

## 主なスクリプト（002_AI_ 直下）

| ファイル | 役割 |
|----------|------|
| `export_logs.py` | Discordからログ取得＋サマリー生成。`TARGET_CHANNEL_ID` で1部屋ずつ取得可。 |
| `post_monthly_report.py` | 前月の週次提出率を全サマリーから集計しDiscordに1通投稿。 |
| `post_weekly_remind.py` | 2週間以上未提出者をサマリーから集計しDiscordにリマインド投稿。 |
| `check_tantosha_activity.py` | 担当者が週1回以上返信・MVP発表しているかを集計。`--post` でDiscord投稿。 |
| `report_feb_weekly.py` | 指定月の週次提出率を手動確認用に集計。 |
| `run_export.sh` | `export_logs.py` のlaunchd/手動用ラッパー（cd＋venv＋token読み込み）。 |
| `run_weekly_remind.sh` | `post_weekly_remind.py` のlaunchd用ラッパー。 |
| `run_tantosha_check.sh` | `check_tantosha_activity.py --post` のlaunchd用ラッパー。 |
| `run_monthly_report.sh` | `post_monthly_report.py` のlaunchd用ラッパー。 |
| `run_export_all_rooms.sh` | 全チャンネル一括取得（環境により不安定な場合は `TARGET_CHANNEL_ID` で1部屋ずつ）。 |

## ディレクトリ

- `nippou_logs/`: ログとサマリー保存先
  - ログ: `{チャンネル名}.txt`（例: `❤️日報：レッド.txt`）
  - サマリー: `{チャンネル名}_サマリー.txt`
  - 卒業生リスト・休会中リストもここに配置

## サマリーの表示仕様（最重要）

サマリーには以下の区分を必ず分ける（混ぜない）。

- `未提出者（休会中を除く）`: **提出義務あり**で未提出（リマインド対象）
- `未提出者のうち休会中（リマインド対象外）`: 未提出だが休会中（リマインド対象外）
- `卒業生（対象外）`: 卒業生（提出義務なし）

## 1部屋ずつ安全にログを取る

14部屋まとめ取りは環境によって不安定なことがあるため、必要に応じて **`TARGET_CHANNEL_ID`** を使い「1部屋ずつ」取得する。

例（ホワイト）:

```bash
cd /Users/kasaimami/002_AI_
source venv/bin/activate
export DISCORD_TOKEN="あなたのBotトークン"   # 1行で " を閉じる
TARGET_CHANNEL_ID=1366955220420006070 python export_logs.py
```

全14部屋のチャンネルIDは `export_logs.py` の `CHANNEL_IDS` を参照。全部屋取得済みのログ・サマリーは `nippou_logs/` に保存されている。

## 自動化（GitHub Actions）

**Mac電源オフ・スリープ中でも動作する**ようにGitHub Actionsで自動化済み。
ワークフロー定義: `.github/workflows/`

| タイミング | ワークフロー | 内容 |
|-----------|-------------|------|
| 毎日 9:00 JST | `export-logs.yml` | 全14部屋ログ取得＋サマリー更新＋自動コミット |
| 毎週月曜 9:30 JST | `weekly-remind.yml` | 2週間以上未提出者リマインド投稿 |
| 毎週金曜 9:00 JST | `tantosha-check.yml` | 担当者活動チェック（返信・MVP）投稿 |
| 毎月1日 9:00 JST | `monthly-report.yml` | 前月の週次提出率アナウンス |
| 毎月15日 9:00 JST | `export-logs-mid.yml` | 月中旬サマリー確定（翌月メンバー混入防止） |
| 毎月2日 9:05 JST | `list-reminder.yml` | 卒業生・休会中リスト更新リマインド |

- `DISCORD_TOKEN` は GitHub Repository Secret に登録済み（Settings → Secrets → Actions）
- Discordへの投稿先は `#🤖おまめ使用中`（ID: `1482931158714155008`）
- launchd（ローカル）も並行設定済み（`~/Library/LaunchAgents/com.kasaimami.*`）。ただしMacスリープ中は動作しない

### 手動実行（緊急時）
```bash
cd /Users/kasaimami/002_AI_
set -a && source .discord_token && set +a && python export_logs.py
```

## 担当者活動チェック仕様

`check_tantosha_activity.py` が各部屋の担当者の活動を週単位で集計する。

- **返信チェック**: 担当者のメッセージが1件以上あれば✅。ただし `<@&ロールID>` を含む全員宛お知らせ（交流会・MVP発表等）は除外する
- **MVP発表チェック**: 誰かのメッセージに「MVPおめでとう」または担当者の「MVP」+「発表/👑」があれば✅
- **担当者マッピング**: スクリプト内の `DEFAULT_TANTOSHA` で定義。`nippou_logs/担当者設定.txt` で上書き可

| 部屋 | 担当者（Discord表示名） |
|------|------------------------|
| ❤️レッド | おまめ_運営 |
| 🤍ホワイト | リリ_運営 |
| 💜パープル | ちーず_運営 |
| 💚グリーン | カエ_運営 |
| 🩷ピンク | ともも_運営 |
| 🖤ブラック | おおなろ_運営 |
| 🧡オレンジ | あん_運営 |
| 🤎ブラウン | ものこ_運営 |
| 💙ブルー | 宮坂育未_運営 |
| 🩵みずいろ | ふーじえ_運営 |
| 💛イエロー | まりっか_ 運営（スペースあり） |
| 🩶グレー | ちひろ_運営 |
| 🐶いぬ | とも_運営 |
| 🐑ひつじ | こぱん_運営 |

> ⚠️ 担当者のDiscord表示名は完全一致が必要。スペースや絵文字の違いに注意（例: `まりっか_ 運営` は `_` と `運` の間にスペースあり）

## サマリーの提出率仕様

- **当月のみ**でカウント（2月以降累計ではない）
- `export_logs.py` は実行時の年月（`YYYY-MM`）に一致するログ行のみを集計対象にする
- 月が変わると自動的に翌月分で再集計される

## CHANNEL_TO_ROLEの注意点

Discordのロール名と完全一致が必要。過去に以下がずれていた（修正済み）:
- 絵文字の違い: `💗`→`🩷`（ピンク）、`🤍`→`🩶`（グレー）
- ダッシュの違い: 半角`-`→全角`−`（いぬ・ひつじ）

ロール名確認コマンド:
```bash
python - <<'EOF'
import asyncio, discord, os
async def main():
    client = discord.Client(intents=discord.Intents.default())
    @client.event
    async def on_ready():
        for g in client.guilds:
            for r in sorted(g.roles, key=lambda r: r.name):
                if "部屋" in r.name or "いぬ" in r.name or "ひつじ" in r.name:
                    print(r.name)
        await client.close()
    await client.start(os.environ["DISCORD_TOKEN"])
asyncio.run(main())
EOF
```

