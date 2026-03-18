"""
週1回「2週間以上日報未提出」リマインドをDiscordに投稿するスクリプト。
nippou_logs のログ・サマリーを解析し、要リマインド対象をまとめて指定チャンネルに送る。

実行:
  cd /Users/kasaimami/002_AI_ && source venv/bin/activate && python post_weekly_remind.py
  python post_weekly_remind.py --dry-run   # 投稿せず内容のみ表示

cron例（毎週月曜 9:00 に送る）:
  0 9 * * 1 cd /Users/kasaimami/002_AI_ && source venv/bin/activate && python post_weekly_remind.py

設定:
  - REMIND_CHANNEL_ID: リマインドを送るDiscordチャンネルID（運営用など）
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

# ★週1リマインドを送るDiscordチャンネルID。None なら送信しない（運営用チャンネルを指定）
REMIND_CHANNEL_ID = 1482931158714155008  # 週次提出率アナウンスと同じチャンネルで可

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

DISCORD_TOKEN = _get_discord_token()

NIPPOU_DIR = os.path.join(_BASE, "nippou_logs")
GRADUATE_LIST_FILE = os.path.join(NIPPOU_DIR, "卒業生リスト.txt")
LOG_LINE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(.+?):\s+")
REMIND_DAYS = 14


def get_list_key(entry: str) -> str:
    """_ または （ または ( より前の部分で照合。"""
    s = entry.strip()
    for sep in ("_", "（", "("):
        if sep in s:
            s = s.split(sep, 1)[0].strip()
            break
    return s


def load_graduate_list() -> set[str]:
    """卒業生リストのキー集合。# はコメント。"""
    if not os.path.exists(GRADUATE_LIST_FILE):
        return set()
    out: set[str] = set()
    with open(GRADUATE_LIST_FILE, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            out.add(ln)
            key = get_list_key(ln)
            if key:
                out.add(key)
    return out


def is_graduate(name: str, graduate_set: set[str]) -> bool:
    if name in graduate_set:
        return True
    return get_list_key(name) in graduate_set


def parse_log_last_dates(log_path: str) -> dict[str, str]:
    """ログファイルから 名前 -> 最終提出日(YYYY-MM-DD) を返す。"""
    result: dict[str, str] = {}
    if not os.path.isfile(log_path):
        return result
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            m = LOG_LINE_RE.match(line.strip())
            if m:
                date_str, name = m.group(1), m.group(2).strip()
                day = date_str.split()[0]
                if name not in result or day > result[name]:
                    result[name] = day
    return result


def parse_summary(
    summary_path: str,
) -> tuple[dict[str, str], list[str], list[str], list[str]]:
    """
    サマリーファイルから (提出者 name->date, 未提出者名一覧, 卒業生名一覧, 休会中名一覧) を返す。
    """
    last_dates: dict[str, str] = {}
    never_submitted: list[str] = []
    graduates: list[str] = []
    kyukai: list[str] = []
    if not os.path.isfile(summary_path):
        return last_dates, never_submitted, graduates, kyukai

    with open(summary_path, "r", encoding="utf-8") as f:
        text = f.read()

    section = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## 提出者"):
            section = "submitter"
            continue
        if line.startswith("## 未提出者のうち休会中"):
            section = "kyukai"
            continue
        if line.startswith("## 未提出者"):
            section = "never"
            continue
        if line.startswith("※"):
            if section == "never":
                section = None
            continue
        if line.startswith("## 卒業生"):
            section = "graduate"
            continue
        if not line or line.startswith("#"):
            continue
        if section == "submitter":
            if "," in line:
                name, date = line.split(",", 1)
                name, date = name.strip(), date.strip()
                if re.match(r"\d{4}-\d{2}-\d{2}", date):
                    last_dates[name] = date
        elif section == "never":
            never_submitted.append(line)
        elif section == "kyukai":
            kyukai.append(line)
        elif section == "graduate":
            graduates.append(line)

    return last_dates, never_submitted, graduates, kyukai


def discover_channel_pairs() -> list[tuple[str, str, str]]:
    """(ログパス, サマリーパス, チャンネル表示名) のリスト。チャンネル名はサマリーのベース名から _サマリー を除いたもの。"""
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


def run_remind_for_channel(
    log_path: str,
    summary_path: str,
    channel_name: str,
    graduate_set: set[str],
    today: str,
) -> tuple[str, list[tuple[str, str, int]]]:
    """
    1チャンネル分の要リマインドを計算。
    返値: (channel_name, [(名前, 最終提出日 or "未提出", 経過日数), ...])
    """
    last_from_log = parse_log_last_dates(log_path)
    summary_dates, never_submitted, summary_graduates, kyukai_names = parse_summary(
        summary_path
    )
    # サマリーに載っている現在のメンバーのみ対象（ロールが外れた人をログ履歴から除外するため）
    current_member_keys = (
        {get_list_key(n) for n in summary_dates}
        | {get_list_key(n) for n in never_submitted}
        | {get_list_key(n) for n in kyukai_names}
        | {get_list_key(n) for n in summary_graduates}
    )
    # ログの最終日付はサマリーの現在メンバーのみに絞る
    last_from_log_filtered = {
        n: d for n, d in last_from_log.items()
        if get_list_key(n) in current_member_keys
    }
    last_dates = {**last_from_log_filtered, **summary_dates}
    exclude = set(graduate_set) | {get_list_key(n) for n in summary_graduates}
    exclude |= {get_list_key(n) for n in kyukai_names}  # 休会中は対象外

    to_remind: list[tuple[str, str, int]] = []
    today_dt = datetime.strptime(today, "%Y-%m-%d").date()

    # 今月未提出の人（卒業生・休会中除く）：ログに過去の投稿があれば日付を使う
    for name in never_submitted:
        key = get_list_key(name)
        if key in exclude or is_graduate(name, graduate_set):
            continue
        last = last_from_log_filtered.get(name)
        if last:
            try:
                last_dt = datetime.strptime(last, "%Y-%m-%d").date()
                days_ago = (today_dt - last_dt).days
                if days_ago >= REMIND_DAYS:
                    to_remind.append((name, last, days_ago))
            except ValueError:
                to_remind.append((name, "未提出", 0))
        else:
            to_remind.append((name, "未提出", 0))

    # 2週間以上前が最終提出の人
    for name, last in last_dates.items():
        if is_graduate(name, graduate_set) or get_list_key(name) in exclude:
            continue
        if name in [n for n, _, _ in to_remind]:
            continue
        try:
            last_dt = datetime.strptime(last, "%Y-%m-%d").date()
            days_ago = (today_dt - last_dt).days
            if days_ago >= REMIND_DAYS:
                to_remind.append((name, last, days_ago))
        except ValueError:
            pass

    return channel_name, to_remind


def build_remind_message(
    results: list[tuple[str, list[tuple[str, str, int]]]],
    today: str,
) -> str:
    """Discordに送る本文を組み立てる。2000文字を超える場合はチャンネルごとに分割送信する前提で1チャンネルずつ返すのではなく、ここでは1メッセージにまとめる。"""
    lines = [
        "**【週次】日報リマインド（2週間以上未提出）**",
        "",
        f"集計日: {today}",
        "",
    ]
    for channel_name, remind_list in results:
        if not remind_list:
            lines.append(f"・**{channel_name}**: 対象者なし ✅")
            continue
        lines.append(f"・**{channel_name}**（要リマインド {len(remind_list)}名）")
        for name, last_str, days_ago in sorted(
            remind_list,
            key=lambda x: (x[1] != "未提出", -(x[2] if isinstance(x[2], int) and x[2] < 10000 else 0)),
        ):
            if last_str == "未提出":
                # 一度も提出なし＝1ヶ月以上リスクとして🚨＋太字
                lines.append(f"  - 🚨 {name}: **未提出**")
            else:
                if days_ago >= 30:
                    # 1ヶ月以上未提出＝サポート対象外アナウンス対象
                    lines.append(f"  - 🚨 {name}: 最終 {last_str}（**{days_ago}日経過**）")
                else:
                    lines.append(f"  - {name}: 最終 {last_str}（{days_ago}日経過）")
        lines.append("")
    lines.extend([
        "※ 卒業生・休会中は対象外です。",
        "※ DMでお声がけいただき、返信がない場合はLINEから連絡するので教えてください。",
    ])
    return "\n".join(lines)


async def post_to_discord(content: str, channel_id: int | None) -> bool:
    if not DISCORD_TOKEN:
        print("  [警告] DISCORD_TOKEN が未設定です")
        return False
    if not channel_id:
        print("  [警告] REMIND_CHANNEL_ID が未設定です")
        return False
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        ch = client.get_channel(channel_id)
        if ch is None:
            print(f"  [警告] チャンネルID {channel_id} が見つかりません")
        else:
            # Discordは2000文字制限
            if len(content) <= 2000:
                await ch.send(content)
            else:
                parts = [content[i : i + 1950] for i in range(0, len(content), 1950)]
                for i, part in enumerate(parts):
                    await ch.send(part if i == 0 else "（続き）\n" + part)
            print(f"  → #{ch.name} にリマインドを送信しました")
        await client.close()

    await client.start(DISCORD_TOKEN)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="2週間以上未提出リマインドをDiscordに投稿")
    parser.add_argument("--dry-run", action="store_true", help="投稿せず内容のみ表示")
    parser.add_argument(
        "--only",
        type=str,
        metavar="チャンネル名",
        help="指定したチャンネル（お部屋）のみ集計・投稿。例: --only \"レッドの部屋\"",
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc).astimezone()
    today = now.strftime("%Y-%m-%d")

    pairs = discover_channel_pairs()
    if args.only:
        pairs = [(lp, sp, name) for lp, sp, name in pairs if name == args.only]
        if not pairs:
            print(f"  [警告] 「{args.only}」に一致するチャンネルがありません。")
            sys.exit(1)
    if not pairs:
        print("nippou_logs にログ・サマリーのペアが見つかりません。")
        sys.exit(1)

    graduate_set = load_graduate_list()
    results: list[tuple[str, list[tuple[str, str, int]]]] = []
    for log_path, summary_path, channel_name in pairs:
        ch_name, remind_list = run_remind_for_channel(
            log_path, summary_path, channel_name, graduate_set, today
        )
        results.append((ch_name, remind_list))

    content = build_remind_message(results, today)
    print("--- リマインド文（予定） ---")
    print(content)
    print("---")

    if args.dry_run:
        print("（--dry-run のため投稿しません）")
        return

    if REMIND_CHANNEL_ID is None:
        print("REMIND_CHANNEL_ID を設定するとDiscordに投稿できます。")
        return

    asyncio.run(post_to_discord(content, int(REMIND_CHANNEL_ID)))


if __name__ == "__main__":
    main()
