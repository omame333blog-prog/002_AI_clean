import csv
import re
from datetime import date, datetime

# ====== 設定 ======
TODAY = date.today()
REMIND_THRESHOLD_DAYS = 7
CSV_PATH = '/Users/kasaimami/Documents/アンチグラビティ/クロードコード/Discord3月/Discord_chat_Sun Feb 01 2026 00_00_00 GMT+0900 (日本標準時)_Sat Feb 28 2026 00_00_00 GMT+0900 (日本標準時).csv'
OUTPUT_PATH = '/Users/kasaimami/Documents/アンチグラビティ/クロードコード/Discord3月/リマインド一覧.html'

# ====== 日報判定パターン ======
REPORT_PATTERNS = [
    r'【.*?日報.*?】',
    r'【.*?の報告.*?】',
    r'【.*?報告.*?】',
    r'①ポストできたか',
    r'②今日できた',
    r'②昨日.*?できた',
    r'②できた',
]

# ====== 日付抽出パターン（コンテンツ内の対象日） ======
DATE_PATTERNS = [
    # 【3月1日(日)日報】など
    r'【\s*(\d{1,2})月(\d{1,2})日',
    # 【2/28（土）日報】など
    r'【\s*(\d{1,2})[/／](\d{1,2})',
    # 2月28日(土) のような行
    r'^(\d{1,2})月(\d{1,2})日',
    # 1月30日 のような形
    r'(\d{1,2})月(\d{1,2})日',
]

def is_daily_report(content):
    if not content:
        return False
    for pat in REPORT_PATTERNS:
        if re.search(pat, content):
            return True
    return False

def extract_report_date(content, post_date):
    """コンテンツ内から日報対象日を抽出。見つからなければ投稿日を使用。"""
    year = post_date.year
    for pat in DATE_PATTERNS:
        m = re.search(pat, content, re.MULTILINE)
        if m:
            try:
                month = int(m.group(1))
                day = int(m.group(2))
                # 年またぎ考慮（1月の投稿で12月の日付が出たら前年）
                if post_date.month == 1 and month == 12:
                    year -= 1
                return date(year, month, day)
            except:
                pass
    # 複数日まとめ提出（「1月30.31日」「2月27日〜28日」）の場合は最後の日を使用
    m = re.search(r'(\d{1,2})月.*?(\d{1,2})日', content)
    if m:
        try:
            month = int(m.group(1))
            day = int(m.group(2))
            return date(year, month, day)
        except:
            pass
    return post_date

# ====== CSVを解析 ======
# ユーザーごとの提出日セット
user_submissions = {}  # {username: set of report dates}

