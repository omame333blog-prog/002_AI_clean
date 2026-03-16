import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import numpy as np
from datetime import date, timedelta

# 日本語フォント設定（Hiragino Sans を使用）
plt.rcParams['font.family'] = 'Hiragino Sans'

# ====== 設定 ======
TODAY = date.today()                 # 今日の日付（自動）
REMIND_THRESHOLD_DAYS = 7           # 何日以上未提出でリマインド対象にするか

# ====== データ定義 ======
# Discordログから解析したユーザーと提出日（レポート対象日）
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

# ====== リマインド検出 ======
def get_last_submission(user):
    dates = submissions.get(user, [])
    return max(dates) if dates else None

def days_since(last_date):
    return (TODAY - last_date).days if last_date else None

remind_targets = []
for user in submissions:
    last = get_last_submission(user)
    d = days_since(last)
    if d is not None and d >= REMIND_THRESHOLD_DAYS:
        remind_targets.append((user, last, d))

# 経過日数が多い順にソート
remind_targets.sort(key=lambda x: x[2], reverse=True)

# ====== コンソール出力 ======
print('=' * 50)
print(f'  日報リマインド対象者 （今日: {TODAY}）')
print(f'  基準: {REMIND_THRESHOLD_DAYS}日以上 日報提出なし')
print('=' * 50)
if remind_targets:
    for user, last, d in remind_targets:
        last_str = f'{last.month}/{last.day}'
        print(f'  {user:<20}  最終提出: {last_str}  ({d}日前)')
else:
    print('  リマインド対象者なし')
print('=' * 50)
print()
print('--- コピー用メッセージ ---')
for user, last, d in remind_targets:
    last_str = f'{last.month}/{last.day}'
    print(f'@{user} 最近どうした？前回提出から{d}日経ってるよ！({last_str}以来)')
print()

# ====== 週の定義（月〜日） ======
weeks = [
    ('2/23週', date(2026,2,23), date(2026,3,1)),
    ('3/2週',  date(2026,3,2),  date(2026,3,8)),
    ('3/9週',  date(2026,3,9),  date(2026,3,15)),
    ('3/16週', date(2026,3,16), date(2026,3,22)),
    ('3/23週', date(2026,3,23), date(2026,3,29)),
]

def count_weekly(user_dates, week_start, week_end):
    return sum(1 for d in user_dates if week_start <= d <= week_end)

# リマインド対象ユーザーのセット
remind_users = {u for u, _, _ in remind_targets}

# ====== ユーザーをリマインド対象→提出数でソート ======
users = sorted(
    submissions.keys(),
    key=lambda u: (u not in remind_users, len(submissions[u])),
    reverse=False  # リマインド対象を上に
)
# リマインド対象を先頭に、それ以外は提出数降順
remind_list = sorted([u for u in users if u in remind_users],
                     key=lambda u: days_since(get_last_submission(u)), reverse=True)
ok_list = sorted([u for u in users if u not in remind_users],
                 key=lambda u: len(submissions[u]), reverse=True)
users = remind_list + ok_list

# ====== 全日付リスト（可視化範囲：2/26〜3/2） ======
all_dates = [date(2026,2,26) + timedelta(days=i) for i in range(5)]
date_labels = ['2/26(木)', '2/27(金)', '2/28(土)', '3/1(日)', '3/2(月)']

# 提出マトリックス作成
matrix = np.zeros((len(users), len(all_dates)), dtype=int)
for i, user in enumerate(users):
    for d in submissions[user]:
        if d in all_dates:
            j = all_dates.index(d)
            matrix[i][j] = 1

# 週別提出有無マトリックス
week_matrix = np.zeros((len(users), len(weeks)), dtype=int)
for i, user in enumerate(users):
    for j, (wlabel, wstart, wend) in enumerate(weeks):
        cnt = count_weekly(submissions[user], wstart, wend)
        week_matrix[i][j] = 1 if cnt >= 1 else 0

# ====== 可視化 ======
fig = plt.figure(figsize=(16, 9), facecolor='#1a1a2e')

# タイトル
fig.text(0.5, 0.96, '日報提出状況 ｜ 週1回以上提出チェック（3月）',
         ha='center', va='top', fontsize=18, fontweight='bold', color='white')
fig.text(0.5, 0.925, f'データ期間：2026年2月26日〜3月2日  ／  今日：{TODAY}',
         ha='center', va='top', fontsize=11, color='#aaaacc')

