"""
2月の週次提出率レポート（テスト用）／ 任意月の週次集計（月末アナウンス用）
ログから指定月を週ごとに集計し、提出率80%以上達成かを判定する。

実行: cd /Users/kasaimami/002_AI_ && source venv/bin/activate && python report_feb_weekly.py
      python report_feb_weekly.py nippou_logs/❤️日報：レッド.txt
"""
import calendar
import os
import re
import sys

_BASE = os.path.dirname(os.path.abspath(__file__))
NIPPOU_DIR = os.path.join(_BASE, "nippou_logs")

LOG_LINE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}\]\s+(.+?):\s+")

# 2月の週の定義（日付範囲の初日〜末日）
FEB_WEEKS = [
    (1, 7),   # 第1週 2/1-2/7
    (8, 14),  # 第2週 2/8-2/14
    (15, 21), # 第3週 2/15-2/21
    (22, 29), # 第4週 2/22-2/29（うるう年対応）
]


def get_weeks_for_month(year: int, month: int) -> list[tuple[int, int]]:
    """指定月の週の範囲リストを返す。(1-7), (8-14), (15-21), (22-末日)。"""
    last_day = calendar.monthrange(year, month)[1]
    return [(1, 7), (8, 14), (15, 21), (22, last_day)]


def get_week_index_for_month(day: int, year: int, month: int) -> int:
    """日が指定月の何週目か返す。1-based。"""
    weeks = get_weeks_for_month(year, month)
    for i, (start, end) in enumerate(weeks, 1):
        if start <= day <= end:
            return i
    return 0


def get_week_index(day: int) -> int:
    """日（1-29）が2月の何週目か返す。1-based。（後方互換）"""
    for i, (start, end) in enumerate(FEB_WEEKS, 1):
        if start <= day <= end:
            return i
    return 0


def parse_target_from_summary(summary_path: str) -> int | None:
    """サマリーファイルから「提出対象者（休会中除く）: N」を取得。"""
    if not os.path.exists(summary_path):
        return None
    pat = re.compile(r"提出対象者（休会中除く）:\s*(\d+)")
    with open(summary_path, "r", encoding="utf-8") as f:
        for line in f:
            m = pat.search(line)
            if m:
                return int(m.group(1))
    return None


def collect_monthly_weekly_submitters(
    lines: list[str], year: int, month: int
) -> dict[int, set[str]]:
    """ログ行から指定月の週別「その週に1回以上投稿した人」を集計。"""
    weeks = get_weeks_for_month(year, month)
    by_week: dict[int, set[str]] = {i: set() for i in range(1, len(weeks) + 1)}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = LOG_LINE_RE.match(line)
        if not m:
            continue
        date_str, name = m.group(1), m.group(2).strip()
        try:
            y, mo, d = int(date_str[:4]), int(date_str[5:7]), int(date_str[8:10])
        except (ValueError, IndexError):
            continue
        if y != year or mo != month:
            continue
        week_idx = get_week_index_for_month(d, year, month)
        if week_idx:
            by_week[week_idx].add(name)
    return by_week


def collect_feb_weekly_submitters(lines: list[str], year: int = 2026) -> dict[int, set[str]]:
    """ログ行から2月の週別「その週に1回以上投稿した人」を集計。（後方互換）"""
    return collect_monthly_weekly_submitters(lines, year, 2)


def run_monthly_weekly_report(
    log_path: str,
    summary_path: str,
    year: int,
    month: int,
    threshold_pct: float = 80.0,
) -> tuple[str, int, int, int, list[tuple[int, int, float, bool]]] | None:
    """
    指定月の週次提出率を計算する。
    返値: (チャンネル表示名, 提出対象者数, 達成週数, 総週数, [(週番号, 提出者数, 提出率, 達成)]) または None（失敗時）
    """
    if not os.path.exists(log_path) or not os.path.exists(summary_path):
        return None
    target_count = parse_target_from_summary(summary_path)
    if target_count is None or target_count <= 0:
        return None
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    weekly = collect_monthly_weekly_submitters(lines, year, month)
    weeks = get_weeks_for_month(year, month)
    details: list[tuple[int, int, float, bool]] = []
    achieved = 0
    for week_num in range(1, len(weeks) + 1):
        submitters = len(weekly.get(week_num, set()))
        rate = (submitters / target_count * 100) if target_count > 0 else 0
        ok = rate >= threshold_pct
        if ok:
            achieved += 1
        details.append((week_num, submitters, rate, ok))
    channel_name = os.path.splitext(os.path.basename(log_path))[0]
    return (channel_name, target_count, achieved, len(weeks), details)


def main() -> None:
    if len(sys.argv) >= 2:
        log_path = os.path.join(_BASE, sys.argv[1]) if not os.path.isabs(sys.argv[1]) else sys.argv[1]
    else:
        log_path = os.path.join(NIPPOU_DIR, "❤️日報：レッド.txt")

    if not os.path.exists(log_path):
        print(f"ログファイルが見つかりません: {log_path}")
        sys.exit(1)

    # サマリーは同じディレクトリで「ログ名_サマリー.txt」
    base_name = os.path.splitext(os.path.basename(log_path))[0]
    summary_path = os.path.join(os.path.dirname(log_path), f"{base_name}_サマリー.txt")
    target_count = parse_target_from_summary(summary_path)
    if target_count is None:
        print("サマリーから「提出対象者（休会中除く）」を取得できません。")
        print("手動で人数を指定する場合は: python report_feb_weekly.py <ログパス> <人数>")
        if len(sys.argv) >= 3 and sys.argv[2].isdigit():
            target_count = int(sys.argv[2])
        else:
            target_count = 19  # レッドの例としてデフォルト
            print(f"デフォルトの提出対象者数 {target_count} で計算します。")
    else:
        print(f"提出対象者（休会中除く）: {target_count} 名（サマリーより）")

    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    weekly = collect_feb_weekly_submitters(lines)
    threshold_pct = 80.0

    print("")
    print("=== 2月 週次提出率（80%以上達成判定） ===")
    print("※ 分母は現在の提出対象者数です。2月時点の在籍と異なる場合があります。")
    print("")
    achieved = 0
    for week_num, (start, end) in enumerate(FEB_WEEKS, 1):
        submitters = len(weekly[week_num])
        rate = (submitters / target_count * 100) if target_count > 0 else 0
        ok = rate >= threshold_pct
        if ok:
            achieved += 1
        status = "✓ 達成" if ok else "✗ 未達"
        print(f"第{week_num}週（2/{start}〜2/{end}）: 提出者 {submitters}/{target_count} → 提出率 {rate:.1f}%  {status}")
    print("")
    print(f"2月の週のうち {achieved}/4 週が {threshold_pct}% 以上でした。")
    if achieved == 4:
        print("→ 2月の週次提出率80%以上は達成しています。")
    else:
        print(f"→ 2月の週次提出率80%以上は未達（あと {4 - achieved} 週）です。")


if __name__ == "__main__":
    main()
