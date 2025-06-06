# MQL5 Expert Advisor セットアップガイド

## 1. 前提条件
- MetaTrader 5 がインストールされていること
- WebRequest が有効になっていること

## 2. EA インストール手順

### Step 1: MetaEditor でEAを開く
1. MetaTrader 5 を起動
2. F4 キーを押してMetaEditorを開く
3. `File` → `Open` → `FX_Trading_EA.mq5` を選択

### Step 2: コンパイル
1. F7 キーを押すか、`Compile` ボタンをクリック
2. エラーがないことを確認

### Step 3: WebRequest 設定
1. MetaTrader 5 で `Tools` → `Options` → `Expert Advisors` タブ
2. `Allow WebRequest for listed URL:` にチェック
3. 以下のURLを追加:
   ```
   http://127.0.0.1:8000
   https://127.0.0.1:8000
   ```

### Step 4: EA 起動
1. Navigator パネルから `Expert Advisors` を展開
2. `FX_Trading_EA` をチャートにドラッグ&ドロップ
3. パラメータを確認して `OK` をクリック

## 3. パラメータ設定

| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| API_URL | http://127.0.0.1:8000 | FastAPI サーバーURL |
| DATA_SEND_INTERVAL | 300 | データ送信間隔（秒） |
| TARGET_SYMBOL | USDJPY | 対象通貨ペア |
| ENABLE_LOGGING | true | ログ出力有効/無効 |
| TIMEFRAME_PERIOD | PERIOD_M5 | タイムフレーム |

## 4. 動作確認方法

### Phase 1 テスト項目:
1. **接続テスト**: EA起動時にFastAPIサーバーに接続できるか
2. **データ送信**: 5分間隔でUSD/JPYのOHLCデータが送信されるか
3. **ログ出力**: `MQL5/Files/FX_Trading_EA.log` にログが記録されるか

### 確認コマンド:
```bash
# FastAPI サーバー起動
cd /path/to/FX_automation
python main.py

# ログ確認
tail -f MQL5/Files/FX_Trading_EA.log
```

## 5. トラブルシューティング

### よくある問題:
1. **WebRequest エラー**: URL設定を確認
2. **接続エラー**: FastAPIサーバーが起動しているか確認
3. **コンパイルエラー**: MQL5のバージョンを確認

### ログファイル場所:
- Windows: `%APPDATA%/MetaQuotes/Terminal/{TERMINAL_ID}/MQL5/Files/`
- 共通フォルダ: MetaTrader 5インストールフォルダ/MQL5/Files/