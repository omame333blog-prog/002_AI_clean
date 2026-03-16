/**
 * 【図解デザイナー講座】添削提出シート
 * 提出から7日経過しても「添削完了」がついていない行を検出してアラート
 *
 * 使い方:
 * 1. 添削提出シート（スプレッドシート）を開く
 * 2. 拡張機能 > Apps Script でこのスクリプトを貼り付けて保存
 * 3. メニュー「添削アラート」>「未完了をチェック」で今すぐ確認
 * 4. 毎日自動でメール通知したい場合は「トリガーを設定」を実行
 */

const CONFIG = {
  // データが始まる行（1行目はリンク等、2行目空、3行目がヘッダーの場合）
  HEADER_ROW: 3,
  DATA_START_ROW: 4,
  // 自動実行（トリガー）で使うシート名。未設定なら手動実行時の「今開いているシート」を使う
  SHEET_NAME: '2026年1月〜',
  // 列番号（1始まり）。シートの列構成に合わせて変更可
  COL_タイムスタンプ: 1,   // A列 = 提出日時
  COL_添削可否: 13,       // M列。M・Nが空＝添削なしなのでアラート対象外
  COL_添削完了: 14,       // N列 = TRUE/FALSE（ヘッダーで「添削完了」の列）
  COL_提出内容: 6,        // ④提出内容（アラート表示用）
  COL_添削担当者: 7,      // ⑤添削担当者（アラート表示用）
  COL_プロセスチェック可否: 11,  // K列。NG or 添削なし＝添削しないのでアラート対象外
  // 何日過ぎたら「遅れ」とするか
  DAYS_OVERDUE: 7,
  // 通知先メール（トリガーでメール送信する場合。空なら送らない）
  NOTIFY_EMAIL: 'omame333.blog@gmail.com, koranomac@gmail.com, yokonatsu8@gmail.com'
};

/**
 * 現在のスプレッドシートで「添削完了」列のインデックスをヘッダーから取得（1始まり）
 * 列がずれている場合に自動で合わせる
 */
function get添削完了ColumnIndex_(sheet) {
  const headerRange = sheet.getRange(CONFIG.HEADER_ROW, 1, CONFIG.HEADER_ROW, 20);
  const headers = headerRange.getValues()[0];
  for (let i = 0; i < headers.length; i++) {
    if (String(headers[i]).trim() === '添削完了') return i + 1;
  }
  return CONFIG.COL_添削完了;
}

/**
 * 7日経過しても添削完了になっていない行の情報を取得
 * @return {Array<{row: number, 提出日: Date, 提出内容: string, 担当者: string}>}
 */
function getOverdueRows_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = (CONFIG.SHEET_NAME && CONFIG.SHEET_NAME.trim())
    ? ss.getSheetByName(CONFIG.SHEET_NAME.trim())
    : ss.getActiveSheet();
  if (!sheet) {
    Logger.log('シートが見つかりません: ' + CONFIG.SHEET_NAME);
    return [];
  }
  const lastRow = sheet.getLastRow();
  if (lastRow < CONFIG.DATA_START_ROW) return [];

  const col添削完了 = get添削完了ColumnIndex_(sheet);
  const col提出内容 = CONFIG.COL_提出内容;
  const col担当者 = CONFIG.COL_添削担当者;

  const now = new Date();
  const overdueMs = CONFIG.DAYS_OVERDUE * 24 * 60 * 60 * 1000;
  const result = [];

  const dataRange = sheet.getRange(CONFIG.DATA_START_ROW, 1, lastRow, Math.max(col添削完了, col提出内容, col担当者));
  const rows = dataRange.getValues();
  const rowCount = rows.length;

  for (let i = 0; i < rowCount; i++) {
    const row = rows[i];
    const rowNumber = CONFIG.DATA_START_ROW + i;
    const timestampVal = row[CONFIG.COL_タイムスタンプ - 1];
    const 添削完了Val = row[col添削完了 - 1];
    const 提出内容 = row[col提出内容 - 1] != null ? String(row[col提出内容 - 1]).trim() : '';
    const 担当者 = row[col担当者 - 1] != null ? String(row[col担当者 - 1]).trim() : '';

    // 添削完了が TRUE ならスキップ
    const isDone = 添削完了Val === true || String(添削完了Val).toUpperCase() === 'TRUE';
    if (isDone) continue;

    // K列がNG or 添削なし＝添削対象外なのでアラートに出さない
    const プロセスチェック可否 = String(row[CONFIG.COL_プロセスチェック可否 - 1] || '').trim();
    if (プロセスチェック可否.toUpperCase() === 'NG' || プロセスチェック可否 === '添削なし') continue;

    // M・N列が両方空（黒）＝添削なしなのでアラートに出さない
    const 添削可否Val = row[CONFIG.COL_添削可否 - 1];
    const isEmpty = function (v) { return v == null || String(v).trim() === ''; };
    if (isEmpty(添削可否Val) && isEmpty(添削完了Val)) continue;

    // タイムスタンプを日付に
    let submitDate = null;
    if (timestampVal instanceof Date) {
      submitDate = timestampVal;
    } else if (timestampVal) {
      const str = String(timestampVal).trim();
      const m = str.match(/^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})/);
      if (m) submitDate = new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10));
    }
    if (!submitDate || isNaN(submitDate.getTime())) continue;

    const elapsed = now.getTime() - submitDate.getTime();
    if (elapsed >= overdueMs) {
      result.push({
        row: rowNumber,
        提出日: submitDate,
        提出内容: 提出内容 || '(内容なし)',
        担当者: 担当者 || '(担当者なし)'
      });
    }
  }
  return result;
}

