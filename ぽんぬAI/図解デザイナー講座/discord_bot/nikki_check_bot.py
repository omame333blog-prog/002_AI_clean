"""
日報チャンネル エラーチェックBot

チェック内容:
① MVP: 木曜日までに週間MVPの発表があるか
② 交流会: 交流会が実施されているか
③ 返信: 日報担当が8日以内に返信しているか
"""

import asyncio
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

import discord
from dotenv import load_dotenv

# 設定を読み込み
load_dotenv("config.env")

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_IDS_STR = os.getenv("CHANNEL_IDS", "")
NIKKI_TANTO_STR = os.getenv("NIKKI_TANTO_USERNAMES", "")

# チャンネルごとの日報担当（オプション）形式: channel_id:username,channel_id:username
CHANNEL_TANTO_MAP_STR = os.getenv("CHANNEL_TANTO_MAP", "")

# 定数
MVP_KEYWORDS = ["MVP", "mvp"]
KOUSAKAI_KEYWORDS = ["交流会"]
MITAMASHITA_EXCLUDE = ["見ました", "見ました！", "拝見しました", "確認しました"]  # これのみは返信に含めない
DAYS_REPLY_OK = 8
DAYS_FETCH = 21  # 取得するメッセージの範囲（日数）
MESSAGES_LIMIT = 500  # 1チャンネルあたり取得する最大メッセージ数


def parse_channel_tanto_map(s: str) -> dict[int, str]:
    """CHANNEL_TANTO_MAP をパースして {channel_id: username} を返す"""
    result = {}
    if not s.strip():
        return result
    for part in s.split(","):
        part = part.strip()
        if ":" in part:
            cid, username = part.split(":", 1)
            try:
                result[int(cid.strip())] = username.strip()
            except ValueError:
                pass
    return result


def is_valid_reply(content: str | None) -> bool:
    """「見ました」のみの返信かどうか。True = 有効な返信、False = 見ましたのみ等で無効"""
    if not content or not content.strip():
        return False
    stripped = content.strip()
    # 短すぎる（1-2語程度）かつ定型句のみは無効
    if stripped in MITAMASHITA_EXCLUDE:
        return False
    if len(stripped) <= 6 and stripped.endswith("ました"):
        return False
    return True


