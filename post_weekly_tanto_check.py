"""
週1回「日報担当の返信」と「MVP発表」の有無をDiscordにアナウンスするスクリプト。
毎週月曜に実行し、先週の「担当者が1回以上返信したか」「MVPを出したか」を集計して投稿する。

実行:
  cd /Users/kasaimami/002_AI_ && source venv/bin/activate && python post_weekly_tanto_check.py
  python post_weekly_tanto_check.py --dry-run   # 投稿せず内容のみ表示

cron例（毎週月曜 9:00。リマインドのあとがおすすめ）:
  0 9 * * 1 cd /Users/kasaimami/002_AI_ && source venv/bin/activate && python post_weekly_tanto_check.py

設定:
  - 日報担当リスト: nippou_logs/日報担当リスト.txt（チャンネル名=担当者表示名）
  - TANTO_ANNOUNCE_CHANNEL_ID: 投稿先DiscordチャンネルID（None なら REMIND_CHANNEL_ID を参照）
  - DISCORD_TOKEN: 環境変数または export_logs.py のトークン
"""
import argparse
import asyncio
import os
import re
import sys
from datetime import datetime, timezone, timedelta

_BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE)
import discord

# ★担当・MVPチェックの投稿先。None なら post_weekly_remind の REMIND_CHANNEL_ID を流用
TANTO_ANNOUNCE_CHANNEL_ID = 1482931158714155008


def _get_discord_token() -> str:
    t = os.environ.get("DISCORD_TOKEN", "").strip()
    if t:
        return t
    path = os.path.join(_BASE, "export_logs.py")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            m = re.search(r'DISCORD_TOKEN\s*=\s*["\']([^"\']+)["\']', f.read())
            if m:
                return m.group(1)
    return ""


def _get_remind_channel_id() -> int | None:
    path = os.path.join(_BASE, "post_weekly_remind.py")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            m = re.search(r"REMIND_CHANNEL_ID\s*=\s*(\d+)", f.read())
            if m:
                return int(m.group(1))
    return None


DISCORD_TOKEN = _get_discord_token()
ANNOUNCE_CHANNEL_ID = TANTO_ANNOUNCE_CHANNEL_ID or _get_remind_channel_id()

NIPPOU_DIR = os.path.join(_BASE, "nippou_logs")
TANTO_LIST_FILE = os.path.join(NIPPOU_DIR, "日報担当リスト.txt")
LOG_LINE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(.+?):\s+(.*)$", re.DOTALL)
MVP_MARKERS = ("MVPを発表", "今週のMVP")


