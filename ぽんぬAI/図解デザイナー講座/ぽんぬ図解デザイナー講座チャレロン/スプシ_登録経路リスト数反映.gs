/**
 * チャレロン管理シート 登録者データからその日の日付の行の Q:CV を自動反映
 * 使い方: 登録者シートにCSVを貼り付け -> メニュー リスト数反映 -> 登録者シートから反映
 * シート名: 登録者 = CSV貼付先, オプチャリスト数 = 書き込み先
 */

const CONFIG = {
  // 登録者CSVを貼るシート名
  REGISTRANTS_SHEET_NAME: '登録者',
  // リスト数シート名(なければ先頭シートを使う)
  LIST_SHEET_NAME: 'オプチャリスト数',
  // 登録者シートの列(1始まり) UTAGEのCSVは 登録経路=22列目, 登録日時=24列目
  COL_登録経路: 22,
  COL_登録日時: 24,
  // リスト数シート: 2行目に共通A_冒頭1などのヘッダーがQ列以降にある。日付=B列、データ3行目～
  COL_日付: 2,
  HEADER_ROW: 2,
  DATA_START_ROW: 3,
  COL_Q: 17,   // Q列=17列目(共通A_冒頭1～)
  COL_CV: 100, // CV列=100列目(LPまで)
  COL_CU: 99,  // CU列=空欄なので「未反映」を入れて使う(旧)
  // 未反映がCY列などCVより右にある場合・今後項目が増える場合に COL_END を大きくする
  COL_END: 113 // Q列からここまで読み書き。CY=103 + 余裕10列分(DI列まで)
};

/**
 * 登録経路の表記を管理シートの列名に合わせる
 */
function normalizeRoute_(s) {
  if (s == null || String(s).trim() === '') return '空欄';
  const t = String(s).trim();
  // 【0206-0309】チャレロン共通A_冒頭1 → 共通A_冒頭1
  const m = t.match(/^【[^】]+】チャレロン(.+)$/);
  if (m) return m[1].trim();
  if (t.indexOf('既存リスト_LINE①') !== -1 || t === '既存LINE①') return '既存LINE①';
  if (t.indexOf('既存リスト_LINE②') !== -1 || t === '既存LINE②') return '既存LINE②';
  return t;
}

/**
 * 日付を管理シート形式に (2026/2/6 に統一)
 * - スプシの日付セルは Date オブジェクトで返るのでここで変換する
 * - 登録者CSVの文字列 "2026-02-06 12:00:00" も対応
 */
function toSheetDate_(val) {
  if (val == null || val === '') return null;
  if (val instanceof Date) {
    var y = val.getFullYear();
    var m = val.getMonth() + 1;
    var d = val.getDate();
    return y + '/' + m + '/' + d;
  }
  var str = String(val).trim();
  if (/^\d{4}\/\d{1,2}\/\d{1,2}$/.test(str)) return str;
  var match = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (!match) return null;
  var y = match[1], m = parseInt(match[2], 10), d = parseInt(match[3], 10);
  return y + '/' + m + '/' + d;
}

/**
 * 登録者シートを読んで 日付×登録経路 の集計オブジェクトを返す
 * 戻り値: { '2026/2/6': { '共通A_冒頭1': 5, ... }, ... }
 */
function aggregateRegistrants_(sheet) {
  const lastRow = sheet.getLastRow();
  const lastCol = Math.max(sheet.getLastColumn(), CONFIG.COL_登録日時);
  if (lastRow < 2) return {};
  const data = sheet.getRange(2, 1, lastRow, lastCol).getValues();
  const byDate = {};
  data.forEach(function (row) {
    const route = row[CONFIG.COL_登録経路 - 1];
    const dt = row[CONFIG.COL_登録日時 - 1];
    const dateStr = toSheetDate_(dt);
    if (!dateStr) return;
    const norm = normalizeRoute_(route);
    if (!byDate[dateStr]) byDate[dateStr] = {};
    byDate[dateStr][norm] = (byDate[dateStr][norm] || 0) + 1;
  });
  return byDate;
}

