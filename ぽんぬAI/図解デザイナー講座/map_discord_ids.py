#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
メンバー表にDiscord IDをマッピングするスクリプト

ルール:
1. アンダースコア(_ または ＿)の前の部分だけでマッチング
2. 矢印(→)がある場合は矢印以降の名前を使用（現在の名前）
3. 絵文字は無視
4. 同じ正規化名で複数の異なるIDがある場合はID列に入れず、要確認リストに出力
5. 大文字小文字は区別しない（RIOとrioは同一）
6. IDの末尾の句読点（. , 等）は無視して同一とみなす（kei1003とkei1003.は同一）
7. 番号が異なるIDは別人の可能性あり→要確認
"""

import csv
import re
from collections import defaultdict

# 絵文字を除去する正規表現（※ヒラガナ・カタカナは除外）
# 24C2-1F251は範囲が広くヒラガナ(U+3040付近)も含むため使用しない
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # Misc Symbols and Pictographs
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U00002600-\U000027BF"  # Misc symbols, Dingbats
    "\U0001F900-\U0001FAFF"  # Supplemental Symbols (🪼など)
    "]+",
    flags=re.UNICODE
)


def remove_emoji(text):
    """絵文字を除去"""
    if not text:
        return ""
    return EMOJI_PATTERN.sub("", text).strip()


def normalize_id_for_comparison(discord_id):
    """
    IDの同一判定用に正規化
    - 小文字に統一
    - 末尾の句読点（. , スペース）を除去
    → 大文字小文字・末尾のピリオド等の違いは同一とみなす
    """
    if not discord_id or not isinstance(discord_id, str):
        return ""
    s = discord_id.lower().strip()
    s = s.rstrip(".,;: 　")
    return s


def normalize_name_for_matching(name):
    """
    マッチング用に名前を正規化
    - 矢印(→)がある場合は矢印以降の部分
    - ハイフン+ランク(-R, -G, -S, -P)は除去
    - アンダースコア(_ または ＿)の前の部分のみ
    - 絵文字を除去
    """
    if not name or not isinstance(name, str):
        return ""
    
    # 矢印がある場合は矢印以降を使用
    if "→" in name:
        name = name.split("→")[-1].strip()
    
    # ハイフン+ランク(-R, -G, -S, -P)を除去（Ka-neko のような名前は維持）
    for hyphen in ["-", "－"]:
        if hyphen in name:
            parts = name.split(hyphen)
            last_part = remove_emoji(parts[-1]).strip()
            if last_part.upper() in ['R', 'G', 'S', 'P'] and len(last_part) <= 2:
                name = hyphen.join(parts[:-1]).strip()
                break
    
    # アンダースコア（半角・全角・類似文字）の前の部分のみ
    underscore_chars = ["_", "＿", "‗"]
    for uc in underscore_chars:
        if uc in name:
            name = name.split(uc)[0].strip()
            break
    
    # 絵文字を除去
    name = remove_emoji(name).strip()
    
    return name


def load_teishutu_mappings(file_paths):
    """
    添削提出シートから名前→IDのマッピングを読み込み
    同じ正規化名で複数の異なるIDがある場合は除外（要確認用に記録）
    - 名前は大文字小文字を区別せずグルーピング（RIOとrioは同一）
    - IDは大文字小文字・末尾の句読点を無視して同一判定（番号が違えば別人）
    戻り値: (確定マッピング {正規化名小文字: ID}, 要確認リスト)
    """
    # 正規化名（小文字） → {IDの集合, 元の名前の例}
    raw_mapping = defaultdict(lambda: {"ids": set(), "original_names": set()})
    
    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for _ in range(13):
                    next(reader)
                for row in reader:
                    if len(row) >= 4:
                        name = row[2].strip() if row[2] else ""
                        discord_id = row[3].strip() if row[3] else ""
                        if name and discord_id and not name.startswith("①"):
                            normalized = normalize_name_for_matching(name)
                            if normalized:
                                key = normalized.lower()
                                raw_mapping[key]["ids"].add(discord_id)
                                raw_mapping[key]["original_names"].add(name)
        except FileNotFoundError:
            print(f"警告: ファイルが見つかりません {file_path}")
    
    confirmed = {}
    verification_list = []
    
    for key, data in raw_mapping.items():
        ids = data["ids"]
        original_names = list(data["original_names"])
        
        # IDを正規化してユニーク数をカウント（大文字小文字・末尾句読点は同一扱い）
        normalized_ids = {normalize_id_for_comparison(i) for i in ids}
        normalized_ids.discard("")  # 空は除外
        
        if len(normalized_ids) == 1:
            confirmed[key] = list(ids)[0]  # 代表として最初のIDを使用
        elif len(normalized_ids) > 1:
            verification_list.append({
                "正規化名": key,
                "元の名前の例": " / ".join(sorted(original_names)[:5]),
                "ID一覧": " / ".join(sorted(ids)),
                "ID数": len(ids)
            })
    
    return confirmed, verification_list


def main():
    # ファイルパス
    teishutu_2026 = "/Users/kasaimami/Downloads/【図解デザイナー講座】添削提出シート - 2026年1月〜 (1).csv"
    teishutu_2025 = "/Users/kasaimami/Downloads/【図解デザイナー講座】添削提出シート - 2025年10月〜.csv"
    member_path = "/Users/kasaimami/Downloads/無題のスプレッドシート - メンバー＆課題進捗表.csv"
    output_path = "/Users/kasaimami/002_AI_/ぽんぬAI/図解デザイナー講座/メンバー＆課題進捗表_Discord ID追加.csv"
    verification_path = "/Users/kasaimami/002_AI_/ぽんぬAI/図解デザイナー講座/要確認リスト_Discord ID.csv"
    
    # 添削シートからマッピングを読み込み（2026を優先、2025で補完）
    confirmed, verification_list = load_teishutu_mappings([teishutu_2026, teishutu_2025])
    
    # 要確認リストを出力
    with open(verification_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["正規化名", "元の名前の例", "ID一覧", "ID数"])
        writer.writeheader()
        writer.writerows(verification_list)
    
    print(f"要確認リスト: {verification_path} ({len(verification_list)}件)")
    
    # メンバー表を読み込み、Discord ID列を追加
    output_rows = []
    matched_count = 0
    
    with open(member_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0:
                new_row = row[:4] + ['Discord ID'] + row[4:]
                output_rows.append(new_row)
            elif i == 1 or i == 2:
                new_row = row[:4] + [''] + row[4:] if len(row) > 4 else row + [''] * max(0, 5 - len(row))
                output_rows.append(new_row)
            else:
                name = row[3] if len(row) > 3 else ""
                discord_id = ""
                
                if name:
                    normalized = normalize_name_for_matching(name)
                    key = normalized.lower() if normalized else ""
                    if key and key in confirmed:
                        discord_id = confirmed[key]
                        matched_count += 1
                
                new_row = row[:4] + [discord_id] + row[4:] if len(row) > 4 else row + [discord_id]
                output_rows.append(new_row)
    
    # メンバー表を出力
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(output_rows)
    
    print(f"メンバー表: {output_path}")
    print(f"  - 確定マッピング数: {len(confirmed)}")
    print(f"  - IDを入れた行数: {matched_count}")


if __name__ == "__main__":
    main()
