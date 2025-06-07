//+------------------------------------------------------------------+
//|                                         Download_2023_Data.mq5 |
//|                              2023年履歴データダウンロードスクリプト |
//|                                                  Version 1.0 |
//+------------------------------------------------------------------+
#property copyright "FX Trading System"
#property version   "1.00"
#property script_show_inputs

//--- Input parameters
input string   SYMBOL_TO_DOWNLOAD = "USDJPY";              // ダウンロードする通貨ペア
input int      YEAR_TO_DOWNLOAD = 2023;                    // ダウンロードする年
input bool     DOWNLOAD_ALL_MAJOR_PAIRS = false;           // 主要6ペア全て
input string   API_URL = "http://127.0.0.1:8000";          // FastAPI Server URL
input int      BATCH_SIZE = 1000;                          // バッチサイズ
input int      DELAY_MS = 100;                             // 送信間隔

//--- Global variables
string         log_file = "Download_2023_Data.log";

//+------------------------------------------------------------------+
//| Script program start function                                   |
//+------------------------------------------------------------------+
void OnStart()
{
    Print("=== 2023年履歴データダウンロード開始 ===");
    WriteLog("Download script started - " + TimeToString(TimeCurrent()));
    
    if(DOWNLOAD_ALL_MAJOR_PAIRS)
    {
        DownloadMajorPairsData(YEAR_TO_DOWNLOAD);
    }
    else
    {
        DownloadYearData(SYMBOL_TO_DOWNLOAD, YEAR_TO_DOWNLOAD, PERIOD_H1);
    }
    
    Print("=== 2023年履歴データダウンロード完了 ===");
    WriteLog("Download script completed - " + TimeToString(TimeCurrent()));
}

//+------------------------------------------------------------------+
//| 履歴データ取得・送信関数                                        |
//+------------------------------------------------------------------+
bool GetAndSendHistoricalData(string symbol, datetime start_date, datetime end_date, ENUM_TIMEFRAMES timeframe)
{
    if(is_processing)
    {
        Print("Already processing historical data request");
        return false;
    }
    
    is_processing = true;
    
    Print("Starting historical data collection for ", symbol);
    Print("Period: ", TimeToString(start_date), " to ", TimeToString(end_date));
    Print("Timeframe: ", EnumToString(timeframe));
    
    // シンボルを選択
    if(!SymbolSelect(symbol, true))
    {
        Print("ERROR: Failed to select symbol: ", symbol);
        is_processing = false;
        return false;
    }
    
    // バー数を計算
    int total_bars = Bars(symbol, timeframe, start_date, end_date);
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
        int copied = CopyRates(symbol, timeframe, current_start, bars_to_get, rates);
        
        if(copied <= 0)
        {
            Print("ERROR: Failed to copy rates. Bars requested: ", bars_to_get);
            Sleep(1000); // 1秒待機して再試行
            continue;
        }
        
        // データをJSON形式で送信
        string json_data = BuildHistoricalDataJSON(symbol, rates, copied, batch_count);
        
        if(SendHistoricalDataBatch(json_data, symbol, batch_count))
        {
            processed_bars += copied;
            batch_count++;
            
            Print("Batch ", batch_count, " sent successfully. Progress: ", processed_bars, "/", total_bars);
            
            // 進捗をログに記録
            if(batch_count % 10 == 0)
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
            current_start = rates[copied-1].time + PeriodSeconds(timeframe);
        }
        
        // サーバー負荷を考慮して少し待機
        Sleep(DELAY_MS);
    }
    
    Print("Historical data collection completed. Total processed: ", processed_bars);
    WriteLog("Historical data collection completed: " + IntegerToString(processed_bars) + " bars");
    
    is_processing = false;
    return true;
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
    
    // シンボルの小数点桁数を取得
    int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
    
    for(int i = 0; i < count; i++)
    {
        json += "    {\n";
        json += "      \"timestamp\": \"" + TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS) + "\",\n";
        json += "      \"open\": " + DoubleToString(rates[i].open, digits) + ",\n";
        json += "      \"high\": " + DoubleToString(rates[i].high, digits) + ",\n";
        json += "      \"low\": " + DoubleToString(rates[i].low, digits) + ",\n";
        json += "      \"close\": " + DoubleToString(rates[i].close, digits) + ",\n";
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
        return true;
    }
    else
    {
        Print("HTTP Error: ", res, " for batch ", batch_number);
        return false;
    }
}

//+------------------------------------------------------------------+
//| 年度データ一括取得                                              |
//+------------------------------------------------------------------+
void DownloadYearData(string symbol, int year, ENUM_TIMEFRAMES timeframe = PERIOD_H1)
{
    datetime start_date = StringToTime(IntegerToString(year) + ".01.01 00:00:00");
    datetime end_date = StringToTime(IntegerToString(year) + ".12.31 23:59:59");
    
    Print("Starting year data download: ", symbol, " for year ", year);
    WriteLog("Year data download request: " + symbol + " (" + IntegerToString(year) + ")");
    
    if(GetAndSendHistoricalData(symbol, start_date, end_date, timeframe))
    {
        Print("Year data download completed: ", symbol, " (", year, ")");
        WriteLog("Year data download completed: " + symbol + " (" + IntegerToString(year) + ")");
    }
    else
    {
        Print("Year data download failed: ", symbol, " (", year, ")");
        WriteLog("Year data download failed: " + symbol + " (" + IntegerToString(year) + ")");
    }
}

//+------------------------------------------------------------------+
//| 主要通貨ペアの過年度データ一括取得                              |
//+------------------------------------------------------------------+
void DownloadMajorPairsData(int year)
{
    string major_pairs[] = {"USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD"};
    
    Print("Starting major pairs data download for year ", year);
    
    for(int i = 0; i < ArraySize(major_pairs); i++)
    {
        string symbol = major_pairs[i];
        
        // シンボルが利用可能かチェック
        if(SymbolSelect(symbol, true))
        {
            Print("Downloading data for: ", symbol);
            DownloadYearData(symbol, year, PERIOD_H1);
            
            // 各通貨ペア間で5秒待機
            Sleep(5000);
        }
        else
        {
            Print("Symbol not available: ", symbol);
        }
    }
    
    Print("Major pairs data download completed for year ", year);
}

//+------------------------------------------------------------------+
//| ログ出力関数                                                    |
//+------------------------------------------------------------------+
void WriteLog(string message)
{
    string timestamp = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
    string log_entry = timestamp + " - " + message + "\n";
    
    int handle = FileOpen(log_file, FILE_WRITE|FILE_READ|FILE_TXT);
    if(handle != INVALID_HANDLE)
    {
        FileSeek(handle, 0, SEEK_END);
        FileWriteString(handle, log_entry);
        FileClose(handle);
    }
}

//--- グローバル変数
bool is_processing = false;