/**
 * リスト数シートのヘッダー行から 経路名→列番号(1始まり) のマップを作る
 */
function buildRouteToCol_(listSheet) {
  var numCols = CONFIG.COL_END - CONFIG.COL_Q + 1;
  const headerRow = listSheet.getRange(CONFIG.HEADER_ROW, CONFIG.COL_Q, 1, numCols).getValues()[0];
  const map = {};
  for (let c = 0; c < headerRow.length; c++) {
    const h = String(headerRow[c] || '').replace(/\n/g, '').trim();
    if (h && !map[h]) map[h] = CONFIG.COL_Q + c;
  }
  return map;
}

/**
 * メイン: 登録者シートから集計し、リスト数シートの該当行の Q:CV に書き込む
 * シートに「未反映」列があれば、経路に列がない人をそこに加算する(60人になる)
 */
function runListFillFromRegistrants() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const regSheet = ss.getSheetByName(CONFIG.REGISTRANTS_SHEET_NAME);
  if (!regSheet) {
    SpreadsheetApp.getUi().alert('"' + CONFIG.REGISTRANTS_SHEET_NAME + '" シートが見つかりません。登録者CSVを貼るシートを作成してください。');
    return;
  }
  let listSheet = ss.getSheetByName(CONFIG.LIST_SHEET_NAME);
  if (!listSheet) listSheet = ss.getSheets()[0];
  var cuCell = listSheet.getRange(CONFIG.HEADER_ROW, CONFIG.COL_CU);
  if (cuCell.isBlank() || String(cuCell.getValue()).trim() === '') {
    cuCell.setValue('未反映');
  }
  const byDate = aggregateRegistrants_(regSheet);
  const routeToCol = buildRouteToCol_(listSheet);
  var totalRegistrants = 0;
  for (var d in byDate) { for (var route in byDate[d]) totalRegistrants += byDate[d][route]; }
  var unmappedList = [];
  var unmappedCount = 0;
  const lastRow = listSheet.getLastRow();
  var numCols = CONFIG.COL_END - CONFIG.COL_Q + 1;
  const hasUnmappedCol = (routeToCol['未反映'] != null);
  for (var r = CONFIG.DATA_START_ROW; r <= lastRow; r++) {
    const dateVal = listSheet.getRange(r, CONFIG.COL_日付).getValue();
    const dateStr = toSheetDate_(dateVal);
    if (!dateStr) continue;
    const counts = byDate[dateStr];
    if (!counts) continue;
    const rowValues = listSheet.getRange(r, CONFIG.COL_Q, 1, numCols).getValues()[0];
    var unmappedInRow = 0;
    for (var routeName in counts) {
      const col = routeToCol[routeName];
      if (col != null) {
        const idx = col - CONFIG.COL_Q;
        rowValues[idx] = counts[routeName];
      } else {
        unmappedInRow += counts[routeName];
        if (unmappedList.indexOf(routeName) === -1) unmappedList.push(routeName);
      }
    }
    if (unmappedInRow > 0 && hasUnmappedCol) {
      const idx = routeToCol['未反映'] - CONFIG.COL_Q;
      rowValues[idx] = unmappedInRow;
    }
    unmappedCount += unmappedInRow;
    listSheet.getRange(r, CONFIG.COL_Q, 1, numCols).setValues([rowValues]);
  }
  var msg = '反映しました。\n登録者合計: ' + totalRegistrants + ' 人\n対象日付: ' + Object.keys(byDate).length + ' 日分';
  if (unmappedCount > 0) {
    msg += '\n\n【' + unmappedCount + ' 人】は経路に列がなく';
    if (hasUnmappedCol) msg += '「未反映」列に入れました。';
    else msg += '反映されていません。\nシートに「未反映」列を追加するか、経路名を追加してください。\n未対応の経路: ' + unmappedList.join(', ');
  }
  SpreadsheetApp.getUi().alert(msg);
}

/**
 * メニューを追加
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('リスト数反映')
    .addItem('登録者シートから反映', 'runListFillFromRegistrants')
    .addToUi();
}
