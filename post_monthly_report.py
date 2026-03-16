"""
毎月末の「週次提出率」アナウンスをDiscordに投稿するスクリプト。
前月の週ごと提出率（80%以上達成週数）を集計し、指定チャンネルに投稿する。

実行:
  cd /Users/kasaimami/002_AI_ && source venv/bin/activate && python post_monthly_report.py
  python post_monthly_report.py --dry-run          # 投稿せず内容のみ表示
  python post_monthly_report.py --month 2026-02   # 指定月で集計

cron例（毎月1日 9:00に前月分を発表）:
  0 9 1 * * cd /Users/kasaimami/002_AI_ && source venv/bin/activate && python post_monthly_report.py

設定:
  - MONTHLY_ANNOUNCE_CHANNEL_ID: アナウンスを送るDiscordチャンネルID
  - DISCORD_TOKEN: 環境変数で設定するか、export_logs.py と同じBotトークンをここに記載
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

_BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE)
import discord

from report_feb_weekly import run_monthly_weekly_report

# ★週次提出率アナウンスを送るDiscordチャンネルID。None なら送信しない（--dry-run 時は無視可）
# チャンネルを右クリック → リンクをコピー → 末尾の数字がID
MONTHLY_ANNOUNCE_CHANNEL_ID = 1482931158714155008  # 例: 1234567890123456789

# ★Botトークン。環境変数 DISCORD_TOKEN 優先。未設定なら export_logs.py から読み込む（import はしない）
def _get_discord_token() -> str:
    t = os.environ.get("DISCORD_TOKEN", "").strip()
    if t:
        return t
    _path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "export_logs.py")
    if os.path.isfile(_path):
        import re
        with open(_path, "r", encoding="utf-8") as f:
            m = re.search(r'DISCORD_TOKEN\s*=\s*["\']([^"\']+)["\']', f.read())
            if m:
                return m.group(1)
    return ""

DISCORD_TOKEN = _get_discord_token()


def discover_channel_pairs() -> list[tuple[str, str]]:
    """nippou_logs 内の *_サマリー.txt から (ログパス, サマリーパス) のリストを返す。"""
    pairs: list[tuple[str, str]] = []
    # nippou_logs の場所: スクリプトと同じディレクトリ、なければカレントディレクトリ（cron 用）
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    nippou_dir = os.path.join(_script_dir, "nippou_logs")
    if not os.path.isdir(nippou_dir):
        nippou_dir = os.path.join(os.getcwd(), "nippou_logs")
    if not os.path.isdir(nippou_dir):
        return pairs
    for name in sorted(os.listdir(nippou_dir)):
        if not name.endswith("_サマリー.txt"):
            continue
        # 例: "❤️日報：レッド_サマリー.txt" → ログは "❤️日報：レッド.txt"
        log_name = name.replace("_サマリー.txt", ".txt")
        summary_path = os.path.join(nippou_dir, name)
        log_path = os.path.join(nippou_dir, log_name)
        if os.path.isfile(log_path):
            pairs.append((log_path, summary_path))
    return pairs


def build_announcement_text(
    year: int, month: int, results: list[tuple[str, int, int, int, list]]
) -> str:
    """アナウンス本文を組み立てる。"""
    month_name = f"{year}年{month}月"
    lines = [
        f"**【{month_name} 週次提出率のお知らせ】**",
        "",
        "今月の週次提出率（提出対象者の80%以上がその週に1回以上投稿）の達成状況です。",
        "",
    ]
    for channel_name, target_count, achieved, total_weeks, details in results:
        if achieved == total_weeks:
            status = "✅ 達成"
        else:
            status = f"⚠️ {achieved}/{total_weeks}週達成（あと{total_weeks - achieved}週で達成）"
        lines.append(f"・**{channel_name}**: {achieved}/{total_weeks}週 {status}")
    lines.extend([
        "",
        "※ 提出対象者数は当月時点のサマリーに基づいています。",
        "※ 休会中の方は提出対象から除いています。",
    ])
    return "\n".join(lines)


async def post_to_discord(content: str, channel_id: int | None) -> bool:
    """Discordに1メッセージ送信。"""
    if not DISCORD_TOKEN:
        print("  [警告] DISCORD_TOKEN が未設定です（export_logs.py または環境変数）")
        return False
    if not channel_id:
        print("  [警告] MONTHLY_ANNOUNCE_CHANNEL_ID が未設定です")
        return False

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        ch = client.get_channel(channel_id)
        if ch is None:
            print(f"  [警告] チャンネルID {channel_id} が見つかりません")
        else:
            await ch.send(content)
            print(f"  → #{ch.name} にアナウンスを送信しました")
        await client.close()

    await client.start(DISCORD_TOKEN)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="毎月末の週次提出率アナウンスをDiscordに投稿")
    parser.add_argument("--dry-run", action="store_true", help="投稿せず、アナウンス文のみ表示")
    parser.add_argument("--month", type=str, metavar="YYYY-MM", help="集計対象月（省略時は前月）")
    args = parser.parse_args()

    # 対象月
    if args.month:
        try:
            y, m = map(int, args.month.split("-"))
            year, month = y, m
        except (ValueError, AttributeError):
            print("--month は YYYY-MM 形式で指定してください")
            sys.exit(1)
    else:
        now = datetime.now(timezone.utc).astimezone()
        if now.month == 1:
            year, month = now.year - 1, 12
        else:
            year, month = now.year, now.month - 1

    pairs = discover_channel_pairs()
    if not pairs:
        print("nippou_logs にログ・サマリーのペアが見つかりません。")
        sys.exit(1)

    results: list = []
    for log_path, summary_path in pairs:
        r = run_monthly_weekly_report(log_path, summary_path, year, month)
        if r is not None:
            results.append(r)
        else:
            print(f"  [スキップ] {os.path.basename(log_path)} の集計に失敗しました")

    if not results:
        print("集計結果が1件もありません。")
        sys.exit(1)

    content = build_announcement_text(year, month, results)
    print("--- アナウンス文（予定） ---")
    print(content)
    print("---")

    if args.dry_run:
        print("（--dry-run のため投稿しません）")
        return

    channel_id = MONTHLY_ANNOUNCE_CHANNEL_ID
    if channel_id is None:
        print("MONTHLY_ANNOUNCE_CHANNEL_ID を設定するとDiscordに投稿できます。")
        return

    asyncio.run(post_to_discord(content, int(channel_id)))


if __name__ == "__main__":
    main()
