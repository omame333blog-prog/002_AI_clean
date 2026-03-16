# 日報チェックBot

図解デザイナー講座の日報チャンネルで、以下のエラーを自動検知するDiscord Botです。

| チェック項目 | 条件 | 出力 |
|--------------|------|------|
| **MVP** | 木曜日までに週間MVP発表がない | 要確認 |
| **交流会** | 直近30日以内に交流会の記録がない | 要確認 |
| **返信** | 日報担当が8日以内に返信していない（「見ました」のみは除外） | 要確認 |

## セットアップ

1. [Discord Bot セットアップガイド.md](./Discord%20Bot%20セットアップガイド.md) に従い、Botを作成・招待
2. `config.example.env` を `config.env` にコピー
3. `config.env` にトークン・チャンネルID・日報担当を記入
4. `pip install -r requirements.txt`

## 実行

```bash
python nikki_check_bot.py
```

結果は `日報チェック結果.csv` に出力されます。

## 定期実行（cron例）

毎週金曜 10:00 に実行する例：

```cron
0 10 * * 5 cd /path/to/discord_bot && python nikki_check_bot.py
```

## ファイル構成

- `nikki_check_bot.py` - メインスクリプト
- `config.env` - 設定（gitに含めないこと）
- `config.example.env` - 設定サンプル
- `Discord Bot セットアップガイド.md` - Bot作成手順