# リマインド対象がいれば上部に警告表示
if remind_targets:
    names_str = '、'.join([u for u, _, _ in remind_targets])
    fig.text(0.5, 0.895,
             f'要リマインド（{REMIND_THRESHOLD_DAYS}日以上未提出）: {names_str}',
             ha='center', va='top', fontsize=10,
             color='#ff8a65',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#3e1a0a', edgecolor='#ff6e40', alpha=0.9))

# --- 左：日別ヒートマップ ---
ax1 = fig.add_axes([0.05, 0.08, 0.42, 0.79])
ax1.set_facecolor('#16213e')

colors_day = {0: '#2d2d4e', 1: '#4fc3f7'}
cell_w, cell_h = 0.8, 0.8

for i, user in enumerate(users):
    for j, d in enumerate(all_dates):
        val = matrix[i][j]
        color = colors_day[val]
        rect = mpatches.FancyBboxPatch(
            (j - cell_w/2, i - cell_h/2), cell_w, cell_h,
            boxstyle="round,pad=0.05",
            facecolor=color, edgecolor='#1a1a2e', linewidth=1.5
        )
        ax1.add_patch(rect)
        if val == 1:
            ax1.text(j, i, '◯', ha='center', va='center', fontsize=14,
                     color='#ffffff', fontweight='bold')

# 軸設定
ax1.set_xlim(-0.6, len(all_dates) - 0.4)
ax1.set_ylim(-0.6, len(users) - 0.4)
ax1.set_xticks(range(len(all_dates)))
ax1.set_xticklabels(date_labels, fontsize=9, color='#ccddff', rotation=15)
ax1.set_yticks(range(len(users)))

# ユーザー名：リマインド対象はオレンジ色で表示
yticklabels = []
for user in users:
    if user in remind_users:
        last = get_last_submission(user)
        d = days_since(last)
        yticklabels.append(f'{user}  !{d}日')
    else:
        yticklabels.append(user)

ylabels = ax1.set_yticklabels(yticklabels, fontsize=10)
for label, user in zip(ylabels, users):
    label.set_color('#ff8a65' if user in remind_users else '#e0e0ff')

ax1.xaxis.set_ticks_position('top')
ax1.xaxis.set_label_position('top')
ax1.tick_params(axis='both', which='both', length=0)
for spine in ax1.spines.values():
    spine.set_visible(False)
ax1.set_title('日別提出カレンダー', color='white', fontsize=13, fontweight='bold', pad=20)

# 提出数ラベル
for i, user in enumerate(users):
    cnt = len(submissions[user])
    ax1.text(len(all_dates) - 0.2, i, f' {cnt}件',
             ha='left', va='center', fontsize=9, color='#99bbff')

# リマインド対象の行に背景ハイライト
for i, user in enumerate(users):
    if user in remind_users:
        bg = mpatches.FancyBboxPatch(
            (-0.55, i - 0.48), len(all_dates) - 0.9 + 0.55, 0.96,
            boxstyle="round,pad=0.02",
            facecolor='#3e1a0a', edgecolor='#ff6e40', linewidth=1.2, alpha=0.4
        )
        ax1.add_patch(bg)

# --- 右：週別提出確認チャート ---
ax2 = fig.add_axes([0.55, 0.08, 0.42, 0.79])
ax2.set_facecolor('#16213e')

color_ok   = '#69f0ae'
color_ng   = '#ef5350'
color_none = '#37474f'
data_cutoff = date(2026, 3, 2)

for i, user in enumerate(users):
    # リマインド対象の行ハイライト
    if user in remind_users:
        bg = mpatches.FancyBboxPatch(
            (-0.48, i - 0.46), len(weeks) - 0.04, 0.92,
            boxstyle="round,pad=0.02",
            facecolor='#3e1a0a', edgecolor='#ff6e40', linewidth=1.2, alpha=0.4
        )
        ax2.add_patch(bg)

    for j, (wlabel, wstart, wend) in enumerate(weeks):
        has_data = wstart <= data_cutoff
        if not has_data:
            color = color_none
            symbol = '－'
            sym_color = '#546e7a'
        elif week_matrix[i][j] == 1:
            color = color_ok
            symbol = '◯'
            sym_color = '#004d40'
        else:
            color = color_ng
            symbol = '×'
            sym_color = '#b71c1c'

        rect = mpatches.FancyBboxPatch(
            (j - 0.4, i - 0.38), 0.8, 0.76,
            boxstyle="round,pad=0.05",
            facecolor=color, edgecolor='#1a1a2e', linewidth=1.5
        )
        ax2.add_patch(rect)
        ax2.text(j, i, symbol, ha='center', va='center', fontsize=16,
                 color=sym_color, fontweight='bold')

# 軸設定
ax2.set_xlim(-0.6, len(weeks) - 0.4)
ax2.set_ylim(-0.6, len(users) - 0.4)
ax2.set_xticks(range(len(weeks)))
ax2.set_xticklabels([w[0] for w in weeks], fontsize=9, color='#ccddff')
ax2.set_yticks(range(len(users)))
ax2.set_yticklabels([''] * len(users))
ax2.xaxis.set_ticks_position('top')
ax2.xaxis.set_label_position('top')
ax2.tick_params(axis='both', which='both', length=0)
for spine in ax2.spines.values():
    spine.set_visible(False)
ax2.set_title('週別提出チェック（週1回以上）', color='white', fontsize=13, fontweight='bold', pad=20)

# 週ごとの達成率
for j, (wlabel, wstart, wend) in enumerate(weeks):
    if wstart <= data_cutoff:
        total = len(users)
        ok = sum(week_matrix[:, j])
        rate = ok / total * 100
        ax2.text(j, -0.55, f'{ok}/{total}\n({rate:.0f}%)',
                 ha='center', va='top', fontsize=8, color='#aaddff')

# 凡例
patches = [
    mpatches.Patch(color=color_ok,      label='提出あり（週1回以上達成）'),
    mpatches.Patch(color=color_ng,      label='提出なし'),
    mpatches.Patch(color=color_none,    label='データなし'),
    mpatches.Patch(color=colors_day[1], label='日報提出日'),
    mpatches.Patch(color='#ff6e40',     label=f'要リマインド（{REMIND_THRESHOLD_DAYS}日以上未提出）'),
]
fig.legend(handles=patches, loc='lower center', ncol=5,
           fontsize=9, facecolor='#2d2d4e', edgecolor='#4444aa',
           labelcolor='white', framealpha=0.8,
           bbox_to_anchor=(0.5, 0.01))

# 保存
output_path = '/Users/kasaimami/Documents/アンチグラビティ/クロードコード/Discord3月/日報提出率_スキル図.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f'\n保存完了: {output_path}')
