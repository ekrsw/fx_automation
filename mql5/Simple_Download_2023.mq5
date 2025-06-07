//+------------------------------------------------------------------+
//|                                        Simple_Download_2023.mq5 |
//|                        シンプルな2023年データダウンロードスクリプト |
//|                                                  Version 1.0 |
//+------------------------------------------------------------------+
#property copyright "FX Trading System"
#property version   "1.00"
#property script_show_inputs

//--- Input parameters
input string   SYMBOL_TO_DOWNLOAD = "USDJPY";              // ダウンロードする通貨ペア
input string   API_URL = "http://127.0.0.1:8000";          // FastAPI Server URL
input int      BATCH_SIZE = 500;                           // バッチサイズ（小さめ）

//--- Global variables
bool is_processing = false;

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
bool SendHistoricalDataBatch(string json_data, string symbol, int batch_number)
{
    string url = API_URL + "/api/v1/mt5/receive-historical-batch";
    string headers = "Content-Type: application/json\r\n";
    
    char post_data[];
    char result[];
    string result_headers;
    
    // JSON文字列をChar配列に変換
    StringToCharArray(json_data, post_data, 0, StringLen(json_data));
    
    int timeout = 10000; // 10秒タイムアウト
    int res = WebRequest("POST", url, headers, timeout, post_data, result, result_headers);
    
    if(res == 200)
    {
        Print("Batch ", batch_number, " sent successfully (HTTP 200)");
        return true;
    }
    else
    {
        Print("HTTP Error: ", res, " for batch ", batch_number);
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
//| 履歴データ取得・送信関数                                        |
//+------------------------------------------------------------------+
bool GetAndSendHistoricalData(string symbol, datetime start_date, datetime end_date)
{
    if(is_processing)
    {
        Print("Already processing historical data request");
        return false;
    }
    
    is_processing = true;
    
    Print("=== Starting historical data collection ===");
    Print("Symbol: ", symbol);
    Print("Start: ", TimeToString(start_date));
    Print("End: ", TimeToString(end_date));
    
    // シンボルを選択
    if(!SymbolSelect(symbol, true))
    {
        Print("ERROR: Failed to select symbol: ", symbol);
        is_processing = false;
        return false;
    }
    
    // 利用可能なバー数を確認
    int total_bars = Bars(symbol, PERIOD_H1, start_date, end_date);
    if(total_bars <= 0)
    {
        Print("ERROR: No bars found for the specified period");
        is_processing = false;
        return false;
    }
    
    Print("Total bars to process: ", total_bars);
    WriteLog("Historical data request: " + symbol + " (" + IntegerToString(total_bars) + " bars)");
    
    // バッチ処理でデータを取得・送信
    int processed_bars = 0;
    int batch_count = 0;
    datetime current_start = start_date;
    
    while(processed_bars < total_bars)
    {
        int bars_to_get = MathMin(BATCH_SIZE, total_bars - processed_bars);
        
        // 履歴データを取得
        MqlRates rates[];
        int copied = CopyRates(symbol, PERIOD_H1, current_start, bars_to_get, rates);
        
        if(copied <= 0)
        {
            Print("ERROR: Failed to copy rates. Requested: ", bars_to_get);
            Sleep(2000); // 2秒待機して再試行
            continue;
        }
        
        // データをJSON形式で送信
        string json_data = BuildHistoricalDataJSON(symbol, rates, copied, batch_count);
        
        if(SendHistoricalDataBatch(json_data, symbol, batch_count))
        {
            processed_bars += copied;
            batch_count++;
            
            Print("Progress: ", processed_bars, "/", total_bars, " (", 
                  DoubleToString((double)processed_bars/total_bars*100, 1), "%)");
            
            // 進捗をログに記録
            if(batch_count % 5 == 0)
            {
                WriteLog("Progress: " + IntegerToString(processed_bars) + "/" + IntegerToString(total_bars) + " bars");
            }
        }
        else
        {
            Print("ERROR: Failed to send batch ", batch_count);
            WriteLog("ERROR: Failed to send batch " + IntegerToString(batch_count));
        }
        
        // 次のバッチの開始時刻を更新
        if(copied > 0)
        {
            current_start = rates[copied-1].time + 3600; // 1時間追加
        }
        
        // サーバー負荷を考慮して少し待機
        Sleep(200); // 200ms待機
    }
    
    Print("=== Historical data collection completed ===");
    Print("Total processed: ", processed_bars, " bars");
    WriteLog("Historical data collection completed: " + IntegerToString(processed_bars) + " bars");
    
    is_processing = false;
    return true;
}

//+------------------------------------------------------------------+
//| Script program start function                                   |
//+------------------------------------------------------------------+
void OnStart()
{
    Print("=== 2023年履歴データダウンロード開始 ===");
    WriteLog("Download script started");
    
    // 2023年の期間を設定
    datetime start_date = StringToTime("2023.01.01 00:00:00");
    datetime end_date = StringToTime("2023.12.31 23:59:59");
    
    // データダウンロード実行
    if(GetAndSendHistoricalData(SYMBOL_TO_DOWNLOAD, start_date, end_date))
    {
        Print("=== データダウンロード成功 ===");
        WriteLog("Download completed successfully for " + SYMBOL_TO_DOWNLOAD);
    }
    else
    {
        Print("=== データダウンロード失敗 ===");
        WriteLog("Download failed for " + SYMBOL_TO_DOWNLOAD);
    }
}