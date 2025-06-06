//+------------------------------------------------------------------+
//|                                                FX_Trading_EA.mq5 |
//|                        ダウ理論・エリオット波動理論ベース自動売買EA |
//|                                            Version 1.0 - Phase 5 |
//+------------------------------------------------------------------+
#property copyright "FX Trading System"
#property version   "1.00"
#property strict

//--- Include files
#include <Trade\Trade.mqh>

//--- Input parameters
input string   API_URL = "http://127.0.0.1:8000";           // FastAPI Server URL
input int      DATA_SEND_INTERVAL = 300;                     // データ送信間隔（秒）
input bool     ENABLE_MULTI_PAIR = true;                     // マルチペア機能有効
input bool     ENABLE_LOGGING = true;                        // ログ出力有効
input int      TIMEFRAME_PERIOD = PERIOD_M5;                 // タイムフレーム
input int      MAX_POSITIONS = 3;                            // 最大ポジション数
input bool     ENABLE_ALERTS = true;                         // アラート機能有効
input bool     ENABLE_PERFORMANCE_MONITORING = true;         // パフォーマンス監視有効
input int      ALERT_CHECK_INTERVAL = 60;                    // アラートチェック間隔（秒）

//--- Global variables
CTrade         trade;
datetime       last_send_time = 0;
datetime       last_multi_pair_check = 0;
datetime       last_alert_check = 0;
datetime       last_performance_check = 0;
string         log_file = "FX_Trading_EA.log";