with open(CSV_PATH, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        username = row.get('Username', '').strip()
        content = row.get('Content', '').strip()
        date_str = row.get('Date', '').strip()

        if not username or not content:
            continue

        # 投稿日を解析（"2026-02-01,00:25:08" 形式）
        try:
            date_part = date_str.split(',')[0]
            post_date = datetime.strptime(date_part, '%Y-%m-%d').date()
        except:
            continue

        # 日報かどうか判定
        if not is_daily_report(content):
            continue

        # 対象日を抽出
        report_date = extract_report_date(content, post_date)

        if username not in user_submissions:
            user_submissions[username] = set()
        user_submissions[username].add(report_date)

# ====== リマインド判定 ======
remind_targets = []
ok_targets = []

for user, dates in user_submissions.items():
    last = max(dates)
    days = (TODAY - last).days
    if days >= REMIND_THRESHOLD_DAYS:
        remind_targets.append((user, last, days))
    else:
        ok_targets.append((user, last, days))

remind_targets.sort(key=lambda x: x[2], reverse=True)
ok_targets.sort(key=lambda x: x[2])

# ====== HTML生成 ======
def badge(days):
    if days >= 14:
        return f'<span class="badge red">{days}日未提出</span>'
    elif days >= 7:
        return f'<span class="badge orange">{days}日未提出</span>'
    else:
        return f'<span class="badge green">{days}日前に提出済</span>'

remind_rows = ''
for user, last, days in remind_targets:
    msg = f'@{user} 最近どうした？{last.month}/{last.day}以来だよ！'
    remind_rows += f'''
    <tr class="remind-row">
      <td class="name">{user}</td>
      <td>{last.month}/{last.day}</td>
      <td>{badge(days)}</td>
      <td><div class="msg-box" onclick="copyText(this)" title="クリックでコピー">{msg}</div></td>
    </tr>'''

ok_rows = ''
for user, last, days in ok_targets:
    ok_rows += f'''
    <tr>
      <td class="name">{user}</td>
      <td>{last.month}/{last.day}</td>
      <td>{badge(days)}</td>
      <td>—</td>
    </tr>'''

html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>日報リマインド一覧</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: "Hiragino Sans", "Helvetica Neue", sans-serif;
      background: #f0f4f8;
      color: #333;
      padding: 32px;
    }}
    h1 {{ font-size: 22px; font-weight: bold; margin-bottom: 4px; }}
    .meta {{ color: #888; font-size: 13px; margin-bottom: 28px; }}
    h2 {{ font-size: 16px; font-weight: bold; margin: 24px 0 10px; padding-left: 10px; }}
    h2.warn {{ border-left: 4px solid #e53935; color: #c62828; }}
    h2.ok   {{ border-left: 4px solid #43a047; color: #2e7d32; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: white;
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }}
    th {{
      background: #37474f;
      color: white;
      padding: 10px 14px;
      text-align: left;
      font-size: 13px;
    }}
    td {{ padding: 10px 14px; font-size: 14px; border-bottom: 1px solid #f0f0f0; }}
    tr:last-child td {{ border-bottom: none; }}
    .remind-row {{ background: #fff8f8; }}
    .name {{ font-weight: bold; }}
    .badge {{
      display: inline-block;
      padding: 3px 10px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: bold;
    }}
    .badge.red    {{ background: #ffebee; color: #c62828; }}
    .badge.orange {{ background: #fff3e0; color: #e65100; }}
    .badge.green  {{ background: #e8f5e9; color: #2e7d32; }}
    .msg-box {{
      background: #fff3e0;
      border: 1px dashed #ffb74d;
      border-radius: 6px;
      padding: 6px 12px;
      font-size: 13px;
      cursor: pointer;
      user-select: all;
      transition: background 0.2s;
    }}
    .msg-box:hover {{ background: #ffe0b2; }}
    .msg-box.copied {{ background: #c8e6c9; border-color: #66bb6a; }}
    .toast {{
      position: fixed;
      bottom: 30px;
      left: 50%;
      transform: translateX(-50%);
      background: #323232;
      color: white;
      padding: 10px 24px;
      border-radius: 24px;
      font-size: 14px;
      opacity: 0;
      transition: opacity 0.3s;
      pointer-events: none;
    }}
    .toast.show {{ opacity: 1; }}
  </style>
</head>
<body>
  <h1>日報リマインド一覧</h1>
  <p class="meta">
    今日: {TODAY} ／ データ期間: 2026年2月 ／ 基準: {REMIND_THRESHOLD_DAYS}日以上未提出をリマインド対象<br>
    解析メンバー数: {len(user_submissions)}名
  </p>

  <h2 class="warn">要リマインド ({len(remind_targets)}名)</h2>
  <table>
    <thead>
      <tr><th>名前</th><th>最終提出日</th><th>状態</th><th>メッセージ（クリックでコピー）</th></tr>
    </thead>
    <tbody>{remind_rows}</tbody>
  </table>

  <h2 class="ok">提出済み ({len(ok_targets)}名)</h2>
  <table>
    <thead>
      <tr><th>名前</th><th>最終提出日</th><th>状態</th><th></th></tr>
    </thead>
    <tbody>{ok_rows}</tbody>
  </table>

  <div class="toast" id="toast">コピーしました！</div>
  <script>
    function copyText(el) {{
      const text = el.innerText.trim();
      navigator.clipboard.writeText(text).then(() => {{
        el.classList.add('copied');
        setTimeout(() => el.classList.remove('copied'), 1500);
        const toast = document.getElementById('toast');
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 2000);
      }});
    }}
  </script>
</body>
</html>'''

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'解析完了: {len(user_submissions)}名のメンバーを検出')
print(f'要リマインド: {len(remind_targets)}名 / 提出済み: {len(ok_targets)}名')
print(f'保存先: {OUTPUT_PATH}')
print()
print('--- 要リマインド一覧 ---')
for user, last, days in remind_targets:
    print(f'  {user:<25} 最終: {last.month}/{last.day} ({days}日前)')
