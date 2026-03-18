#!/usr/bin/env python3
"""
文字数カウントスクリプト
4パターンの文字数を出力します。
"""
import sys

def count_chars(text: str) -> dict:
    # スペース類：半角スペース、全角スペース、タブ
    SPACES = {' ', '　', '\t'}
    NEWLINES = {'\n', '\r'}

    # 改行含む・スペース含む
    total = len(text)

    # 改行含む・スペース除く
    no_space = sum(1 for c in text if c not in SPACES)

    # 改行除く・スペース含む
    no_newline = sum(1 for c in text if c not in NEWLINES)

    # 改行除く・スペース除く
    no_space_no_newline = sum(1 for c in text if c not in SPACES and c not in NEWLINES)

    return {
        "改行含む・スペース含む": total,
        "改行含む・スペース除く": no_space,
        "改行除く・スペース含む": no_newline,
        "改行除く・スペース除く": no_space_no_newline,
    }

if __name__ == "__main__":
    text = sys.stdin.read()
    results = count_chars(text)
    for label, count in results.items():
        print(f"{label}: {count}")
