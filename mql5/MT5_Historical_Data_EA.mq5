//+------------------------------------------------------------------+
//|                                    MT5_Historical_Data_EA.mq5 |
//|                               MT5履歴データ取得専用EA |
//|                                            Version 1.0 |
//+------------------------------------------------------------------+
#property copyright "FX Trading System"
#property version   "1.00"
#property strict

//--- Include files
#include <Trade\Trade.mqh>
#include <Arrays\ArrayObj.mqh>

//--- Input parameters
input string   API_URL = "http://127.0.0.1:8000";           // FastAPI Server URL
input bool     ENABLE_LOGGING = true;                        // ログ出力有効
input int      BATCH_SIZE = 1000;                           // 一度に送信するバー数
input int      DELAY_MS = 100;                              // 送信間隔（ミリ秒）

//--- Global variables
string         log_file = "MT5_Historical_Data.log";
bool           is_processing = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("=== MT5 Historical Data EA Starting ===");
    Print("API URL: ", API_URL);
    Print("Batch Size: ", BATCH_SIZE);
    
    // ログファイル初期化
    if(ENABLE_LOGGING)
    {
        WriteLog("Historical Data EA Initialized - " + TimeToString(TimeCurrent()));
    }
    
    // HTTP通信テスト
    if(!TestConnection())
    {
        Print("ERROR: Failed to connect to FastAPI server");
        WriteLog("ERROR: Connection test failed");
        return INIT_FAILED;
    }
    
    Print("Historical Data EA initialization completed");
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("=== MT5 Historical Data EA Stopping ===");
    WriteLog("Historical Data EA Deinitialized - Reason: " + IntegerToString(reason));
}

//+------------------------------------------------------------------+
//| Expert tick function                                            |
//+------------------------------------------------------------------+
void OnTick()
{
    // このEAはHTTPリクエストベースで動作するため、OnTickでは何もしない
}

//+------------------------------------------------------------------+
//| HTTP接続テスト関数                                              |
//+------------------------------------------------------------------+
bool TestConnection()
{
    string url = API_URL + "/status";
    string headers = "Content-Type: application/json\r\n";
    
    char post_data[];
    char result[];
    string result_headers;
    
    Print("Testing connection to: ", url);
    
    int timeout = 5000;
    int res = WebRequest("GET", url, headers, timeout, post_data, result, result_headers);
    
    if(res == 200)
    {
        Print("Connection test successful");
        return true;
    }
    else
    {
        Print("Connection test failed. HTTP code: ", res);
        return false;
    }
}

