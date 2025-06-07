//+------------------------------------------------------------------+
//|                                        Download_2023_Only.mq5  |
//|                        2023年専用データダウンロードスクリプト   |
//|                                                  Version 1.0 |
//+------------------------------------------------------------------+
#property copyright "FX Trading System"
#property version   "1.00"
#property script_show_inputs

//--- Input parameters
input string   SYMBOL_TO_DOWNLOAD = "USDJPY";              // ダウンロードする通貨ペア
input string   API_URL = "http://127.0.0.1:8000";          // FastAPI Server URL
input int      BATCH_SIZE = 500;                           // バッチサイズ

//--- 2023年専用設定
datetime start_2023 = D'2023.01.06 00:00:00';  // 2023年1月6日から
datetime end_2023   = D'2023.12.31 23:59:59';  // 2023年12月31日まで

//+------------------------------------------------------------------+
//| ログ出力関数                                                    |
//+------------------------------------------------------------------+
void WriteLog(string message)
{
    string timestamp = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
    string log_entry = timestamp + " - " + message;
    Print(log_entry);
}

//+------------------------------------------------------------------+
//| HTTPデータ送信関数                                              |
//+------------------------------------------------------------------+
bool SendHistoricalDataBatch(string json_data, int batch_number)
{
    string url = API_URL + "/api/v1/mt5/receive-historical-batch";
    string headers = "Content-Type: application/json\r\n";
    
    char post_data[];
    char result[];
    string result_headers;
    
    // JSON文字列をChar配列に変換
    StringToCharArray(json_data, post_data, 0, StringLen(json_data));
    
    int timeout = 15000; // 15秒タイムアウト
    int res = WebRequest("POST", url, headers, timeout, post_data, result, result_headers);
    
    if(res == 200)
    {
        Print("✓ Batch ", batch_number, " sent successfully");
        return true;
    }
    else
    {
        Print("✗ HTTP Error: ", res, " for batch ", batch_number);
        return false;
    }
}

//+------------------------------------------------------------------+
//| JSON構築関数                                                    |
//+------------------------------------------------------------------+
string BuildHistoricalDataJSON(string symbol, MqlRates& rates[], int count, int batch_number)
{
    string json = "{\n";
    json += "  \"symbol\": \"" + symbol + "\",\n";
    json += "  \"batch_number\": " + IntegerToString(batch_number) + ",\n";
    json += "  \"timeframe\": \"H1\",\n";
    json += "  \"data\": [\n";
    
    for(int i = 0; i < count; i++)
    {
        json += "    {\n";
        json += "      \"timestamp\": \"" + TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS) + "\",\n";
        json += "      \"open\": " + DoubleToString(rates[i].open, 5) + ",\n";
        json += "      \"high\": " + DoubleToString(rates[i].high, 5) + ",\n";
        json += "      \"low\": " + DoubleToString(rates[i].low, 5) + ",\n";
        json += "      \"close\": " + DoubleToString(rates[i].close, 5) + ",\n";
        json += "      \"volume\": " + IntegerToString(rates[i].tick_volume) + "\n";
        json += "    }";
        
        if(i < count - 1) json += ",";
        json += "\n";
    }
    
    json += "  ]\n";
    json += "}";
    
    return json;
}

//+------------------------------------------------------------------+
//| Script program start function                                   |
//+------------------------------------------------------------------+
void OnStart()
{
    Print("=== 2023年専用履歴データダウンロード開始 ===");
    Print("期間: ", TimeToString(start_2023), " ～ ", TimeToString(end_2023));
    Print("通貨ペア: ", SYMBOL_TO_DOWNLOAD);
    
    // シンボルを選択
    if(!SymbolSelect(SYMBOL_TO_DOWNLOAD, true))
    {
        Print("✗ ERROR: シンボル選択失敗: ", SYMBOL_TO_DOWNLOAD);
        return;
    }
    
    // 利用可能なバー数を確認
    int total_bars = Bars(SYMBOL_TO_DOWNLOAD, PERIOD_H1, start_2023, end_2023);
    if(total_bars <= 0)
    {
        Print("✗ ERROR: 指定期間にデータがありません");
        return;
    }
    
    Print("📊 処理対象バー数: ", total_bars);
    Print("📦 バッチサイズ: ", BATCH_SIZE);
    Print("📈 予想バッチ数: ", MathCeil((double)total_bars / BATCH_SIZE));
    
    // データ取得開始
    int processed_bars = 0;
    int batch_count = 0;
    int success_batches = 0;
    int failed_batches = 0;
    
    while(processed_bars < total_bars)
    {
        int bars_to_get = MathMin(BATCH_SIZE, total_bars - processed_bars);
        
        // 履歴データを取得
        MqlRates rates[];
        int copied = CopyRates(SYMBOL_TO_DOWNLOAD, PERIOD_H1, 
                              start_2023 + processed_bars * 3600, bars_to_get, rates);
        
        if(copied <= 0)
        {
            Print("⚠ WARNING: データコピー失敗 (要求: ", bars_to_get, "件)");
            Sleep(3000); // 3秒待機して再試行
            continue;
        }
        
        // 2023年のデータのみフィルタリング
        MqlRates filtered_rates[];
        int filtered_count = 0;
        
        for(int i = 0; i < copied; i++)
        {
            if(rates[i].time >= start_2023 && rates[i].time <= end_2023)
            {
                ArrayResize(filtered_rates, filtered_count + 1);
                filtered_rates[filtered_count] = rates[i];
                filtered_count++;
            }
        }
        
        if(filtered_count > 0)
        {
            // JSON構築・送信
            string json_data = BuildHistoricalDataJSON(SYMBOL_TO_DOWNLOAD, filtered_rates, filtered_count, batch_count);
            
            if(SendHistoricalDataBatch(json_data, batch_count))
            {
                success_batches++;
                processed_bars += copied;
                
                Print("📈 進捗: ", processed_bars, "/", total_bars, " (", 
                      DoubleToString((double)processed_bars/total_bars*100, 1), "%) - ",
                      "2023年データ: ", filtered_count, "件送信");
            }
            else
            {
                failed_batches++;
                Print("❌ バッチ送信失敗: ", batch_count);
            }
        }
        else
        {
            Print("ℹ 2023年データなし (スキップ)");
            processed_bars += copied;
        }
        
        batch_count++;
        
        // 進捗状況表示
        if(batch_count % 10 == 0)
        {
            Print("=== 中間報告 ===");
            Print("処理済みバッチ: ", batch_count);
            Print("成功: ", success_batches, " / 失敗: ", failed_batches);
            Print("処理済みバー: ", processed_bars, "/", total_bars);
        }
        
        // サーバー負荷軽減
        Sleep(300);
    }
    
    Print("=== 2023年データダウンロード完了 ===");
    Print("✅ 成功バッチ: ", success_batches);
    Print("❌ 失敗バッチ: ", failed_batches);
    Print("📊 総処理バー: ", processed_bars);
    Print("🎯 期間: 2023年1月6日～12月31日");
}