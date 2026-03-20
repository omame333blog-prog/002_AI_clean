"""
日報ログ取得スクリプト
Discordから日報を取得し、002_AI_/nippou_logs/ に保存する。

実行: cd /Users/kasaimami/002_AI_ && source venv/bin/activate && python export_logs.py
テスト（1チャンネル）: TEST=1 python export_logs.py
"""
import os
import re
import json
import sys
import asyncio
from datetime import datetime, timezone
import discord

# ★Botトークンは環境変数から読む（ファイルに直書きしない）
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

# ★日報チャンネルのID（1チャンネルずつ、チャンネル名で別ファイルに保存）
CHANNEL_IDS = [
    1366955154141614190,  # レッドの部屋
    1366955220420006070,  # ホワイトの部屋
    1366955268855955569,  # パープルの部屋
    1385984348309688441,  # グリーンの部屋
    1385984417100726425,  # ピンクの部屋
    1420627078834946059,  # ブラックの部屋
    1420626668749324308,  # オレンジの部屋
    1420627377754603601,  # ブラウンの部屋
    1432259083683102720,  # ブルーの部屋
    1442705451039850548,  # みずいろの部屋
    1456297262308266015,  # イエローの部屋
    1464304043538251906,  # グレーの部屋
    1476381913731174615,  # いぬの部屋
    1476382049928609938,  # ひつじの部屋
]

CHANNEL_TO_ROLE = {
    1366955154141614190: "レッドのお部屋❤️",
    1366955220420006070: "ホワイトのお部屋🤍",
    1366955268855955569: "パープルのお部屋💜",
    1385984348309688441: "グリーンのお部屋💚",
    1385984417100726425: "ピンクのお部屋🩷",
    1420627078834946059: "ブラックのお部屋🖤",
    1420626668749324308: "オレンジのお部屋🧡",
    1420627377754603601: "ブラウンのお部屋🤎",
    1432259083683102720: "ブルーのお部屋💙",
    1442705451039850548: "みずいろのお部屋🩵",
    1456297262308266015: "イエローのお部屋💛",
    1464304043538251906: "グレーのお部屋🩶",
    1476381913731174615: "いぬ−戌–のお部屋🐶",
    1476382049928609938: "ひつじ−未−のお部屋🐑",
}

# 保存先：このスクリプトと同じ 002_AI_ 直下の nippou_logs
_BASE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_BASE, "nippou_logs")
STATE_FILE = os.path.join(OUTPUT_DIR, "export_state.json")
# 卒業生リスト（1行1名）。スプレッドシート「全体のメンバーの課題進捗表」の卒業生を反映すること。
GRADUATE_LIST_FILE = os.path.join(OUTPUT_DIR, "卒業生リスト.txt")
# 休会中リスト（1行1名）。未提出者の中に休会中の人がいればサマリーに「未提出者のうち休会中」として表示（リマインド対象外の確認用）。
KYUKAI_LIST_FILE = os.path.join(OUTPUT_DIR, "休会中リスト.txt")
FIRST_FETCH_AFTER = datetime(2026, 2, 1, tzinfo=timezone.utc)
TEST_MODE = os.environ.get("TEST", "").strip() == "1"

# ★結果を送信するDiscordチャンネルID（運営幹部用など）。None なら送信しない。
# チャンネルを右クリック → リンクをコピー → 末尾の数字がID
POST_CHANNEL_ID = None  # 例: 1234567890123456789


def safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "channel"


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


LOG_LINE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(.+?):\s+")


