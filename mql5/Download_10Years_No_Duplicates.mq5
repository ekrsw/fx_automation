//+------------------------------------------------------------------+
//|                                 Download_10Years_No_Duplicates.mq5|
//|                                         FX Automation System      |
//|                                                                  |
//+------------------------------------------------------------------+
#property copyright "FX Automation System"
#property link      ""
#property version   "1.00"

#include <Trade\Trade.mqh>

// サーバーのURL
input string ServerURL = "http://127.0.0.1:8000/api/v1/mt5/receive-historical-batch";
input string Symbol = "USDJPY";
input int YearsToDownload = 1;  // テスト用に1年に変更
input int BatchSize = 10;  // 一度に送信するデータ数（デバッグ用に非常に小さく）
input int MaxRetries = 3;    // 送信失敗時のリトライ回数

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("=== 10年分履歴データダウンロード開始 (重複チェック付き) ===");
    
    // 現在時刻と10年前の時刻を計算
    datetime endTime = TimeCurrent();
    datetime startTime = endTime - (365 * 24 * 60 * 60 * YearsToDownload); // 10年前
    
    Print("データ取得期間: ", TimeToString(startTime), " から ", TimeToString(endTime));
    
    // 年ごとにデータを取得して処理
    for(int year = 0; year < YearsToDownload; year++)
    {
        datetime yearStart = endTime - ((year + 1) * 365 * 24 * 60 * 60);
        datetime yearEnd = endTime - (year * 365 * 24 * 60 * 60);
        
        MqlDateTime yearStartStruct;
        TimeToStruct(yearStart, yearStartStruct);
        Print("処理中: ", yearStartStruct.year, "年");
        
        if(!DownloadYearData(yearStart, yearEnd))
        {
            MqlDateTime yearStartErrorStruct;
            TimeToStruct(yearStart, yearStartErrorStruct);
            Print("エラー: ", yearStartErrorStruct.year, "年のデータ取得に失敗しました");
        }
        
        // サーバー負荷軽減のため少し待機
        Sleep(2000);
    }
    
    Print("=== 10年分履歴データダウンロード完了 ===");
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| 年間データのダウンロード                                         |
//+------------------------------------------------------------------+
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
    
    Print("コピーされたデータ数: ", copied, " 件");
    
    // バッチ処理でデータを送信
    int totalSent = 0;
    int batches = (copied + BatchSize - 1) / BatchSize; // 切り上げ除算
    
    for(int batch = 0; batch < batches; batch++)
    {
        int start = batch * BatchSize;
        int end = MathMin(start + BatchSize, copied);
        int batchDataCount = end - start;
        
        string jsonData = PrepareJSONBatch(rates, start, end);
        
        // デバッグ: 最初のバッチのJSONを出力
        if(batch == 0) {
            Print("JSON Sample (first 200 chars): ", StringSubstr(jsonData, 0, 200));
        }
        
        bool sent = false;
        for(int retry = 0; retry < MaxRetries && !sent; retry++)
        {
            if(retry > 0)
            {
                Print("リトライ ", retry, " / ", MaxRetries);
                Sleep(1000 * retry); // リトライ間隔を徐々に延長
            }
            
            sent = SendDataToServer(jsonData, batchDataCount);
        }
        
        if(sent)
        {
            totalSent += batchDataCount;
            Print("バッチ ", batch + 1, "/", batches, " 送信成功 (", batchDataCount, " 件)");
        }
        else
        {
            Print("バッチ ", batch + 1, "/", batches, " 送信失敗");
        }
        
        // サーバー負荷軽減のため待機
        Sleep(500);
    }
    
    Print("年間データ送信完了: ", totalSent, " / ", copied, " 件");
    return (totalSent > 0);
}