def load_tanto_list() -> dict[str, list[str]]:
    """チャンネル名 -> 担当者表示名のリスト。# と空行はスキップ。"""
    out: dict[str, list[str]] = {}
    if not os.path.isfile(TANTO_LIST_FILE):
        return out
    with open(TANTO_LIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            channel_name, right = line.split("=", 1)
            channel_name = channel_name.strip()
            names = [n.strip() for n in right.split(",") if n.strip()]
            if channel_name and names:
                out[channel_name] = names
    return out


def discover_channel_pairs() -> list[tuple[str, str, str]]:
    """(ログパス, サマリーパス, チャンネル表示名) のリスト。"""
    pairs: list[tuple[str, str, str]] = []
    nippou_dir = NIPPOU_DIR
    if not os.path.isdir(nippou_dir):
        nippou_dir = os.path.join(os.getcwd(), "nippou_logs")
    if not os.path.isdir(nippou_dir):
        return pairs
    for name in sorted(os.listdir(nippou_dir)):
        if not name.endswith("_サマリー.txt"):
            continue
        log_name = name.replace("_サマリー.txt", ".txt")
        summary_path = os.path.join(nippou_dir, name)
        log_path = os.path.join(nippou_dir, log_name)
        channel_name = name.replace("_サマリー.txt", "")
        if os.path.isfile(log_path):
            pairs.append((log_path, summary_path, channel_name))
    return pairs


def parse_log_lines_in_range(
    log_path: str,
    range_start: datetime,
    range_end: datetime,
) -> list[tuple[datetime, str, str]]:
    """ログから指定期間内の行を (日時, 名前, 本文) で返す。"""
    result: list[tuple[datetime, str, str]] = []
    if not os.path.isfile(log_path):
        return result
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            m = LOG_LINE_RE.match(line.strip())
            if not m:
                continue
            date_str, name, body = m.group(1), m.group(2).strip(), (m.group(3) or "").strip()
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                if range_start <= dt <= range_end:
                    result.append((dt, name, body))
            except ValueError:
                continue
    return result


def run_tanto_check_for_channel(
    log_path: str,
    channel_name: str,
    tanto_names: list[str],
    range_start: datetime,
    range_end: datetime,
) -> tuple[str, dict[str, int], bool]:
    """
    1チャンネル分の「担当者ごとの投稿数」と「MVP発表の有無」を返す。
    返値: (channel_name, {担当者名: 投稿数}, MVP発表したか)
    """
    rows = parse_log_lines_in_range(log_path, range_start, range_end)
    counts: dict[str, int] = {t: 0 for t in tanto_names}
    mvp_done = False
    for _dt, name, body in rows:
        if name in counts:
            counts[name] += 1
        if any(m in body for m in MVP_MARKERS):
            mvp_done = True
    return channel_name, counts, mvp_done


def build_announcement(
    results: list[tuple[str, dict[str, int], bool]],
    week_start: datetime,
    week_end: datetime,
) -> str:
    """Discordに送る本文を組み立てる。"""
    start_str = week_start.strftime("%m/%d")
    end_str = week_end.strftime("%m/%d")
    lines = [
        "**【週次】日報担当チェック（返信・MVP）**",
        "",
        f"対象週: {start_str}（月）〜 {end_str}（日）",
        "",
    ]
    for channel_name, counts, mvp_done in results:
        lines.append(f"・**{channel_name}**")
        for name, n in counts.items():
            if n >= 1:
                lines.append(f"  返信: {name} ✅")
            else:
                lines.append(f"  返信: {name} ⚠️")
        lines.append(f"  MVP: {'✅ 発表済み' if mvp_done else '⚠️ 未発表'}")
        lines.append("")
    lines.append("※ 上記は先週1週間のログに基づく集計です。")
    return "\n".join(lines)


async def post_to_discord(content: str, channel_id: int | None) -> bool:
    if not DISCORD_TOKEN:
        print("  [警告] DISCORD_TOKEN が未設定です")
        return False
    if not channel_id:
        print("  [警告] 投稿先チャンネルIDが未設定です（TANTO_ANNOUNCE_CHANNEL_ID / REMIND_CHANNEL_ID）")
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
            print(f"  → #{ch.name} に担当チェックを送信しました")
        await client.close()

    await client.start(DISCORD_TOKEN)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="日報担当の週次返信・MVPチェックをDiscordに投稿")
    parser.add_argument("--dry-run", action="store_true", help="投稿せず内容のみ表示")
    args = parser.parse_args()

    # 先週 = 先週月曜 00:00 〜 先週日曜 23:59（今日が月曜なら昨日までが先週日曜）
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_sunday = today - timedelta(days=1)
    last_monday = last_sunday - timedelta(days=6)
    range_start = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    range_end = last_sunday.replace(hour=23, minute=59, second=59, microsecond=999_999)

    tanto_by_channel = load_tanto_list()
    if not tanto_by_channel:
        print("日報担当リスト（nippou_logs/日報担当リスト.txt）に1件も登録がありません。")
        sys.exit(1)

    pairs = discover_channel_pairs()
    channel_to_path: dict[str, str] = {name: log_path for log_path, _sp, name in pairs}

    results: list[tuple[str, dict[str, int], bool]] = []
    for channel_name, tanto_names in sorted(tanto_by_channel.items()):
        log_path = channel_to_path.get(channel_name)
        if not log_path:
            print(f"  [スキップ] {channel_name} のログファイルが見つかりません")
            continue
        ch_name, counts, mvp_done = run_tanto_check_for_channel(
            log_path, channel_name, tanto_names, range_start, range_end
        )
        results.append((ch_name, counts, mvp_done))

    if not results:
        print("集計対象のチャンネルがありません。")
        sys.exit(1)

    content = build_announcement(results, last_monday, last_sunday)
    print("--- 担当チェック文（予定） ---")
    print(content)
    print("---")

    if args.dry_run:
        print("（--dry-run のため投稿しません）")
        return

    channel_id = ANNOUNCE_CHANNEL_ID
    if channel_id is None:
        print("TANTO_ANNOUNCE_CHANNEL_ID または post_weekly_remind.py の REMIND_CHANNEL_ID を設定してください。")
        return

    asyncio.run(post_to_discord(content, int(channel_id)))


if __name__ == "__main__":
    main()