def parse_submitters_from_lines(lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        m = LOG_LINE_RE.match(line.strip())
        if m:
            date_str, name = m.group(1), m.group(2).strip()
            day = date_str.split()[0]
            if name not in result or day > result[name]:
                result[name] = day
    return result


def get_list_key(entry: str) -> str:
    """リストの1行から照合用キーを取得。_ または （ または ( より前の部分。例: もりゆき（ゆき）→ もりゆき"""
    s = entry.strip()
    for sep in ("_", "（", "("):
        if sep in s:
            s = s.split(sep, 1)[0].strip()
            break
    return s


def load_graduate_list() -> tuple[set[str], set[str]]:
    """卒業生リストを読み、(表示名キー集合, ユーザー名集合) を返す。# 始まりはコメント。

    - 「完全一致」… 卒業生リストに Discord 表示名そのものを書いた場合（例: やすこ_B）
    - 「キー一致」… _ や （ より前だけを書いた場合（例: やすこ）
    - 「ユーザー名指定」… 「表示名 @username」の形式（例: ゆか @yuka4059）→ 同名別人でも確実に区別

    ただし曖昧マッチが原因で「やすこ_B / やすこ_R」のような重複が起きないよう、
    _ や （ を含む行についてはキー一致用の短縮版は追加しない。
    """
    if not os.path.exists(GRADUATE_LIST_FILE):
        return set(), set()
    out: set[str] = set()
    usernames: set[str] = set()
    with open(GRADUATE_LIST_FILE, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            # 「表示名 @username」形式の処理
            if " @" in ln:
                username = ln.split(" @", 1)[1].strip().lower()
                if username:
                    usernames.add(username)
                continue
            out.add(ln)
            # _ や （ を含まない素の名前だけ、キー一致用にも追加する
            if all(sep not in ln for sep in ("_", "（", "(")):
                key = get_list_key(ln)
                if key and key != ln:
                    out.add(key)
    return out, usernames


def load_kyukai_list() -> set[str]:
    """休会中リストを読み、照合用のキー集合を返す。# 始まりはコメント。"""
    if not os.path.exists(KYUKAI_LIST_FILE):
        return set()
    out: set[str] = set()
    with open(KYUKAI_LIST_FILE, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            out.add(ln)
            key = get_list_key(ln)
            if key:
                out.add(key)
    return out


def is_in_list(display_name: str, key_set: set[str]) -> bool:
    """表示名がリストに含まれるか（完全一致または _/（/( より前のキー一致、大小文字無視）。"""
    # 候補となる表示名のキー（そのまま / _より前 / （より前 など）
    candidates = {
        display_name.strip(),
        get_base_name(display_name).strip(),
        get_list_key(display_name).strip(),
    }
    # リスト側も大小文字を無視して比較
    lower_keys = {k.lower() for k in key_set}
    for cand in candidates:
        if not cand:
            continue
        if cand in key_set or cand.lower() in lower_keys:
            return True
    return False


def get_base_name(display_name: str) -> str:
    """Discord表示名の _ または ＿（全角）より前の部分を返す。なければそのまま。"""
    for sep in ("_", "＿"):
        if sep in display_name:
            return display_name.split(sep, 1)[0].strip()
    return display_name


def resolve_graduates(
    members: list[discord.Member],
    graduate_set: set[str],
    graduate_usernames: set[str] | None = None,
) -> tuple[list[discord.Member], list[tuple[str, list[str]]]]:
    """
    在籍メンバーの中で卒業生を判定する。
    ユーザー名指定（@username）があれば最優先で確定。次に表示名の完全一致、キー一致の順。
    同じキーの人が複数いれば重複扱いにして除外せず、報告用に返す。
    返値: (卒業生と確定したメンバーリスト, [(名前, [重複している表示名のリスト]), ...])
    """
    graduates: list[discord.Member] = []
    ambiguous: list[tuple[str, list[str]]] = []
    already = set()

    # ユーザー名指定（最優先・曖昧なし）
    if graduate_usernames:
        lower_usernames = {u.lower() for u in graduate_usernames}
        for m in members:
            if m.name.lower() in lower_usernames:
                graduates.append(m)
                already.add(m.id)

    remaining = [m for m in members if m.id not in already]

    base_to_members: dict[str, list[discord.Member]] = {}
    for m in remaining:
        base = get_base_name(m.display_name)
        base_to_members.setdefault(base, []).append(m)

    for m in remaining:
        if m.display_name in graduate_set:
            graduates.append(m)
            continue
        base = get_base_name(m.display_name)
        if base not in graduate_set:
            continue
        same_base = base_to_members.get(base, [m])
        if len(same_base) > 1:
            names = sorted({x.display_name for x in same_base})
            if not any(a[0] == base and a[1] == names for a in ambiguous):
                ambiguous.append((base, names))
            continue
        graduates.append(m)

    return graduates, ambiguous


def get_role_members(guild: discord.Guild, role_name: str) -> list[discord.Member]:
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        return []
    return [m for m in guild.members if role in m.roles and not m.bot]


class MyClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        print(f"保存先: {OUTPUT_DIR}")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        state = load_state()

        if not TEST_MODE:
            # メンバー一覧の追加取得はスキップし、そのままチャンネル別ログを取得する
            print("  メンバー一覧の追加取得をスキップします（そのままチャンネル別ログを取得）")
        else:
            print("  [テストモード] メンバー一覧取得をスキップ（ログのみ取得）")

        # 環境変数 TARGET_CHANNEL_ID があれば、そのIDだけを対象にする（1部屋ずつ取得したいとき用）
        target_id_env = os.environ.get("TARGET_CHANNEL_ID", "").strip()
        if target_id_env:
            try:
                target_id = int(target_id_env)
                channel_ids = [target_id]
                print(f"  TARGET_CHANNEL_ID={target_id} のみ取得します")
            except ValueError:
                print(f"  [警告] TARGET_CHANNEL_ID='{target_id_env}' は数値として解釈できません。通常のCHANNEL_IDSを使用します。")
                channel_ids = CHANNEL_IDS[:1] if TEST_MODE else CHANNEL_IDS
        else:
            channel_ids = CHANNEL_IDS[:1] if TEST_MODE else CHANNEL_IDS
        if TEST_MODE:
            print("[テストモード] 1チャンネルのみ取得します")
        graduate_set, graduate_usernames = load_graduate_list()
        kyukai_set = load_kyukai_list()
        if graduate_set or graduate_usernames:
            print(f"卒業生リスト: {len(graduate_set)} 名（メンバー数・未提出者・提出率から除外）")
        if kyukai_set:
            print(f"休会中リスト: {len(kyukai_set)} 名（未提出者の中にいれば「休会中」として表示）")
        summary_files: list[str] = []
        for channel_id in channel_ids:
            try:
                channel = await self.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                print(f"  [スキップ] チャンネルID {channel_id} を取得できません: {e}")
                continue
            if channel is None:
                print(f"  [スキップ] チャンネルID {channel_id} が見つかりません")
                continue

            name = safe_filename(channel.name)
            out_path = os.path.join(OUTPUT_DIR, f"{name}.txt")
            summary_path = os.path.join(OUTPUT_DIR, f"{name}_サマリー.txt")
            sid = str(channel_id)

            existing_lines: list[str] = []
            if os.path.exists(out_path):
                with open(out_path, "r", encoding="utf-8") as f:
                    existing_lines = [ln for ln in f.read().splitlines() if ln.strip()]

            last_msg_id = state.get(sid)
            new_lines: list[str] = []
            latest_msg_id = None

            if last_msg_id:
                cursor = discord.Object(id=int(last_msg_id))
                async for message in channel.history(limit=None, after=cursor, oldest_first=True):
                    if message.author.bot:
                        continue
                    ts = message.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
                    new_lines.append(f"[{ts}] {message.author.display_name}: {message.content.replace(chr(10), ' ')}")
                    latest_msg_id = message.id
                print(f"取得中: #{channel.name} (差分 {len(new_lines)} 件)")
            else:
                async for message in channel.history(limit=None, after=FIRST_FETCH_AFTER, oldest_first=True):
                    if message.author.bot:
                        continue
                    ts = message.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
                    new_lines.append(f"[{ts}] {message.author.display_name}: {message.content.replace(chr(10), ' ')}")
                    latest_msg_id = message.id
                print(f"取得中: #{channel.name} (初回・2月以降 {len(new_lines)} 件)")

            all_lines = existing_lines + new_lines
            def sort_key(ln: str) -> str:
                m = LOG_LINE_RE.match(ln.strip())
                return m.group(1) if m else ""
            all_lines.sort(key=sort_key)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n".join(all_lines))

            if latest_msg_id:
                state[sid] = str(latest_msg_id)

            current_month = datetime.now(timezone.utc).astimezone().strftime("%Y-%m")
            monthly_lines = [ln for ln in all_lines if ln.startswith(f"[{current_month}")]
            submitters_map = parse_submitters_from_lines(monthly_lines)
            guild = channel.guild
            role_name = CHANNEL_TO_ROLE.get(channel_id, channel.name)
            members = get_role_members(guild, role_name)
            # 卒業生はメンバー数・未提出者・提出率から除外（交流会等のためロールは付けたまま）
            # 同じ「_より前」の名前が複数人いるときは重複扱いで除外せず、確認を促す
            graduates_in_room, ambiguous_list = resolve_graduates(members, graduate_set, graduate_usernames)
            enrolled = [m for m in members if m not in graduates_in_room]

            # 複数該当時：手動実行なら「この人たちのうち誰を卒業生として除外するか」を確認
            if ambiguous_list and sys.stdin.isatty():
                for base_name, display_names in ambiguous_list:
                    names_str = ", ".join(sorted(display_names))
                    print(f"\n  【確認 #{channel.name}】「{base_name}」に一致する人が複数います: {names_str}")
                    try:
                        raw = input("  → 卒業生として除外する表示名をカンマ区切りで入力（Enterでどちらも除外しない）: ").strip()
                    except (EOFError, KeyboardInterrupt):
                        raw = ""
                    to_exclude = {s.strip() for s in raw.split(",") if s.strip()}
                    for dname in to_exclude:
                        if dname in display_names:
                            m = next((x for x in members if x.display_name == dname), None)
                            if m and m not in graduates_in_room:
                                graduates_in_room.append(m)
                                enrolled = [x for x in enrolled if x != m]
                    if to_exclude:
                        print(f"  → {', '.join(to_exclude)} を卒業生として除外しました。")
            else:
                for base_name, display_names in ambiguous_list:
                    print(f"  [重複 #{channel.name}] 「{base_name}」に一致する人が複数います（{', '.join(display_names)}）。"
                          " 卒業生リストに Discord表示名をそのまま追加するか、手動実行で確認してください。")

            non_submitters = [m for m in enrolled if m.display_name not in submitters_map]

            # 未提出者のうち休会中かどうか：常に休会中リストを参照（手動・cron 共通）
            kyukai_in_non: list[discord.Member] = []
            visible_non_submitters = non_submitters
            if non_submitters:
                kyukai_in_non = [
                    m for m in non_submitters if is_in_list(m.display_name, kyukai_set)
                ]
                if kyukai_in_non:
                    print(
                        f"  【休会中リスト】未提出者 {len(non_submitters)} 名のうち休会中: "
                        + ", ".join(m.display_name for m in kyukai_in_non)
                    )
                    # 表示上の「未提出者」には休会中を含めない（区別しやすくする）
                    visible_non_submitters = [m for m in non_submitters if m not in kyukai_in_non]

            total = len(enrolled)
            submitted = sum(1 for m in enrolled if m.display_name in submitters_map)
            # 提出率の分母は「提出対象者」＝メンバー数のうち休会中を除く（休会中は日報提出義務なし）
            target_count = total - len(kyukai_in_non)
            rate = (submitted / target_count * 100) if target_count > 0 else 0
            summary_lines = [
                f"# {channel.name} - メンバーサマリー", "",
                f"メンバー数: {total}",
                f"提出対象者（休会中除く）: {target_count}",
                f"提出者: {submitted}",
                f"未提出者（休会中を除く）: {len(visible_non_submitters)}",
                f"提出率: {rate:.1f}%",
                "",
                "## 提出者（名前, 最終提出日）",
            ]
            for m in enrolled:
                if m.display_name in submitters_map:
                    summary_lines.append(f"{m.display_name}, {submitters_map[m.display_name]}")
            summary_lines.extend(["", "## 未提出者（休会中を除く）"])
            for m in visible_non_submitters:
                summary_lines.append(m.display_name)
            if kyukai_in_non:
                summary_lines.extend(["", "## 未提出者のうち休会中（リマインド対象外）"])
                for m in kyukai_in_non:
                    summary_lines.append(m.display_name)
                summary_lines.append("")
                summary_lines.append("※ 上記は未提出者ですが休会中のためリマインド対象外です。")
            if graduates_in_room:
                summary_lines.extend(["", "## 卒業生（対象外）"])
                for m in graduates_in_room:
                    summary_lines.append(m.display_name)
            if ambiguous_list:
                still_ambiguous = [
                    (base_name, [d for d in display_names if next((m for m in members if m.display_name == d), None) in enrolled])
                    for base_name, display_names in ambiguous_list
                ]
                still_ambiguous = [(b, names) for b, names in still_ambiguous if len(names) > 1]
                if still_ambiguous:
                    summary_lines.extend(["", "## 要確認（同名で複数人。卒業生リストに表示名を追加するか、次回手動実行で指定してください）"])
                    for base_name, display_names in still_ambiguous:
                        summary_lines.append(f"- 「{base_name}」→ {', '.join(display_names)}")

            with open(summary_path, "w", encoding="utf-8") as f:
                f.write("\n".join(summary_lines))
            summary_files.append(summary_path)

            print(f"  → {out_path} (合計 {len(all_lines)} 件)")
            if total > 0:
                msg = f"  → {summary_path} (提出率 {rate:.1f}%, 未提出 {len(non_submitters)} 名)"
                if graduates_in_room:
                    msg += f", 卒業生除外 {len(graduates_in_room)} 名"
                print(msg)
            elif len(members) > 0:
                print(f"  → {summary_path} (在籍0・卒業生のみ {len(graduates_in_room)} 名)")
            else:
                print(f"  → ロール「{role_name}」が見つかりません（CHANNEL_TO_ROLEを確認）")

        save_state(state)
        print("すべてのチャンネルの取得が完了しました。")

        # 指定チャンネルに結果を送信（POST_CHANNEL_ID が設定されている場合）
        if POST_CHANNEL_ID and summary_files:
            try:
                post_ch = self.get_channel(int(POST_CHANNEL_ID))
                if post_ch:
                    dt = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
                    await post_ch.send(f"📋 **日報サマリー**（{dt} 取得分）")
                    # Discordは1メッセージあたり最大10ファイル
                    for i in range(0, len(summary_files), 10):
                        batch = summary_files[i : i + 10]
                        await post_ch.send(files=[discord.File(p) for p in batch])
                    print(f"  → #{post_ch.name} に送信しました")
                else:
                    print("  [警告] POST_CHANNEL_ID のチャンネルが見つかりません")
            except Exception as e:
                print(f"  [警告] Discord送信に失敗: {e}")

        await asyncio.sleep(1)  # バックグラウンド処理の終了を待つ
        try:
            await self.close()
        except Exception:
            pass  # 切断時のエラーは無視


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = MyClient(intents=intents)
asyncio.run(client.start(DISCORD_TOKEN))
