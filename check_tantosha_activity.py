"""
担当者活動チェックスクリプト
各部屋の日報担当者が週1回以上返信しているか、MVPを発表しているかを集計して報告する。

実行:
  cd /Users/kasaimami/002_AI_ && python check_tantosha_activity.py
  python check_tantosha_activity.py --weeks 4       # 直近4週分
  python check_tantosha_activity.py --month 2026-02 # 特定月
  python check_tantosha_activity.py --post          # Discordに投稿（直近1週）

cron例（毎週金曜 9:00）:
  0 9 * * 5 cd /Users/kasaimami/002_AI_ && /bin/bash -c 'source venv/bin/activate && set -a && source .discord_token && set +a && python check_tantosha_activity.py --post'

担当者の上書き:
  nippou_logs/担当者設定.txt に「チャンネル名: 担当者名」形式で記載
"""

import argparse
import asyncio
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import discord

_BASE = os.path.dirname(os.path.abspath(__file__))
NIPPOU_DIR = os.path.join(_BASE, "nippou_logs")
CONFIG_FILE = os.path.join(NIPPOU_DIR, "担当者設定.txt")

# 投稿先チャンネルID（#🤖おまめ使用中）
POST_CHANNEL_ID = 1482931158714155008

def _get_discord_token() -> str:
    t = os.environ.get("DISCORD_TOKEN", "").strip()
    if t:
        return t
    path = os.path.join(_BASE, ".discord_token")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                m = re.search(r'DISCORD_TOKEN=["\']?([^"\'\\s]+)', line)
                if m:
                    return m.group(1).strip()
    return ""

LOG_LINE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(.+?):\s+(.*)")

# ★デフォルト担当者マッピング（ログから自動推定）
DEFAULT_TANTOSHA = {
    "❤️日報：レッド":     "おまめ_運営",
    "🤍日報：ホワイト":   "リリ_運営",
    "💜日報：パープル":   "ちーず_運営",
    "💚日報：グリーン":   "カエ_運営",
    "🩷日報：ピンク":     "ともも_運営",
    "🖤日報：ブラック":   "おおなろ_運営",
    "🧡日報：オレンジ":   "あん_運営",
    "🤎日報：ブラウン":   "ものこ_運営",
    "💙日報：ブルー":     "宮坂育未_運営",
    "🩵日報：みずいろ":   "ふーじえ_運営",
    "💛日報：イエロー":   "まりっか_ 運営",
    "🩶日報：グレー":     "ちひろ_運営",
    "🐶日報：-いぬ-戌":  "とも_運営",
    "🐑日報：-ひつじ-未": "こぱん_運営",
}

CHANNEL_ORDER = list(DEFAULT_TANTOSHA.keys())


def load_config() -> dict[str, str]:
    """担当者設定.txt を読み込み、デフォルトマッピングを上書き。"""
    mapping = dict(DEFAULT_TANTOSHA)
    if not os.path.exists(CONFIG_FILE):
        return mapping
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                ch, tantosha = line.split(":", 1)
                mapping[ch.strip()] = tantosha.strip()
    return mapping


def get_week_start(dt: datetime) -> datetime:
    """その週の月曜日（00:00:00）を返す。"""
    return dt - timedelta(days=dt.weekday(), hours=dt.hour, minutes=dt.minute, seconds=dt.second, microseconds=dt.microsecond)


def parse_log(log_path: str) -> list[tuple[datetime, str, str]]:
    """ログを解析し (datetime, username, content) のリストを返す。"""
    result = []
    if not os.path.isfile(log_path):
        return result
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            m = LOG_LINE_RE.match(line.strip())
            if m:
                try:
                    dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    result.append((dt, m.group(2).strip(), m.group(3)))
                except ValueError:
                    pass
    return result


