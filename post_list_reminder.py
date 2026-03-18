"""
毎月2日に「卒業生リスト・休会中リストを更新してください」とDiscordに投稿するスクリプト。
（1日は post_monthly_report.py が動くので2日にずらす）

実行:
  cd /Users/kasaimami/002_AI_ && source venv/bin/activate && python post_list_reminder.py
  python post_list_reminder.py --dry-run   # 投稿せず内容のみ表示

cron例（毎月2日 9:05）:
  5 9 2 * * cd /Users/kasaimami/002_AI_ && /bin/bash -c 'source venv/bin/activate && set -a && source .discord_token && set +a && python post_list_reminder.py'
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

import discord

CHANNEL_ID = 1482931158714155008  # #🤖おまめ使用中

def _get_discord_token() -> str:
    t = os.environ.get("DISCORD_TOKEN", "").strip()
    if t:
        return t
    return ""

DISCORD_TOKEN = _get_discord_token()


def build_message() -> str:
    now = datetime.now(timezone.utc).astimezone()
    return (
        f"**【{now.year}年{now.month}月 月初リスト更新リマインド】**\n"
        "\n"
        "月初のメンバー整理をお願いします ✅\n"
        "\n"
        "**確認・更新するファイル（`nippou_logs/` 内）**\n"
        "1. `卒業生リスト.txt` — 先月卒業した方を追加\n"
        "2. `休会中リスト.txt` — 新規休会・復帰を反映\n"
        "\n"
        "**更新後にやること**\n"
        "```\n"
        "cd /Users/kasaimami/002_AI_\n"
        "set -a && source .discord_token && set +a\n"
        "python export_logs.py\n"
        "```\n"
        "（全14部屋のサマリーが最新メンバーで再生成されます）"
    )


async def post_to_discord(content: str, dry_run: bool) -> None:
    if dry_run:
        print("--- 投稿予定メッセージ ---")
        print(content)
        print("（--dry-run のため投稿しません）")
        return

    if not DISCORD_TOKEN:
        print("[警告] DISCORD_TOKEN が未設定です（.discord_token を source してください）")
        sys.exit(1)

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        ch = client.get_channel(CHANNEL_ID)
        if ch is None:
            print(f"[警告] チャンネルID {CHANNEL_ID} が見つかりません")
        else:
            await ch.send(content)
            print(f"→ #{ch.name} にリマインドを送信しました")
        await client.close()

    await client.start(DISCORD_TOKEN)


def main() -> None:
    parser = argparse.ArgumentParser(description="月初リスト更新リマインドをDiscordに投稿")
    parser.add_argument("--dry-run", action="store_true", help="投稿せず内容のみ表示")
    args = parser.parse_args()

    content = build_message()
    asyncio.run(post_to_discord(content, args.dry_run))


if __name__ == "__main__":
    main()
