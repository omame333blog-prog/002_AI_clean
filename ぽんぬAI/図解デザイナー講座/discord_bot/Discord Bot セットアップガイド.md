# Discord Bot セットアップガイド

日報チャンネルのエラーチェック（MVP・交流会・返信）を自動化するBotの設定手順です。

---

## 1. Discord Developer Portal でBotを作成

1. [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
2. 右上の **「New Application」** をクリック
3. 名前を入力（例：`日報チェックBot`）→ Create
4. 左メニューから **「Bot」** を選択
5. **「Add Bot」** をクリック
6. **「Reset Token」** をクリック → 表示されたトークンを**必ずコピーして安全な場所に保存**
   - ⚠️ このトークンは他人に知られないようにしてください

---

## 2. Botに権限を設定

1. Botのページで **「Privileged Gateway Intents」** を確認
2. **「MESSAGE CONTENT INTENT」** を **ON** にする（メッセージ内容を読み取るため必須）
3. **「Save Changes」** で保存

---

## 3. Botをサーバーに招待

1. 左メニュー **「OAuth2」** → **「URL Generator」**
2. **SCOPES** で **「bot」** にチェック
3. **BOT PERMISSIONS** で以下にチェック：
   - ✅ View Channels（チャンネルの閲覧）
   - ✅ Read Message History（メッセージ履歴の閲覧）
4. 下部に表示されたURLをコピーしてブラウザで開く
5. 図解デザイナー講座のサーバーを選択 → 認証
6. Botがサーバーに参加したことを確認

---

## 4. チャンネルIDを取得

1. Discordの **「設定」** → **「詳細設定」** → **「開発者モード」** をON
2. チェックしたい日報チャンネルで **右クリック** → **「IDをコピー」**
3. 各部屋のチャンネルIDをメモ（例：ブラウン部屋、ブルー部屋など）

---

## 5. 設定ファイルを作成

1. `config.example.env` を `config.env` にコピー
2. `config.env` を開き、以下を記入：
   - `DISCORD_BOT_TOKEN`：Botのトークン
   - `CHANNEL_IDS`：チェック対象のチャンネルID（カンマ区切り）
   - `NIKKI_TANTO_USERNAMES`：日報担当のDiscord Username（返信チェック用、カンマ区切り）

---

## 6. 実行

```bash
cd discord_bot
pip install -r requirements.txt
python nikki_check_bot.py
```

結果は `日報チェック結果.csv` に出力されます。

---

## トラブルシューティング

| エラー | 対処 |
|--------|------|
| 「Missing Access」 | Botにチャンネル閲覧権限があるか確認。サーバー設定でチャンネル権限を確認 |
| 「Unknown Message」 | MESSAGE CONTENT INTENT がONか確認 |
| 「403 Forbidden」 | トークンが正しいか、Botがサーバーに参加しているか確認 |
