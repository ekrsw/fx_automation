//+------------------------------------------------------------------+
//|                                          Test_Single_Data.mq5    |
//|                                    FX Automation System Test     |
//+------------------------------------------------------------------+
#property copyright "FX Automation System"
#property link      ""
#property version   "1.00"

input string ServerURL = "http://127.0.0.1:8000/api/v1/mt5/receive-historical-batch";

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{
    Print("=== テスト: 単一データ送信 ===");
    
    // テスト用JSONデータ（1件のみ）
    string json = "{";
    json += "\"symbol\":\"USDJPY\",";
    json += "\"timeframe\":\"H1\",";
    json += "\"batch_number\":0,";
    json += "\"check_duplicates\":true,";
    json += "\"data\":[";
    json += "{";
    json += "\"timestamp\":\"2024-01-01 00:00:00\",";
    json += "\"open\":140.5,";
    json += "\"high\":140.6,";
    json += "\"low\":140.4,";
    json += "\"close\":140.55,";
    json += "\"volume\":100";
    json += "}";
    json += "]";
    json += "}";
    
    Print("JSON to send:");
    Print(json);
    Print("JSON length: ", StringLen(json));
    
    // JSONの最後の10文字を出力（デバッグ用）
    int len = StringLen(json);
    Print("Last 10 chars:");
    for(int i = len - 10; i < len; i++) {
        ushort charCode = StringGetCharacter(json, i);
        Print("Char[", i, "] = '", StringSubstr(json, i, 1), "' (code: ", charCode, ")");
    }
    
    // ファイルに保存してデバッグ
    int handle = FileOpen("test_json.txt", FILE_WRITE|FILE_TXT|FILE_ANSI);
    if(handle != INVALID_HANDLE) {
        FileWriteString(handle, json);
        FileClose(handle);
        Print("JSON saved to file: test_json.txt");
    }
    
    // 送信
    char post[];
    char result[];
    string headers = "Content-Type: application/json\r\n";
    
    // StringToCharArrayでUTF-8エンコーディングを使用
    int jsonLen = StringLen(json);
    StringToCharArray(json, post, 0, -1, CP_UTF8);
    
    // デバッグ: 変換後のサイズを確認
    Print("Post array size: ", ArraySize(post));
    Print("JSON length: ", jsonLen);
    
    // null終端文字が含まれている場合のみ削除
    if(ArraySize(post) > jsonLen) {
        ArrayResize(post, jsonLen);
        Print("Resized array to: ", jsonLen);
    }
    
    int res = WebRequest("POST", ServerURL, headers, 5000, post, result, headers);
    
    if(res == 200)
    {
        Print("SUCCESS: ", CharArrayToString(result));
    }
    else if(res == -1)
    {
        Print("WebRequest Error: ", GetLastError());
    }
    else
    {
        Print("HTTP Error: ", res);
        Print("Response: ", CharArrayToString(result));
    }
}
//+------------------------------------------------------------------+