def analyze_channel_post(channel_name: str, tantosha: str,
                         reply_start, reply_end, mvp_start, mvp_end) -> dict:
    """
    --post モード専用: 返信とMVPで異なる期間を集計する。
    reply_start/end: 返信チェック期間（date オブジェクト）
    mvp_start/end:   MVP発表チェック期間（date オブジェクト）
    """
    log_path = os.path.join(NIPPOU_DIR, f"{channel_name}.txt")
    messages = parse_log(log_path)

    # 返信チェック（reply_start〜reply_end、全員宛お知らせ除外）
    reply_msgs = [
        (u, c) for dt, u, c in messages
        if reply_start <= dt.date() <= reply_end
        and tantosha and u == tantosha
        and "<@&" not in c
    ]

    # MVP発表チェック（mvp_start〜mvp_end）
    mvp_msgs = [(u, c) for dt, u, c in messages if mvp_start <= dt.date() <= mvp_end]
    mvp_congrats = any("MVPおめでとう" in c or "MVP おめでとう" in c for _, c in mvp_msgs)
    mvp_announce = any("MVP" in c and ("発表" in c or "👑" in c) for _, c in mvp_msgs)

    return {
        "replied": len(reply_msgs) > 0,
        "reply_count": len(reply_msgs),
        "mvp_announced": mvp_congrats or mvp_announce,
    }


def analyze_channel(channel_name: str, tantosha: str, weeks: list[datetime]) -> list[dict]:
    """
    1チャンネル分を解析。
    weeks: チェックしたい各週の月曜日リスト。
    returns: [{week_start, replied, mvp_announced, reply_count}, ...]
    """
    log_path = os.path.join(NIPPOU_DIR, f"{channel_name}.txt")
    messages = parse_log(log_path)

    # 週 → メッセージを振り分け
    week_messages: dict[datetime, list[tuple[str, str]]] = defaultdict(list)
    for dt, user, content in messages:
        ws = get_week_start(dt)
        week_messages[ws].append((user, content))

    results = []
    for ws in weeks:
        msgs = week_messages.get(ws, [])
        we = ws + timedelta(days=6)

        # 担当者の返信チェック（<@&ロールID> の全員宛お知らせは除外）
        tantosha_msgs = [
            (u, c) for u, c in msgs
            if tantosha and u == tantosha and "<@&" not in c
        ]
        replied = len(tantosha_msgs) > 0

        # MVP発表チェック：「MVPおめでとう」が誰かのメッセージにあれば発表済みとみなす
        mvp_congrats = any("MVPおめでとう" in c or "MVP おめでとう" in c for _, c in msgs)
        # 担当者自身のMVP発表投稿も確認
        mvp_announce = any(
            ("MVP" in c and ("発表" in c or "👑" in c))
            for u, c in msgs
        )
        mvp_announced = mvp_congrats or mvp_announce

        results.append({
            "week_start": ws,
            "week_end": we,
            "replied": replied,
            "reply_count": len(tantosha_msgs),
            "mvp_announced": mvp_announced,
        })

    return results


def get_weeks_for_month(year_month: str) -> list[datetime]:
    """指定月に含まれる月曜日（週の開始）リストを返す。"""
    y, m = map(int, year_month.split("-"))
    # 月の最初の日
    first = datetime(y, m, 1)
    # 月の最後の日
    if m == 12:
        last = datetime(y + 1, 1, 1) - timedelta(days=1)
    else:
        last = datetime(y, m + 1, 1) - timedelta(days=1)

    # 月曜日を列挙（月をまたがってもその週に月内の日があればカウント）
    weeks = set()
    d = first
    while d <= last:
        weeks.add(get_week_start(d))
        d += timedelta(days=1)
    return sorted(weeks)


def get_recent_weeks(n: int) -> list[datetime]:
    """直近n週の月曜日リストを返す。"""
    today = datetime.now()
    this_monday = get_week_start(today)
    return sorted([this_monday - timedelta(weeks=i) for i in range(n - 1, -1, -1)])


def format_week(ws: datetime, we: datetime) -> str:
    return f"{ws.strftime('%m/%d')}〜{we.strftime('%m/%d')}"


async def post_to_discord(content: str) -> None:
    token = _get_discord_token()
    if not token:
        print("  [警告] DISCORD_TOKEN が未設定です")
        return
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        ch = client.get_channel(POST_CHANNEL_ID)
        if ch is None:
            print(f"  [警告] チャンネルID {POST_CHANNEL_ID} が見つかりません")
        else:
            if len(content) <= 2000:
                await ch.send(content)
            else:
                parts = [content[i:i+1950] for i in range(0, len(content), 1950)]
                for i, part in enumerate(parts):
                    await ch.send(part if i == 0 else "（続き）\n" + part)
            print(f"  → #{ch.name} に投稿しました")
        await client.close()

    await client.start(token)


