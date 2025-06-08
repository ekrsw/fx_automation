# MT5統合技術ガイド

**バージョン**: 2.0  
**最終更新**: 2025年6月8日  
**対象**: MT5-Python API統合によるデータ取得システム

## 📋 概要

本ガイドはMetaTrader 5 (MT5)とPython FastAPIサーバー間のデータ統合について、実装からトラブルシューティングまでの技術詳細を記載しています。

## 🏗 システム構成

### アーキテクチャ
```
[MT5 Terminal] ←→ [MQL5 Expert Advisor] ←HTTP→ [Python FastAPI] ←→ [SQLite DB]
```

### 通信プロトコル
- **プロトコル**: HTTP/1.1
- **データ形式**: JSON
- **エンコーディング**: UTF-8
- **認証**: なし (ローカル通信)

## 🔧 MT5側実装

### 1. 基本設定

#### WebRequest許可設定
```
1. MT5 → ツール → オプション → エキスパートアドバイザー
2. ☑ アルゴリズム取引を許可する
3. ☑ WebRequestを許可するURLリスト
4. URLリスト追加: http://127.0.0.1:8000
```

**重要**: `localhost`ではなく`127.0.0.1`を使用する

### 2. MQL5スクリプト構造

#### 基本テンプレート
```mql5
#property copyright "FX Automation System"
#property version   "1.00"

input string ServerURL = "http://127.0.0.1:8000/api/v1/mt5/receive-historical-batch";
input string Symbol = "USDJPY";
input int BatchSize = 100;
input int MaxRetries = 3;

int OnInit()
{
    // 初期化処理
    return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
    // 終了処理
}
```

#### データ取得の実装
```mql5
bool DownloadYearData(datetime startTime, datetime endTime)
{
    MqlRates rates[];
    ArraySetAsSeries(rates, false);
    
    // 1時間足データをコピー
    int copied = CopyRates(Symbol, PERIOD_H1, startTime, endTime, rates);
    
    if(copied <= 0)
    {
        Print("データコピー失敗: ", GetLastError());
        return false;
    }
    
    // バッチ処理でデータを送信
    int batches = (copied + BatchSize - 1) / BatchSize;
    
    for(int batch = 0; batch < batches; batch++)
    {
        int start = batch * BatchSize;
        int end = MathMin(start + BatchSize, copied);
        
        string jsonData = PrepareJSONBatch(rates, start, end);
        
        bool sent = false;
        for(int retry = 0; retry < MaxRetries && !sent; retry++)
        {
            sent = SendDataToServer(jsonData, end - start);
            if(!sent && retry < MaxRetries - 1)
            {
                Sleep(1000 * (retry + 1));
            }
        }
    }
    
    return true;
}
```

### 3. JSON生成

#### 正しいJSON形式
```mql5
string PrepareJSONBatch(MqlRates &rates[], int start, int end)
{
    string json = "{";
    json += "\"symbol\":\"" + Symbol + "\",";
    json += "\"timeframe\":\"H1\",";
    json += "\"batch_number\":" + IntegerToString(start/BatchSize) + ",";
    json += "\"check_duplicates\":true,";
    json += "\"data\":[";
    
    for(int i = start; i < end; i++)
    {
        if(i > start) json += ",";
        
        // タイムスタンプの適切なフォーマット
        string timestamp = TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS);
        StringReplace(timestamp, " ", " ");
        
        json += "{";
        json += "\"timestamp\":\"" + timestamp + "\",";
        json += "\"open\":" + StringFormat("%.5f", rates[i].open) + ",";
        json += "\"high\":" + StringFormat("%.5f", rates[i].high) + ",";
        json += "\"low\":" + StringFormat("%.5f", rates[i].low) + ",";
        json += "\"close\":" + StringFormat("%.5f", rates[i].close) + ",";
        json += "\"volume\":" + IntegerToString(rates[i].tick_volume);
        json += "}";
    }
    
    json += "],";
    json += "\"check_duplicates\":true";
    json += "}";
    
    return json;
}
```

#### 重要なポイント
1. **数値フォーマット**: `StringFormat("%.5f", value)` を使用
2. **タイムスタンプ**: `TIME_DATE|TIME_SECONDS` 形式
3. **UTF-8エンコーディング**: `CP_UTF8` を明示的に指定

