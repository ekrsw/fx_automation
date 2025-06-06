//+------------------------------------------------------------------+
//|                                                FX_Trading_EA.mq5 |
//|                        ダウ理論・エリオット波動理論ベース自動売買EA |
//|                                            Version 1.0 - Phase 1 |
//+------------------------------------------------------------------+
#property copyright "FX Trading System"
#property version   "1.00"
#property strict

//--- Include files
#include <Trade\Trade.mqh>
#include <JSON.mqh>

//--- Input parameters
input string   API_URL = "http://127.0.0.1:8000";           // FastAPI Server URL
input int      DATA_SEND_INTERVAL = 300;                     // データ送信間隔（秒）
input string   TARGET_SYMBOL = "USDJPY";                     // 対象通貨ペア
input bool     ENABLE_LOGGING = true;                        // ログ出力有効
input int      TIMEFRAME_PERIOD = PERIOD_M5;                 // タイムフレーム

//--- Global variables
CTrade         trade;
datetime       last_send_time = 0;
string         log_file = "FX_Trading_EA.log";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("=== FX Trading EA Starting ===");
    Print("API URL: ", API_URL);
    Print("Target Symbol: ", TARGET_SYMBOL);
    Print("Send Interval: ", DATA_SEND_INTERVAL, " seconds");
    
    // ログファイル初期化
    if(ENABLE_LOGGING)
    {
        WriteLog("EA Initialized - " + TimeToString(TimeCurrent()));
    }
    
    // HTTP通信テスト
    if(!TestConnection())
    {
        Print("ERROR: Failed to connect to FastAPI server");
        WriteLog("ERROR: Connection test failed");
        return INIT_FAILED;
    }
    
    Print("EA initialization completed successfully");
    WriteLog("EA initialization completed");
    
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("=== FX Trading EA Stopping ===");
    WriteLog("EA Deinitialized - Reason: " + IntegerToString(reason));
}

//+------------------------------------------------------------------+
//| Expert tick function                                            |
//+------------------------------------------------------------------+
void OnTick()
{
    // 定期的なデータ送信チェック
    if(TimeCurrent() - last_send_time >= DATA_SEND_INTERVAL)
    {
        SendMarketData();
        last_send_time = TimeCurrent();
    }
}

//+------------------------------------------------------------------+
//| Timer function (alternative to OnTick for regular intervals)    |
//+------------------------------------------------------------------+
void OnTimer()
{
    SendMarketData();
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
    
    int timeout = 5000; // 5秒タイムアウト
    int res = WebRequest("GET", url, headers, timeout, post_data, result, result_headers);
    
    if(res == 200)
    {
        string response = CharArrayToString(result);
        Print("Connection test successful. Response: ", response);
        WriteLog("Connection test successful");
        return true;
    }
    else
    {
        Print("Connection test failed. HTTP code: ", res);
        WriteLog("Connection test failed. HTTP code: " + IntegerToString(res));
        return false;
    }
}

//+------------------------------------------------------------------+
//| 市場データ送信関数                                              |
//+------------------------------------------------------------------+
void SendMarketData()
{
    // OHLC データ取得
    MqlRates rates[];
    int copied = CopyRates(TARGET_SYMBOL, TIMEFRAME_PERIOD, 0, 100, rates);
    
    if(copied <= 0)
    {
        Print("ERROR: Failed to get market data for ", TARGET_SYMBOL);
        WriteLog("ERROR: Failed to get market data");
        return;
    }
    
    // JSON データ構築
    string json_data = BuildMarketDataJSON(rates, copied);
    
    // HTTP POST送信
    if(SendHTTPRequest(json_data))
    {
        Print("Market data sent successfully. Records: ", copied);
        WriteLog("Market data sent: " + IntegerToString(copied) + " records");
    }
    else
    {
        Print("ERROR: Failed to send market data");
        WriteLog("ERROR: Failed to send market data");
    }
}

//+------------------------------------------------------------------+
//| JSON データ構築関数                                             |
//+------------------------------------------------------------------+
string BuildMarketDataJSON(MqlRates &rates[], int count)
{
    string json = "{";
    json += "\"symbol\":\"" + TARGET_SYMBOL + "\",";
    json += "\"data\":[";
    
    for(int i = 0; i < count; i++)
    {
        if(i > 0) json += ",";
        
        json += "{";
        json += "\"symbol\":\"" + TARGET_SYMBOL + "\",";
        json += "\"timestamp\":\"" + TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS) + "\",";
        json += "\"open\":" + DoubleToString(rates[i].open, 5) + ",";
        json += "\"high\":" + DoubleToString(rates[i].high, 5) + ",";
        json += "\"low\":" + DoubleToString(rates[i].low, 5) + ",";
        json += "\"close\":" + DoubleToString(rates[i].close, 5) + ",";
        json += "\"volume\":" + DoubleToString(rates[i].tick_volume, 0);
        json += "}";
    }
    
    json += "]}";
    return json;
}

//+------------------------------------------------------------------+
//| HTTP リクエスト送信関数                                         |
//+------------------------------------------------------------------+
bool SendHTTPRequest(string json_data)
{
    string url = API_URL + "/api/v1/market-data";
    string headers = "Content-Type: application/json\r\n";
    
    char post_data[];
    StringToCharArray(json_data, post_data, 0, StringLen(json_data));
    
    char result[];
    string result_headers;
    
    int timeout = 10000; // 10秒タイムアウト
    int res = WebRequest("POST", url, headers, timeout, post_data, result, result_headers);
    
    if(res == 200)
    {
        string response = CharArrayToString(result);
        Print("HTTP Response: ", response);
        return true;
    }
    else
    {
        Print("HTTP Error: ", res);
        Print("Headers: ", result_headers);
        return false;
    }
}

//+------------------------------------------------------------------+
//| ログ出力関数                                                    |
//+------------------------------------------------------------------+
void WriteLog(string message)
{
    if(!ENABLE_LOGGING) return;
    
    int file_handle = FileOpen(log_file, FILE_WRITE | FILE_TXT | FILE_COMMON);
    if(file_handle == INVALID_HANDLE)
    {
        Print("ERROR: Cannot create log file");
        return;
    }
    
    string log_entry = TimeToString(TimeCurrent()) + " - " + message + "\n";
    FileWrite(file_handle, log_entry);
    FileClose(file_handle);
}

//+------------------------------------------------------------------+
//| 現在価格情報取得関数                                            |
//+------------------------------------------------------------------+
string GetCurrentPriceInfo()
{
    double bid = SymbolInfoDouble(TARGET_SYMBOL, SYMBOL_BID);
    double ask = SymbolInfoDouble(TARGET_SYMBOL, SYMBOL_ASK);
    double spread = ask - bid;
    
    string info = "Symbol: " + TARGET_SYMBOL;
    info += ", Bid: " + DoubleToString(bid, 5);
    info += ", Ask: " + DoubleToString(ask, 5);
    info += ", Spread: " + DoubleToString(spread * MathPow(10, 5), 1) + " pips";
    
    return info;
}

//+------------------------------------------------------------------+
//| エラーハンドリング関数                                          |
//+------------------------------------------------------------------+
void HandleError(int error_code, string function_name)
{
    string error_msg = "Error in " + function_name + ": " + IntegerToString(error_code);
    Print(error_msg);
    WriteLog("ERROR: " + error_msg);
}

//+------------------------------------------------------------------+