//+------------------------------------------------------------------+
//| JSONデータの準備（バッチ処理用）                                 |
//+------------------------------------------------------------------+
string PrepareJSONBatch(MqlRates &rates[], int start, int end)
{
    string json = "{";
    json += "\"symbol\":\"" + Symbol + "\",";
    json += "\"timeframe\":\"H1\",";
    json += "\"batch_number\":" + IntegerToString(start/BatchSize) + ",";  // バッチ番号追加
    json += "\"data\":[";
    
    for(int i = start; i < end; i++)
    {
        if(i > start) json += ",";
        
        json += "{";
        // TimeToStringの結果を一度変数に格納して確認
        string timestamp = TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS);
        StringReplace(timestamp, " ", " ");  // 余分な空白を削除
        
        json += "\"timestamp\":\"" + timestamp + "\",";
        // DoubleToStringの代わりにStringFormatを使用
        json += "\"open\":" + StringFormat("%.5f", rates[i].open) + ",";
        json += "\"high\":" + StringFormat("%.5f", rates[i].high) + ",";
        json += "\"low\":" + StringFormat("%.5f", rates[i].low) + ",";
        json += "\"close\":" + StringFormat("%.5f", rates[i].close) + ",";
        json += "\"volume\":" + IntegerToString(rates[i].tick_volume);
        json += "}";
    }
    
    json += "],";
    json += "\"check_duplicates\":true"; // 重複チェックフラグ
    json += "}";
    
    return json;
}

//+------------------------------------------------------------------+
//| HTTPでデータをサーバーに送信                                     |
//+------------------------------------------------------------------+
bool SendDataToServer(string jsonData, int dataCount)
{
    char post[];
    char result[];
    string headers;
    
    // デバッグ: JSONの長さと最初と最後の部分を出力
    Print("JSON Length: ", StringLen(jsonData));
    Print("JSON Start: ", StringSubstr(jsonData, 0, 100));
    Print("JSON End: ", StringSubstr(jsonData, StringLen(jsonData) - 100, 100));
    
    // JSONデータをchar配列に変換
    int jsonLength = StringLen(jsonData);
    StringToCharArray(jsonData, post, 0, -1, CP_UTF8);
    
    // null終端文字が含まれている場合のみ削除
    if(ArraySize(post) > jsonLength) {
        ArrayResize(post, jsonLength);
    }
    
    // HTTPヘッダー設定
    headers = "Content-Type: application/json\r\n";
    
    // タイムアウトを長めに設定（大量データ処理のため）
    int timeout = 30000; // 30秒
    
    // HTTPリクエスト送信
    int res = WebRequest("POST", ServerURL, headers, timeout, post, result, headers);
    
    if(res == 200)
    {
        string response = CharArrayToString(result);
        
        // レスポンスから処理結果を解析
        if(StringFind(response, "\"success\":true") >= 0)
        {
            // 保存件数と重複件数を抽出（簡易的な解析）
            int savedPos = StringFind(response, "\"saved\":");
            int dupPos = StringFind(response, "\"duplicates\":");
            
            if(savedPos >= 0 && dupPos >= 0)
            {
                string savedStr = StringSubstr(response, savedPos + 8, 10);
                string dupStr = StringSubstr(response, dupPos + 13, 10);
                
                int saved = 0;
                int duplicates = 0;
                
                // 数値部分を抽出
                for(int i = 0; i < StringLen(savedStr); i++)
                {
                    if(savedStr[i] >= '0' && savedStr[i] <= '9')
                    {
                        saved = saved * 10 + (savedStr[i] - '0');
                    }
                    else if(savedStr[i] == ',' || savedStr[i] == '}')
                    {
                        break;
                    }
                }
                
                for(int i = 0; i < StringLen(dupStr); i++)
                {
                    if(dupStr[i] >= '0' && dupStr[i] <= '9')
                    {
                        duplicates = duplicates * 10 + (dupStr[i] - '0');
                    }
                    else if(dupStr[i] == ',' || dupStr[i] == '}')
                    {
                        break;
                    }
                }
                
                Print("保存: ", saved, " 件, 重複: ", duplicates, " 件");
            }
            
            return true;
        }
        else
        {
            Print("サーバーエラー: ", response);
            return false;
        }
    }
    else if(res == -1)
    {
        int error = GetLastError();
        Print("WebRequestエラー: ", error);
        
        if(error == 4014)
        {
            Print("WebRequestが許可されていません。");
            Print("ツール -> オプション -> エキスパートアドバイザー で以下を確認してください:");
            Print("1. 'WebRequestを許可するURLリスト' にチェック");
            Print("2. URLリストに '", ServerURL, "' を追加");
        }
        
        return false;
    }
    else
    {
        Print("HTTPエラー: ", res);
        if(ArraySize(result) > 0)
        {
            Print("レスポンス: ", CharArrayToString(result));
        }
        return false;
    }
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("Download_10Years_No_Duplicates EA 終了");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    // OnInitで処理が完了するため、ここでは何もしない
}
//+------------------------------------------------------------------+