### 4. HTTP通信実装

#### WebRequest実装
```mql5
bool SendDataToServer(string jsonData, int dataCount)
{
    char post[];
    char result[];
    string headers = "Content-Type: application/json\r\n";
    
    // 正しい文字列変換
    int jsonLength = StringLen(jsonData);
    StringToCharArray(jsonData, post, 0, -1, CP_UTF8);
    
    // null終端文字の適切な処理
    if(ArraySize(post) > jsonLength) {
        ArrayResize(post, jsonLength);
    }
    
    int timeout = 30000; // 30秒
    int res = WebRequest("POST", ServerURL, headers, timeout, post, result, headers);
    
    if(res == 200)
    {
        string response = CharArrayToString(result);
        if(StringFind(response, "\"success\":true") >= 0)
        {
            // 成功時の処理
            return true;
        }
    }
    else if(res == -1)
    {
        int error = GetLastError();
        if(error == 4014)
        {
            Print("WebRequestが許可されていません");
            // 設定手順を表示
        }
    }
    
    return false;
}
```

## 🐍 Python側実装

### 1. API エンドポイント

#### データ受信エンドポイント
```python
@router.post("/mt5/receive-historical-batch")
async def receive_historical_batch(batch_data: Dict[str, Any]):
    """
    MT5 EAからの履歴データバッチを受信（重複チェック対応）
    """
    try:
        symbol = batch_data.get("symbol")
        batch_number = batch_data.get("batch_number", 0)
        data_records = batch_data.get("data", [])
        check_duplicates = batch_data.get("check_duplicates", False)
        
        if not symbol or not data_records:
            raise HTTPException(status_code=400, detail="シンボルまたはデータが不足")
        
        # 重複チェック付きで保存
        result = await save_mt5_historical_data_with_duplicate_check(
            symbol, data_records, check_duplicates
        )
        
        return {
            "success": True,
            "symbol": symbol,
            "batch_number": batch_number,
            "received_records": len(data_records),
            "saved": result["saved"],
            "duplicates": result["duplicates"],
            "message": f"保存: {result['saved']}件, 重複: {result['duplicates']}件"
        }
        
    except Exception as e:
        logger.error(f"MT5バッチデータ受信エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 2. 重複チェック機能

#### 効率的な重複検出
```python
async def save_mt5_historical_data_with_duplicate_check(
    symbol: str, 
    data_records: List[Dict[str, Any]], 
    check_duplicates: bool = True
) -> Dict[str, int]:
    """
    重複チェック付きデータ保存
    """
    if not data_records:
        return {"saved": 0, "duplicates": 0}
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    saved_count = 0
    duplicate_count = 0
    
    # 既存タイムスタンプの事前取得（パフォーマンス最適化）
    existing_timestamps = set()
    if check_duplicates:
        cursor.execute("""
            SELECT DISTINCT timestamp FROM market_data 
            WHERE symbol = ?
        """, (symbol,))
        existing_timestamps = {row[0] for row in cursor.fetchall()}
    
    for record in data_records:
        try:
            timestamp = record["timestamp"]
            
            # 重複チェック
            if check_duplicates and timestamp in existing_timestamps:
                duplicate_count += 1
                continue
            
            cursor.execute("""
                INSERT OR IGNORE INTO market_data 
                (symbol, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                timestamp,
                float(record["open"]),
                float(record["high"]),
                float(record["low"]),
                float(record["close"]),
                int(record.get("volume", 0))
            ))
            
            if cursor.rowcount > 0:
                saved_count += 1
                if check_duplicates:
                    existing_timestamps.add(timestamp)
            else:
                duplicate_count += 1
                
        except Exception as e:
            logger.warning(f"データ保存スキップ: {record.get('timestamp')} - {str(e)}")
    
    conn.commit()
    conn.close()
    
    return {"saved": saved_count, "duplicates": duplicate_count}
```

### 3. データベース設計

#### テーブル構造
```sql
CREATE TABLE IF NOT EXISTS market_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp 
ON market_data(symbol, timestamp);

CREATE INDEX IF NOT EXISTS idx_market_data_timestamp 
ON market_data(timestamp);
```

## 🐛 トラブルシューティング

### 1. 共通エラーと解決策

#### WebRequestエラー 4014
```
問題: WebRequestが許可されていません
原因: MT5のWebRequest設定が無効
解決: オプション → エキスパートアドバイザー → WebRequest許可
```

#### HTTPエラー 422 (JSON無効)
```
問題: JSON decode error - Expecting ',' delimiter
原因: JSONの構文エラー、通常は文字列終端処理
解決: StringToCharArrayの適切な使用
```

#### 接続エラー (HTTPエラー 7)
```
問題: Failed to connect to server
原因: サーバー未起動またはポート違い
解決: Pythonサーバーの起動確認、ポート8000使用確認
```

#### タイムスタンプ形式混在
```
問題: ドット形式とハイフン形式の混在
原因: MT5のTimeToString関数の出力形式
解決: データベース側での後処理統一
```

### 2. デバッグ手法

#### MT5側デバッグ
```mql5
// JSON内容の確認
Print("JSON Length: ", StringLen(jsonData));
Print("JSON Start: ", StringSubstr(jsonData, 0, 100));
Print("JSON End: ", StringSubstr(jsonData, StringLen(jsonData) - 100, 100));

// レスポンス解析
if(res == 200) {
    string response = CharArrayToString(result);
    Print("Server Response: ", response);
}
```

#### Python側デバッグ
```python
# ログレベル設定
logging.getLogger("app.api.mt5_data").setLevel(logging.DEBUG)

# 詳細ログ出力
logger.debug(f"Received {len(data_records)} records for {symbol}")
logger.debug(f"Sample data: {data_records[0] if data_records else 'No data'}")
```

### 3. パフォーマンス最適化

#### バッチサイズ調整
```
小さすぎる (< 50):   通信オーバーヘッド大
適切 (100-1000):     バランス良好
大きすぎる (> 2000): タイムアウトリスク
```

#### メモリ管理
```mql5
// 大量データ処理時は配列のリサイズを最小限に
ArrayResize(rates, expected_size);
ArraySetAsSeries(rates, false);
```

#### データベース最適化
```sql
-- 定期的なバキューム
VACUUM;

-- インデックス再構築
REINDEX;
```

## 🔒 セキュリティ考慮事項

### 1. ネットワークセキュリティ
- ローカルホスト通信のみ使用
- ファイアウォール設定でポート8000を内部のみに制限
- HTTPS化は外部アクセス時のみ検討

### 2. データ保護
- 市場データは公開情報のため機密性は低い
- バックアップの暗号化は推奨
- ログファイルでの機密情報露出に注意

### 3. アクセス制御
- MT5ターミナルのアクセス制限
- データベースファイルの適切な権限設定
- API認証は将来の拡張で検討

## 📈 監視とメンテナンス

### 1. 日常監視項目
```python
# データ件数監視
daily_count = cursor.execute("""
    SELECT COUNT(*) FROM market_data 
    WHERE DATE(created_at) = DATE('now')
""").fetchone()[0]

# エラー率監視
error_rate = failed_requests / total_requests * 100

# レスポンス時間監視
avg_response_time = sum(response_times) / len(response_times)
```

### 2. 定期メンテナンス
```sql
-- 月次: 古いログの削除
DELETE FROM logs WHERE created_at < datetime('now', '-3 months');

-- 四半期: データ整合性チェック
SELECT symbol, COUNT(*), MIN(timestamp), MAX(timestamp) 
FROM market_data GROUP BY symbol;

-- 年次: データベース最適化
VACUUM;
ANALYZE;
```

### 3. アラート設定
```python
# 重要なアラート条件
if error_rate > 5:
    send_alert("MT5統合エラー率が5%を超過")

if daily_count == 0:
    send_alert("本日のデータ取得が0件")

if response_time > 10:
    send_alert("レスポンス時間が10秒を超過")
```

## 🚀 今後の拡張計画

### 1. 短期拡張 (1ヶ月以内)
- 複数通貨ペア同時処理
- リアルタイムデータ取得
- 増分更新機能

### 2. 中期拡張 (3ヶ月以内)
- 複数ブローカー対応
- データ品質監視
- 自動復旧機能

### 3. 長期拡張 (6ヶ月以内)
- 機械学習による異常検知
- クラウド統合
- 高可用性構成

---

**作成者**: Claude AI Assistant  
**技術レビュー**: 実装テスト完了  
**承認日**: 2025年6月8日