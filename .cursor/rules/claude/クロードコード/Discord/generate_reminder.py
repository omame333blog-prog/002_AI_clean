from datetime import date

# ====== 設定 ======
TODAY = date.today()
REMIND_THRESHOLD_DAYS = 7

# ====== データ ======
submissions = {
    'はせがわまな_P': [date(2026,2,28), date(2026,3,1)],
    'saco_P':         [date(2026,2,28), date(2026,3,1)],
    'けいK_P':        [date(2026,2,27)],
    'まいあ_P':       [date(2026,2,28)],
    'ねこねこ_P':     [date(2026,2,27), date(2026,2,28), date(2026,3,1)],
    'ヒナ_P':         [date(2026,2,28), date(2026,3,1)],
    'のの_P':         [date(2026,2,27), date(2026,2,28)],
    'つかちゃん_G':   [date(2026,2,27), date(2026,2,28), date(2026,3,1)],
    'まさみ_B':       [date(2026,3,1)],
    'おが_B':         [date(2026,3,1)],
    'もりこ_B':       [date(2026,2,26), date(2026,2,27), date(2026,2,28), date(2026,3,1)],
    'Chihiro_P':      [date(2026,2,26), date(2026,2,27), date(2026,2,28)],
}

# ====== リマインド対象を抽出 ======
remind_targets = []
ok_targets = []

for user, dates in submissions.items():
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
      <td><div class="msg-box" onclick="copyText(this)" title="クリックでコピー">
        {msg}
      </div></td>
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
    h1 {{
      font-size: 22px;
      font-weight: bold;
      margin-bottom: 4px;
    }}
    .meta {{
      color: #888;
      font-size: 13px;
      margin-bottom: 28px;
    }}
    h2 {{
      font-size: 16px;
      font-weight: bold;
      margin: 24px 0 10px;
      padding-left: 10px;
    }}
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
    td {{
      padding: 10px 14px;
      font-size: 14px;
      border-bottom: 1px solid #f0f0f0;
    }}
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
  <p class="meta">今日: {TODAY} ／ 基準: {REMIND_THRESHOLD_DAYS}日以上未提出をリマインド対象</p>

  <h2 class="warn">要リマインド ({len(remind_targets)}名)</h2>
  <table>
    <thead>
      <tr>
        <th>名前</th>
        <th>最終提出日</th>
        <th>状態</th>
        <th>メッセージ（クリックでコピー）</th>
      </tr>
    </thead>
    <tbody>{remind_rows}</tbody>
  </table>

  <h2 class="ok">提出済み ({len(ok_targets)}名)</h2>
  <table>
    <thead>
      <tr>
        <th>名前</th>
        <th>最終提出日</th>
        <th>状態</th>
        <th></th>
      </tr>
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

output_path = '/Users/kasaimami/Documents/アンチグラビティ/クロードコード/Discord3月/リマインド一覧.html'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'保存完了: {output_path}')