def get_monday_of_week(dt: datetime) -> datetime:
    """その日が含まれる週の月曜日 0:00 を返す（JST想定）"""
    return (dt - timedelta(days=dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def get_thursday_of_week(dt: datetime) -> datetime:
    """その週の木曜日 23:59 を返す"""
    monday = get_monday_of_week(dt)
    return monday + timedelta(days=3, hours=23, minutes=59, seconds=59)


async def check_channel(
    client: discord.Client,
    channel_id: int,
    channel_name: str,
    channel_tanto_map: dict[int, str],
    global_tantos: list[str],
) -> dict:
    """1チャンネル分のチェックを実行"""
    channel = client.get_channel(channel_id)
    if not channel:
        try:
            channel = await client.fetch_channel(channel_id)
        except discord.NotFound:
            return {
                "channel_id": channel_id,
                "channel_name": channel_name or str(channel_id),
                "error": "チャンネルが見つかりません",
                "mvp_ok": None,
                "kousakai_ok": None,
                "reply_ok": None,
            }

    # 日報担当: チャンネル専用があればそれ、なければグローバルリスト
    tantos = [channel_tanto_map[channel_id]] if channel_id in channel_tanto_map else global_tantos

    cutoff = datetime.utcnow() - timedelta(days=DAYS_FETCH)
    messages: list[discord.Message] = []
    async for msg in channel.history(limit=MESSAGES_LIMIT):
        if msg.created_at.replace(tzinfo=None) < cutoff:
            break
        messages.append(msg)

    now = datetime.utcnow()
    monday = get_monday_of_week(now)
    thursday = get_thursday_of_week(now)

    # ① MVP: 今週、木曜日までの期間にMVPを含むメッセージがあるか
    mvp_ok = False
    if now >= thursday:
        # 木曜日を過ぎている → 今週分のMVPが必要
        for m in messages:
            if monday <= m.created_at.replace(tzinfo=None) <= thursday:
                c = (m.content or "").upper()
                if any(k in c for k in MVP_KEYWORDS):
                    mvp_ok = True
                    break
    else:
        # 木曜日より前（月〜水）→ 前週分をチェック
        prev_monday = monday - timedelta(days=7)
        prev_thursday = thursday - timedelta(days=7)
        for m in messages:
            mt = m.created_at.replace(tzinfo=None)
            if prev_monday <= mt <= prev_thursday:
                c = (m.content or "").upper()
                if any(k in c for k in MVP_KEYWORDS):
                    mvp_ok = True
                    break

    # ② 交流会: 直近30日以内に「交流会」を含むメッセージがあるか
    kousakai_cutoff = now - timedelta(days=30)
    kousakai_ok = False
    for m in messages:
        if m.created_at.replace(tzinfo=None) >= kousakai_cutoff:
            if any(k in (m.content or "") for k in KOUSAKAI_KEYWORDS):
                kousakai_ok = True
                break

    # ③ 返信: 日報担当が8日以内に有効な返信をしているか
    reply_ok = True  # 担当がいなければOK扱い
    if tantos:
        reply_cutoff = now - timedelta(days=DAYS_REPLY_OK)
        reply_ok = False
        for m in messages:
            if m.created_at.replace(tzinfo=None) < reply_cutoff:
                continue
            # name / display_name / global_name のいずれかにマッチ
            author_names = []
            if hasattr(m.author, "name") and m.author.name:
                author_names.append(m.author.name.lower())
            if hasattr(m.author, "display_name") and m.author.display_name:
                author_names.append(m.author.display_name.lower())
            if hasattr(m.author, "global_name") and m.author.global_name:
                author_names.append(m.author.global_name.lower())
            for t in tantos:
                t_lower = t.lower()
                if any(t_lower in n or n in t_lower for n in author_names):
                    if is_valid_reply(m.content):
                        reply_ok = True
                        break
            if reply_ok:
                break

    return {
        "channel_id": channel_id,
        "channel_name": channel_name or (channel.name if channel else str(channel_id)),
        "error": None,
        "mvp_ok": mvp_ok,
        "kousakai_ok": kousakai_ok,
        "reply_ok": reply_ok,
    }


async def main():
    if not TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN が設定されていません。config.env を確認してください。")
        return

    channel_ids = [int(x.strip()) for x in CHANNEL_IDS_STR.split(",") if x.strip()]
    if not channel_ids:
        print("ERROR: CHANNEL_IDS が設定されていません。config.env を確認してください。")
        return

    global_tantos = [x.strip() for x in NIKKI_TANTO_STR.split(",") if x.strip()]
    channel_tanto_map = parse_channel_tanto_map(CHANNEL_TANTO_MAP_STR)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True

    client = discord.Client(intents=intents)

    results = []

    @client.event
    async def on_ready():
        nonlocal results
        print(f"ログイン成功: {client.user}")
        for cid in channel_ids:
            r = await check_channel(client, cid, "", channel_tanto_map, global_tantos)
            results.append(r)
            print(f"  {r['channel_name']}: MVP={r['mvp_ok']}, 交流会={r['kousakai_ok']}, 返信={r['reply_ok']}")
        await client.close()

    await client.start(TOKEN)

    # CSV出力
    out_path = Path(__file__).parent / "日報チェック結果.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["チャンネルID", "チャンネル名", "MVP", "交流会", "返信", "備考"])
        for r in results:
            mvp = "OK" if r["mvp_ok"] else ("要確認" if r["mvp_ok"] is False else "-")
            kao = "OK" if r["kousakai_ok"] else ("要確認" if r["kousakai_ok"] is False else "-")
            rep = "OK" if r["reply_ok"] else ("要確認" if r["reply_ok"] is False else "-")
            note = r["error"] or ""
            w.writerow([r["channel_id"], r["channel_name"], mvp, kao, rep, note])

    print(f"\n結果を {out_path} に保存しました。")


if __name__ == "__main__":
    asyncio.run(main())