//+------------------------------------------------------------------+
//| 履歴データ取得・送信関数（メイン処理）                          |
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
    
    while(processed_bars < total_bars)
    {
        int bars_to_get = MathMin(BATCH_SIZE, total_bars - processed_bars);
        
        // 履歴データを取得
        MqlRates rates[];
        int copied = CopyRates(symbol, timeframe, start_date, bars_to_get, rates);
        
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
            start_date = rates[copied-1].time + PeriodSeconds(timeframe);
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
//| 履歴データJSON構築関数                                          |
//+------------------------------------------------------------------+
string BuildHistoricalDataJSON(string symbol, MqlRates &rates[], int count, int batch_number)
{
    string json = "{\n";
    json += "  \"symbol\": \"" + symbol + "\",\n";
    json += "  \"batch_number\": " + IntegerToString(batch_number) + ",\n";
    json += "  \"total_records\": " + IntegerToString(count) + ",\n";
    json += "  \"data\": [\n";
    
    for(int i = 0; i < count; i++)
    {
        string timestamp = TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS);
        // MT5の時刻形式をISO形式に変換
        timestamp = StringReplace(timestamp, ".", "-");
        timestamp = StringReplace(timestamp, " ", "T");
        
        json += "    {\n";
        json += "      \"timestamp\": \"" + timestamp + "\",\n";
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
//| 履歴データバッチ送信関数                                        |
//+------------------------------------------------------------------+
bool SendHistoricalDataBatch(string json_data, string symbol, int batch_number)
{
    string url = API_URL + "/api/v1/mt5/receive-historical-batch";
    string headers = "Content-Type: application/json\r\n";
    
    char post_data[];
    StringToCharArray(json_data, post_data, 0, StringLen(json_data));
    
    char result[];
    string result_headers;
    
    int timeout = 30000; // 30秒タイムアウト
    int res = WebRequest("POST", url, headers, timeout, post_data, result, result_headers);
    
    if(res == 200)
    {
        return true;
    }
    else
    {
        Print("HTTP Error: ", res, " for batch ", batch_number);
        if(res == -1)
        {
            Print("WebRequest error. Check if URL is in allowed list: Tools -> Options -> Expert Advisors -> Allow WebRequest for listed URL");
        }
        return false;
    }
}

//+------------------------------------------------------------------+
//| 利用可能なシンボル一覧取得                                      |
//+------------------------------------------------------------------+
void GetAvailableSymbols()
{
    Print("=== Available Symbols ===");
    
    int total = SymbolsTotal(true);
    string symbols[];
    ArrayResize(symbols, total);
    
    for(int i = 0; i < total; i++)
    {
        string symbol_name = SymbolName(i, true);
        symbols[i] = symbol_name;
        
        // 主要通貨ペアの詳細情報を表示
        if(StringFind(symbol_name, "USD") >= 0 || StringFind(symbol_name, "EUR") >= 0 || 
           StringFind(symbol_name, "GBP") >= 0 || StringFind(symbol_name, "JPY") >= 0)
        {
            double point = SymbolInfoDouble(symbol_name, SYMBOL_POINT);
            int digits = (int)SymbolInfoInteger(symbol_name, SYMBOL_DIGITS);
            
            Print(symbol_name, " - Digits: ", digits, ", Point: ", point);
        }
    }
    
    // シンボル一覧をサーバーに送信
    SendSymbolsList(symbols, total);
    
    Print("Total symbols available: ", total);
}

//+------------------------------------------------------------------+
//| シンボル一覧送信関数                                            |
//+------------------------------------------------------------------+
bool SendSymbolsList(string &symbols[], int count)
{
    string json = "{\n";
    json += "  \"symbols\": [\n";
    
    for(int i = 0; i < count; i++)
    {
        json += "    \"" + symbols[i] + "\"";
        if(i < count - 1) json += ",";
        json += "\n";
    }
    
    json += "  ],\n";
    json += "  \"total_count\": " + IntegerToString(count) + ",\n";
    json += "  \"timestamp\": \"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + "\"\n";
    json += "}";
    
    string url = API_URL + "/api/v1/mt5/receive-symbols";
    string headers = "Content-Type: application/json\r\n";
    
    char post_data[];
    StringToCharArray(json, post_data, 0, StringLen(json));
    
    char result[];
    string result_headers;
    
    int res = WebRequest("POST", url, headers, 5000, post_data, result, result_headers);
    
    return (res == 200);
}

//+------------------------------------------------------------------+
//| ターミナル情報取得・送信                                        |
//+------------------------------------------------------------------+
void SendTerminalInfo()
{
    string json = "{\n";
    json += "  \"terminal_info\": {\n";
    json += "    \"name\": \"" + TerminalInfoString(TERMINAL_NAME) + "\",\n";
    json += "    \"company\": \"" + TerminalInfoString(TERMINAL_COMPANY) + "\",\n";
    json += "    \"language\": \"" + TerminalInfoString(TERMINAL_LANGUAGE) + "\",\n";
    json += "    \"data_path\": \"" + TerminalInfoString(TERMINAL_DATA_PATH) + "\",\n";
    json += "    \"commondata_path\": \"" + TerminalInfoString(TERMINAL_COMMONDATA_PATH) + "\",\n";
    json += "    \"build\": " + IntegerToString(TerminalInfoInteger(TERMINAL_BUILD)) + ",\n";
    json += "    \"connected\": " + (TerminalInfoInteger(TERMINAL_CONNECTED) ? "true" : "false") + ",\n";
    json += "    \"max_bars\": " + IntegerToString(TerminalInfoInteger(TERMINAL_MAXBARS)) + "\n";
    json += "  },\n";
    json += "  \"account_info\": {\n";
    json += "    \"login\": " + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ",\n";
    json += "    \"server\": \"" + AccountInfoString(ACCOUNT_SERVER) + "\",\n";
    json += "    \"name\": \"" + AccountInfoString(ACCOUNT_NAME) + "\",\n";
    json += "    \"company\": \"" + AccountInfoString(ACCOUNT_COMPANY) + "\",\n";
    json += "    \"currency\": \"" + AccountInfoString(ACCOUNT_CURRENCY) + "\",\n";
    json += "    \"balance\": " + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",\n";
    json += "    \"equity\": " + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + "\n";
    json += "  }\n";
    json += "}";
    
    string url = API_URL + "/api/v1/mt5/receive-terminal-info";
    string headers = "Content-Type: application/json\r\n";
    
    char post_data[];
    StringToCharArray(json, post_data, 0, StringLen(json));
    
    char result[];
    string result_headers;
    
    WebRequest("POST", url, headers, 5000, post_data, result, result_headers);
}

//+------------------------------------------------------------------+
//| ログ出力関数                                                    |
//+------------------------------------------------------------------+
void WriteLog(string message)
{
    if(!ENABLE_LOGGING) return;
    
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

//+------------------------------------------------------------------+
//| カスタム関数：年度データ一括取得                                |
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
//| カスタム関数：主要通貨ペアの過年度データ一括取得                |
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