def main():
    parser = argparse.ArgumentParser(description="担当者活動チェック（返信・MVP発表）")
    parser.add_argument("--weeks", type=int, default=4, help="直近何週分チェックするか（デフォルト: 4）")
    parser.add_argument("--month", type=str, help="特定月を指定（例: 2026-02）。指定するとその月全体を集計。")
    parser.add_argument("--post", action="store_true", help="Discordに投稿する（直近1週）")
    args = parser.parse_args()

    mapping = load_config()

    if args.post:
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        # 返信: 実行日の前7日間（例: 金曜03/20実行 → 03/13〜03/19）
        reply_start = today - timedelta(days=7)
        reply_end = yesterday
        # MVP: 当週月曜〜前日（例: 金曜03/20実行 → 03/16〜03/19）
        mvp_start = get_week_start(datetime.now()).date()
        mvp_end = yesterday
        period_label = f"返信 {reply_start.strftime('%m/%d')}〜{reply_end.strftime('%m/%d')} / MVP {mvp_start.strftime('%m/%d')}〜{mvp_end.strftime('%m/%d')}"
        weeks = None  # --post モードでは使わない
    elif args.month:
        weeks = get_weeks_for_month(args.month)
        period_label = f"{args.month} 全週"
    else:
        weeks = get_recent_weeks(args.weeks)
        period_label = f"直近{args.weeks}週"

    print(f"\n📊 担当者活動チェック（{period_label}）")
    print(f"集計日: {datetime.now().strftime('%Y-%m-%d')}\n")

    # 担当者設定.txt が存在しない場合、テンプレートを案内
    if not os.path.exists(CONFIG_FILE):
        print(f"💡 担当者設定.txt が未作成です。デフォルトのマッピングを使用します。")
        print(f"   カスタマイズしたい場合は {CONFIG_FILE} に記載してください。\n")

    summary_lines = []
    total_checked = 0
    replied_ok = 0
    mvp_ok = 0

    for ch in CHANNEL_ORDER:
        tantosha = mapping.get(ch, "")
        if not tantosha:
            summary_lines.append(f"\n{ch}")
            summary_lines.append(f"  ⚠️ 担当者未設定")
            continue

        summary_lines.append(f"\n{ch}（担当：{tantosha}）")

        if args.post:
            r = analyze_channel_post(ch, tantosha, reply_start, reply_end, mvp_start, mvp_end)
            replied_mark = "✅" if r["replied"] else "❌"
            mvp_mark = "✅" if r["mvp_announced"] else "❌"
            count_str = f"（{r['reply_count']}件）" if r["reply_count"] > 0 else ""
            summary_lines.append(f"  返信 {replied_mark}{count_str}  MVP発表 {mvp_mark}")
            total_checked += 1
            if r["replied"]: replied_ok += 1
            if r["mvp_announced"]: mvp_ok += 1
        else:
            results = analyze_channel(ch, tantosha, weeks)
            for r in results:
                week_label = format_week(r["week_start"], r["week_end"])
                replied_mark = "✅" if r["replied"] else "❌"
                mvp_mark = "✅" if r["mvp_announced"] else "❌"
                count_str = f"（{r['reply_count']}件）" if r["reply_count"] > 0 else ""
                summary_lines.append(
                    f"  {week_label}  返信 {replied_mark}{count_str}  MVP発表 {mvp_mark}"
                )
                total_checked += 1
                if r["replied"]: replied_ok += 1
                if r["mvp_announced"]: mvp_ok += 1

    output = "\n".join(summary_lines)
    for line in summary_lines:
        print(line)

    footer_lines = []
    print("\n" + "─" * 50)
    if total_checked > 0:
        footer_lines.append(f"返信達成率:    {replied_ok}/{total_checked} ({replied_ok/total_checked*100:.0f}%)")
        footer_lines.append(f"MVP発表達成率: {mvp_ok}/{total_checked} ({mvp_ok/total_checked*100:.0f}%)")
    for line in footer_lines:
        print(line)
    print()

    if args.post:
        header = (
            f"**【担当者活動チェック】**\n"
            f"返信期間: {reply_start.strftime('%m/%d')}〜{reply_end.strftime('%m/%d')}"
            f"　MVP期間: {mvp_start.strftime('%m/%d')}〜{mvp_end.strftime('%m/%d')}\n"
            f"集計日: {datetime.now().strftime('%Y-%m-%d')}\n"
        )
        discord_msg = header + output + "\n─────────────────────\n" + "\n".join(footer_lines)
        asyncio.run(post_to_discord(discord_msg))


if __name__ == "__main__":
    main()