/**
 * 未完了の行をチェックしてダイアログで表示
 */
function checkOverdueAndShowAlert() {
  const overdue = getOverdueRows_();
  if (overdue.length === 0) {
    SpreadsheetApp.getUi().alert('添削アラート', '7日経過で未完了の提出はありません。', SpreadsheetApp.getUi().ButtonSet.OK);
    return;
  }

  const lines = overdue.map(function (o) {
    const d = o.提出日;
    const dateStr = d.getFullYear() + '/' + (d.getMonth() + 1) + '/' + d.getDate();
    return '行' + o.row + ' | ' + dateStr + ' | ' + o.担当者 + ' | ' + (o.提出内容.length > 30 ? o.提出内容.substring(0, 30) + '…' : o.提出内容);
  });
  const message = '7日経過しているのに添削完了になっていない提出が ' + overdue.length + ' 件あります。\n\n' + lines.join('\n');
  SpreadsheetApp.getUi().alert('添削アラート（要対応）', message, SpreadsheetApp.getUi().ButtonSet.OK);
}

/**
 * 未完了の行をチェックしてメール送信（NOTIFY_EMAIL が設定されている場合）
 */
function checkOverdueAndSendEmail() {
  const overdue = getOverdueRows_();
  const email = (CONFIG.NOTIFY_EMAIL || '').trim();
  if (!email) {
    SpreadsheetApp.getUi().alert('NOTIFY_EMAIL が未設定です。スクリプト内 CONFIG.NOTIFY_EMAIL に通知先メールアドレスを入れてください。');
    return;
  }
  if (overdue.length === 0) return;

  const lines = overdue.map(function (o) {
    const d = o.提出日;
    const dateStr = d.getFullYear() + '/' + (d.getMonth() + 1) + '/' + d.getDate();
    return '行' + o.row + ' | ' + dateStr + ' | ' + o.担当者 + ' | ' + o.提出内容;
  });
  const subject = '【添削アラート】7日経過で未完了が ' + overdue.length + ' 件あります';
  const body = '以下の提出は7日経過していますが、添削完了になっていません。\n\n' + lines.join('\n') + '\n\n※このメールは添削提出シートのApps Scriptから送信されています。';
  GmailApp.sendEmail(email, subject, body);
  SpreadsheetApp.getUi().alert('送信しました', '通知先 ' + email + ' にメールを送りました。', SpreadsheetApp.getUi().ButtonSet.OK);
}

/**
 * テスト配信：NOTIFY_EMAIL に「テストです」メールを1通送る（届くか確認用）
 */
function sendTestEmail() {
  const email = (CONFIG.NOTIFY_EMAIL || '').trim();
  if (!email) {
    SpreadsheetApp.getUi().alert('NOTIFY_EMAIL が未設定です。CONFIG にメールアドレスを入れてください。');
    return;
  }
  const subject = '【添削アラート】テスト配信';
  const body = 'これはテスト配信です。\nこのメールが届いていれば、本番のアラートも同じアドレスに届きます。\n\n' + new Date().toLocaleString('ja-JP');
  GmailApp.sendEmail(email, subject, body);
  SpreadsheetApp.getUi().alert('送信しました', email + ' にテストメールを送りました。受信トレイを確認してください。', SpreadsheetApp.getUi().ButtonSet.OK);
}

/**
 * 毎日決まった時間に実行する用（トリガーから呼ばれる）
 * 未完了が1件以上あれば NOTIFY_EMAIL に送信
 */
function runDailyOverdueCheck() {
  const overdue = getOverdueRows_();
  const email = (CONFIG.NOTIFY_EMAIL || '').trim();
  if (overdue.length === 0 || !email) return;

  const lines = overdue.map(function (o) {
    const d = o.提出日;
    const dateStr = d.getFullYear() + '/' + (d.getMonth() + 1) + '/' + d.getDate();
    return '行' + o.row + ' | ' + dateStr + ' | ' + o.担当者 + ' | ' + o.提出内容;
  });
  const subject = '【添削アラート】7日経過で未完了が ' + overdue.length + ' 件あります';
  const body = '以下の提出は7日経過していますが、添削完了になっていません。\n\n' + lines.join('\n');
  GmailApp.sendEmail(email, subject, body);
}

/**
 * メニューを追加
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('添削アラート')
    .addItem('未完了をチェック（今すぐ表示）', 'checkOverdueAndShowAlert')
    .addItem('未完了をメール送信', 'checkOverdueAndSendEmail')
    .addItem('テスト配信を送る', 'sendTestEmail')
    .addToUi();
}