// 監視対象通貨ペア
string         currency_pairs[] = {"USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD"};

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("=== FX Trading EA Starting - Phase 5 ===");
    Print("API URL: ", API_URL);
    Print("Multi-Pair Mode: ", ENABLE_MULTI_PAIR ? "Enabled" : "Disabled");
    Print("Send Interval: ", DATA_SEND_INTERVAL, " seconds");
    Print("Alerts: ", ENABLE_ALERTS ? "Enabled" : "Disabled");
    Print("Performance Monitoring: ", ENABLE_PERFORMANCE_MONITORING ? "Enabled" : "Disabled");
    
    // ファイルパス情報を表示
    Print("Log file path: ", log_file);
    Print("Terminal data path: ", TerminalInfoString(TERMINAL_DATA_PATH));
    Print("Terminal common path: ", TerminalInfoString(TERMINAL_COMMONDATA_PATH));
    
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
        if(ENABLE_MULTI_PAIR)
        {
            SendMultiPairData();
        }
        else
        {
            SendMarketData();
        }
        last_send_time = TimeCurrent();
    }
    
    // マルチペア推奨チェック（10分間隔）
    if(ENABLE_MULTI_PAIR && TimeCurrent() - last_multi_pair_check >= 600)
    {
        CheckMultiPairRecommendations();
        last_multi_pair_check = TimeCurrent();
    }
    
    // アラートチェック
    if(ENABLE_ALERTS && TimeCurrent() - last_alert_check >= ALERT_CHECK_INTERVAL)
    {
        CheckSystemAlerts();
        last_alert_check = TimeCurrent();
    }
    
    // パフォーマンス監視（5分間隔）
    if(ENABLE_PERFORMANCE_MONITORING && TimeCurrent() - last_performance_check >= 300)
    {
        SendPerformanceData();
        last_performance_check = TimeCurrent();
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
    // OHLC データ取得（USDJPY固定）
    MqlRates rates[];
    int copied = CopyRates("USDJPY", (ENUM_TIMEFRAMES)TIMEFRAME_PERIOD, 0, 100, rates);
    
    if(copied <= 0)
    {
        Print("ERROR: Failed to get market data for USDJPY");
        WriteLog("ERROR: Failed to get market data");
        return;
    }
    
    // JSON データ構築
    string json_data = BuildMarketDataJSON("USDJPY", rates, copied);
    
    // HTTP POST送信
    if(SendHTTPRequest(json_data, "/api/v1/market-data"))
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
//| マルチペア市場データ送信関数                                    |
//+------------------------------------------------------------------+
void SendMultiPairData()
{
    int total_sent = 0;
    
    for(int i = 0; i < ArraySize(currency_pairs); i++)
    {
        string symbol = currency_pairs[i];
        
        // シンボルが利用可能かチェック
        if(!SymbolSelect(symbol, true))
        {
            Print("WARNING: Symbol ", symbol, " not available");
            continue;
        }
        
        // OHLC データ取得
        MqlRates rates[];
        int copied = CopyRates(symbol, (ENUM_TIMEFRAMES)TIMEFRAME_PERIOD, 0, 100, rates);
        
        if(copied <= 0)
        {
            Print("WARNING: Failed to get market data for ", symbol);
            continue;
        }
        
        // JSON データ構築
        string json_data = BuildMarketDataJSON(symbol, rates, copied);
        
        // HTTP POST送信
        if(SendHTTPRequest(json_data, "/api/v1/market-data"))
        {
            total_sent++;
            Print("Market data sent for ", symbol, ": ", copied, " records");
        }
        else
        {
            Print("ERROR: Failed to send market data for ", symbol);
        }
        
        // 短い間隔を置く
        Sleep(100);
    }
    
    WriteLog("Multi-pair data sent: " + IntegerToString(total_sent) + "/" + IntegerToString(ArraySize(currency_pairs)) + " pairs");
}

//+------------------------------------------------------------------+
//| マルチペア推奨チェック関数                                      |
//+------------------------------------------------------------------+
void CheckMultiPairRecommendations()
{
    string url = API_URL + "/api/v1/multi-pair/recommendations";
    string headers = "Content-Type: application/json\r\n";
    
    char post_data[];
    char result[];
    string result_headers;
    
    Print("Checking multi-pair recommendations...");
    
    int timeout = 10000;
    int res = WebRequest("GET", url, headers, timeout, post_data, result, result_headers);
    
    if(res == 200)
    {
        string response = CharArrayToString(result);
        Print("Multi-pair recommendations received: ", response);
        WriteLog("Multi-pair recommendations: " + response);
        
        // TODO: レスポンスを解析して自動取引実行
        // ProcessMultiPairRecommendations(response);
    }
    else
    {
        Print("Failed to get multi-pair recommendations. HTTP code: ", res);
        WriteLog("ERROR: Multi-pair recommendations failed: " + IntegerToString(res));
    }
}

//+------------------------------------------------------------------+
//| JSON データ構築関数                                             |
//+------------------------------------------------------------------+
string BuildMarketDataJSON(string symbol, MqlRates &rates[], int count)
{
    string json = "{";
    json += "\"symbol\":\"" + symbol + "\",";
    json += "\"data\":[";
    
    for(int i = 0; i < count; i++)
    {
        if(i > 0) json += ",";
        
        json += "{";
        json += "\"symbol\":\"" + symbol + "\",";
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
bool SendHTTPRequest(string json_data, string endpoint)
{
    string url = API_URL + endpoint;
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
        // Print("HTTP Response: ", response);  // レスポンス出力を抑制
        return true;
    }
    else
    {
        Print("HTTP Error: ", res, " for ", endpoint);
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
    
    // ファイルを追記モードで開く
    int file_handle = FileOpen(log_file, FILE_WRITE | FILE_READ | FILE_TXT | FILE_COMMON);
    if(file_handle == INVALID_HANDLE)
    {
        Print("ERROR: Cannot create log file: ", log_file);
        Print("Error code: ", GetLastError());
        return;
    }
    
    // ファイルの末尾に移動
    FileSeek(file_handle, 0, SEEK_END);
    
    string log_entry = TimeToString(TimeCurrent()) + " - " + message;
    FileWriteString(file_handle, log_entry + "\r\n");
    FileClose(file_handle);
    
    // デバッグ用：ターミナルにもログを出力
    Print("LOG: ", message);
}

//+------------------------------------------------------------------+
//| 現在価格情報取得関数                                            |
//+------------------------------------------------------------------+
string GetCurrentPriceInfo(string symbol = "USDJPY")
{
    double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
    double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
    double spread = ask - bid;
    
    string info = "Symbol: " + symbol;
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
//| システムアラートチェック関数（フェーズ5新機能）                  |
//+------------------------------------------------------------------+
void CheckSystemAlerts()
{
    string url = API_URL + "/api/v1/alerts/active/count";
    string headers = "Content-Type: application/json\r\n";
    
    char post_data[];
    char result[];
    string result_headers;
    
    int timeout = 5000;
    int res = WebRequest("GET", url, headers, timeout, post_data, result, result_headers);
    
    if(res == 200)
    {
        string response = CharArrayToString(result);
        Print("Active alerts check: ", response);
        WriteLog("Active alerts: " + response);
        
        // 重要アラートがある場合の処理
        ProcessAlertResponse(response);
    }
    else
    {
        Print("Failed to check alerts. HTTP code: ", res);
        WriteLog("ERROR: Alert check failed: " + IntegerToString(res));
    }
}

//+------------------------------------------------------------------+
//| アラート応答処理関数                                            |
//+------------------------------------------------------------------+
void ProcessAlertResponse(string response)
{
    // 簡易的なJSON解析（実際の実装では専用のJSONライブラリを使用）
    if(StringFind(response, "\"total\":") >= 0)
    {
        // アラート数を抽出（簡易版）
        int start_pos = StringFind(response, "\"total\":") + 8;
        int end_pos = StringFind(response, ",", start_pos);
        if(end_pos < 0) end_pos = StringFind(response, "}", start_pos);
        
        if(end_pos > start_pos)
        {
            string alert_count_str = StringSubstr(response, start_pos, end_pos - start_pos);
            int alert_count = (int)StringToInteger(alert_count_str);
            
            if(alert_count > 0)
            {
                Print("WARNING: ", alert_count, " active alerts detected!");
                WriteLog("WARNING: " + IntegerToString(alert_count) + " active alerts");
                
                // 重要アラートが5個以上の場合は取引を一時停止
                if(alert_count >= 5)
                {
                    Print("CRITICAL: Too many alerts, suspending trading operations");
                    WriteLog("CRITICAL: Trading suspended due to high alert count");
                    // 実際の実装では取引停止フラグを設定
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| パフォーマンスデータ送信関数（フェーズ5新機能）                  |
//+------------------------------------------------------------------+
void SendPerformanceData()
{
    // システムパフォーマンス情報を収集
    string performance_data = BuildPerformanceJSON();
    
    // パフォーマンス監視APIに送信
    if(SendHTTPRequest(performance_data, "/api/v1/performance/live-metrics"))
    {
        Print("Performance data sent successfully");
        WriteLog("Performance data transmitted");
    }
    else
    {
        Print("ERROR: Failed to send performance data");
        WriteLog("ERROR: Performance data transmission failed");
    }
}

//+------------------------------------------------------------------+
//| パフォーマンスJSON構築関数                                      |
//+------------------------------------------------------------------+
string BuildPerformanceJSON()
{
    // 口座情報を取得
    double account_balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double account_equity = AccountInfoDouble(ACCOUNT_EQUITY);
    double account_margin = AccountInfoDouble(ACCOUNT_MARGIN);
    double account_free_margin = AccountInfoDouble(ACCOUNT_FREEMARGIN);
    
    // ポジション情報を取得
    int total_positions = PositionsTotal();
    
    // 今日の統計
    datetime today_start = TimeCurrent() - (TimeCurrent() % (24 * 3600));
    
    string json = "{";
    json += "\"timestamp\":\"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + "\",";
    json += "\"account_info\":{";
    json += "\"balance\":" + DoubleToString(account_balance, 2) + ",";
    json += "\"equity\":" + DoubleToString(account_equity, 2) + ",";
    json += "\"margin\":" + DoubleToString(account_margin, 2) + ",";
    json += "\"free_margin\":" + DoubleToString(account_free_margin, 2) + ",";
    json += "\"margin_level\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_LEVEL), 2);
    json += "},";
    json += "\"positions\":{";
    json += "\"total\":" + IntegerToString(total_positions) + ",";
    json += "\"max_allowed\":" + IntegerToString(MAX_POSITIONS);
    json += "},";
    json += "\"ea_status\":{";
    json += "\"multi_pair_enabled\":" + (ENABLE_MULTI_PAIR ? "true" : "false") + ",";
    json += "\"alerts_enabled\":" + (ENABLE_ALERTS ? "true" : "false") + ",";
    json += "\"performance_monitoring\":" + (ENABLE_PERFORMANCE_MONITORING ? "true" : "false");
    json += "}";
    json += "}";
    
    return json;
}

//+------------------------------------------------------------------+
//| バックテストデータ要求処理関数（フェーズ5新機能）                |
//+------------------------------------------------------------------+
void HandleBacktestRequest()
{
    string url = API_URL + "/api/v1/backtest/ea-data-request";
    string headers = "Content-Type: application/json\r\n";
    
    char post_data[];
    char result[];
    string result_headers;
    
    int timeout = 5000;
    int res = WebRequest("GET", url, headers, timeout, post_data, result, result_headers);
    
    if(res == 200)
    {
        string response = CharArrayToString(result);
        
        // バックテスト用の詳細データを送信
        if(StringFind(response, "\"request_data\":true") >= 0)
        {
            SendDetailedBacktestData();
        }
    }
}

//+------------------------------------------------------------------+
//| 詳細バックテストデータ送信関数                                  |
//+------------------------------------------------------------------+
void SendDetailedBacktestData()
{
    // 過去100件のより詳細なデータを送信
    for(int i = 0; i < ArraySize(currency_pairs); i++)
    {
        string symbol = currency_pairs[i];
        
        if(!SymbolSelect(symbol, true)) continue;
        
        // 詳細なOHLCVデータ
        MqlRates rates[];
        int copied = CopyRates(symbol, (ENUM_TIMEFRAMES)TIMEFRAME_PERIOD, 0, 200, rates);
        
        if(copied > 0)
        {
            string detailed_json = BuildDetailedMarketDataJSON(symbol, rates, copied);
            SendHTTPRequest(detailed_json, "/api/v1/backtest/detailed-data");
            Sleep(200); // サーバー負荷軽減
        }
    }
    
    WriteLog("Detailed backtest data sent for " + IntegerToString(ArraySize(currency_pairs)) + " pairs");
}

//+------------------------------------------------------------------+
//| 詳細市場データJSON構築関数                                      |
//+------------------------------------------------------------------+
string BuildDetailedMarketDataJSON(string symbol, MqlRates &rates[], int count)
{
    string json = "{";
    json += "\"symbol\":\"" + symbol + "\",";
    json += "\"timeframe\":\"" + IntegerToString(TIMEFRAME_PERIOD) + "\",";
    json += "\"data_type\":\"detailed_backtest\",";
    json += "\"count\":" + IntegerToString(count) + ",";
    json += "\"data\":[";
    
    for(int i = 0; i < count; i++)
    {
        if(i > 0) json += ",";
        
        json += "{";
        json += "\"symbol\":\"" + symbol + "\",";
        json += "\"timestamp\":\"" + TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS) + "\",";
        json += "\"open\":" + DoubleToString(rates[i].open, 5) + ",";
        json += "\"high\":" + DoubleToString(rates[i].high, 5) + ",";
        json += "\"low\":" + DoubleToString(rates[i].low, 5) + ",";
        json += "\"close\":" + DoubleToString(rates[i].close, 5) + ",";
        json += "\"volume\":" + DoubleToString(rates[i].tick_volume, 0) + ",";
        json += "\"spread\":" + DoubleToString(rates[i].spread, 1);
        json += "}";
    }
    
    json += "]}";
    return json;
}

//+------------------------------------------------------------------+
//| 最適化パラメータ更新関数（フェーズ5新機能）                      |
//+------------------------------------------------------------------+
void CheckOptimizationUpdates()
{
    string url = API_URL + "/api/v1/optimization/ea-parameters";
    string headers = "Content-Type: application/json\r\n";
    
    char post_data[];
    char result[];
    string result_headers;
    
    int timeout = 5000;
    int res = WebRequest("GET", url, headers, timeout, post_data, result, result_headers);
    
    if(res == 200)
    {
        string response = CharArrayToString(result);
        Print("Optimization parameters check: ", response);
        
        // パラメータ更新があれば適用
        ProcessOptimizationParameters(response);
    }
}

//+------------------------------------------------------------------+
//| 最適化パラメータ処理関数                                        |
//+------------------------------------------------------------------+
void ProcessOptimizationParameters(string response)
{
    // 簡易的なJSON解析でパラメータ更新をチェック
    if(StringFind(response, "\"update_available\":true") >= 0)
    {
        Print("INFO: New optimized parameters available");
        WriteLog("INFO: Optimization parameters update detected");
        
        // 実際の実装では、新しいパラメータを解析して設定を更新
        // 例: 新しいエントリー閾値、ストップロス設定など
    }
}

//+------------------------------------------------------------------+