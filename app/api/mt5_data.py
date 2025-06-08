"""
MT5データ取得API
MetaTrader5から直接過年度データを取得してバックテスト用データベースに保存
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import pandas as pd
import json

from app.core.database import get_db_connection

router = APIRouter()
logger = logging.getLogger(__name__)

# MT5からのデータ受信用エンドポイント
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
            raise HTTPException(status_code=400, detail="シンボルまたはデータが不足しています")
        
        # データベースに保存（重複チェック付き）
        result = await save_mt5_historical_data_with_duplicate_check(symbol, data_records, check_duplicates)
        saved_count = result["saved"]
        duplicate_count = result["duplicates"]
        
        logger.info(f"MT5バッチデータ受信: {symbol} バッチ#{batch_number} ({saved_count}/{len(data_records)}件保存, {duplicate_count}件重複)")
        
        return {
            "success": True,
            "status": "success",
            "symbol": symbol,
            "batch_number": batch_number,
            "received_records": len(data_records),
            "saved": saved_count,
            "duplicates": duplicate_count,
            "message": f"保存: {saved_count}件, 重複: {duplicate_count}件"
        }
        
    except Exception as e:
        logger.error(f"MT5バッチデータ受信エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"バッチデータ受信に失敗: {str(e)}")

@router.post("/mt5/receive-symbols")
async def receive_symbols_list(symbols_data: Dict[str, Any]):
    """
    MT5から利用可能なシンボル一覧を受信
    """
    try:
        symbols = symbols_data.get("symbols", [])
        total_count = symbols_data.get("total_count", 0)
        
        logger.info(f"MT5シンボル一覧受信: {total_count}個のシンボル")
        
        # 主要通貨ペアをフィルタリング
        major_pairs = []
        fx_pairs = []
        
        for symbol in symbols:
            if any(pair in symbol for pair in ["USD", "EUR", "GBP", "JPY", "AUD", "CHF", "CAD"]):
                fx_pairs.append(symbol)
                if symbol in ["USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD"]:
                    major_pairs.append(symbol)
        
        return {
            "status": "received",
            "total_symbols": total_count,
            "fx_pairs": fx_pairs,
            "major_pairs": major_pairs,
            "major_pairs_count": len(major_pairs),
            "fx_pairs_count": len(fx_pairs)
        }
        
    except Exception as e:
        logger.error(f"シンボル一覧受信エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"シンボル一覧受信に失敗: {str(e)}")

@router.post("/mt5/trigger-historical-download")
async def trigger_historical_download(
    symbol: str = "USDJPY",
    year: int = 2023,
    timeframe: str = "H1"
):
    """
    MT5に履歴データダウンロードを指示
    
    Note: この機能を使うには、MT5でMT5_Historical_Data_EAを起動し、
          EA内のDownloadYearData()関数を手動で実行する必要があります。
    """
    try:
        # MT5がアクティブかチェック（実際の実装では、MT5との通信状態を確認）
        logger.info(f"履歴データダウンロード要求: {symbol} ({year}年)")
        
        # この情報をログに記録し、ユーザーに手動手順を案内
        instructions = f"""
        MT5履歴データダウンロード手順:
        
        1. MetaTrader 5を開く
        2. MT5_Historical_Data_EAが起動していることを確認
        3. エキスパートタブでコードを実行:
           
           // {year}年の{symbol}データをダウンロード
           DownloadYearData("{symbol}", {year}, PERIOD_{timeframe});
           
        4. または、Experts/Scripts/で以下を実行:
           
           void OnStart()
           {{
               DownloadYearData("{symbol}", {year}, PERIOD_{timeframe});
           }}
        
        5. ダウンロード完了まで待機（進捗はMT5のログで確認）
        """
        
        return {
            "status": "instructions_provided",
            "symbol": symbol,
            "year": year,
            "timeframe": timeframe,
            "message": "MT5でのデータダウンロード手順を確認してください",
            "instructions": instructions,
            "api_endpoint": "/api/v1/mt5/receive-historical-batch",
            "expected_records": f"約8760件（{year}年の1時間足データ）"
        }
        
    except Exception as e:
        logger.error(f"履歴データダウンロード指示エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ダウンロード指示に失敗: {str(e)}")

@router.post("/mt5/receive-terminal-info")
async def receive_terminal_info(terminal_data: Dict[str, Any]):
    """
    MT5ターミナル情報を受信
    """
    try:
        terminal_info = terminal_data.get("terminal_info", {})
        account_info = terminal_data.get("account_info", {})
        
        logger.info(f"MT5ターミナル情報受信: {terminal_info.get('name', 'Unknown')} Build#{terminal_info.get('build', 'Unknown')}")
        
        return {
            "status": "received",
            "terminal": {
                "name": terminal_info.get("name"),
                "build": terminal_info.get("build"),
                "connected": terminal_info.get("connected", False),
                "max_bars": terminal_info.get("max_bars")
            },
            "account": {
                "server": account_info.get("server"),
                "login": account_info.get("login"),
                "currency": account_info.get("currency"),
                "balance": account_info.get("balance")
            }
        }
        
    except Exception as e:
        logger.error(f"ターミナル情報受信エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ターミナル情報受信に失敗: {str(e)}")

class MT5DataRequest(BaseModel):
    symbol: str
    start_date: str  # YYYY-MM-DD format
    end_date: str    # YYYY-MM-DD format
    timeframe: str = "H1"  # M1, M5, M15, M30, H1, H4, D1
    max_bars: int = 50000  # 最大取得バー数

class MT5ConnectionTest(BaseModel):
    terminal_path: Optional[str] = None
    login: Optional[int] = None
    server: Optional[str] = None

@router.post("/mt5/test-connection")
async def test_mt5_connection():
    """
    MT5との接続をテスト
    """
    try:
        # MT5接続テスト用のHTTPリクエストを送信
        test_result = await send_mt5_command("test_connection", {})
        
        return {
            "status": "success" if test_result.get("connected", False) else "failed",
            "message": test_result.get("message", "MT5接続テスト完了"),
            "terminal_info": test_result.get("terminal_info", {}),
            "account_info": test_result.get("account_info", {})
        }
        
    except Exception as e:
        logger.error(f"MT5接続テストエラー: {str(e)}")
        return {
            "status": "failed",
            "message": f"MT5接続テストに失敗: {str(e)}",
            "suggestion": "MT5が起動しており、EAが動作していることを確認してください"
        }

@router.get("/mt5/symbols")
async def get_mt5_symbols():
    """
    MT5で利用可能な通貨ペア一覧を取得
    """
    try:
        result = await send_mt5_command("get_symbols", {})
        
        return {
            "symbols": result.get("symbols", []),
            "count": len(result.get("symbols", [])),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"MT5通貨ペア取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"通貨ペア取得に失敗: {str(e)}")

@router.post("/mt5/download-historical")
async def download_historical_data(request: MT5DataRequest, background_tasks: BackgroundTasks):
    """
    MT5から過年度データをダウンロード
    """
    try:
        # リクエスト検証
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
        
        if start_dt >= end_dt:
            raise HTTPException(status_code=400, detail="開始日は終了日より前である必要があります")
        
        if end_dt > datetime.now():
            raise HTTPException(status_code=400, detail="終了日は現在日時より前である必要があります")
        
        # 期間が長すぎる場合の警告
        days_diff = (end_dt - start_dt).days
        if days_diff > 365 * 2:  # 2年以上
            logger.warning(f"長期間のデータ要求: {days_diff}日間")
        
        # バックグラウンドでデータ取得を開始
        background_tasks.add_task(
            execute_mt5_data_download,
            request.symbol,
            request.start_date,
            request.end_date,
            request.timeframe,
            request.max_bars
        )
        
        return {
            "status": "started",
            "message": f"{request.symbol} の過年度データ取得を開始しました",
            "symbol": request.symbol,
            "period": f"{request.start_date} to {request.end_date}",
            "timeframe": request.timeframe,
            "estimated_bars": min(request.max_bars, days_diff * 24 if request.timeframe == "H1" else days_diff)
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"日付形式エラー: {str(e)}")
    except Exception as e:
        logger.error(f"MT5データダウンロード開始エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"データダウンロード開始に失敗: {str(e)}")

@router.get("/mt5/download-status/{symbol}")
async def get_download_status(symbol: str):
    """
    データダウンロードの進捗状況を確認
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 最近1時間以内のデータ追加状況をチェック
        cursor.execute("""
            SELECT 
                COUNT(*) as new_records,
                MIN(timestamp) as earliest_new,
                MAX(timestamp) as latest_new
            FROM market_data 
            WHERE symbol = ? 
            AND created_at > datetime('now', '-1 hour')
        """, (symbol,))
        
        recent_result = cursor.fetchone()
        
        # 全体のデータ状況
        cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                MIN(timestamp) as earliest,
                MAX(timestamp) as latest
            FROM market_data 
            WHERE symbol = ?
        """, (symbol,))
        
        total_result = cursor.fetchone()
        conn.close()
        
        return {
            "symbol": symbol,
            "recent_download": {
                "new_records": recent_result[0],
                "earliest_new": recent_result[1],
                "latest_new": recent_result[2]
            },
            "total_data": {
                "total_records": total_result[0],
                "data_range": {
                    "start": total_result[1],
                    "end": total_result[2]
                }
            },
            "status": "active" if recent_result[0] > 0 else "completed"
        }
        
    except Exception as e:
        logger.error(f"ダウンロード状況確認エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"状況確認に失敗: {str(e)}")

@router.get("/mt5/timeframes")
async def get_available_timeframes():
    """
    利用可能なタイムフレーム一覧を取得
    """
    return {
        "timeframes": {
            "M1": {"description": "1分足", "bars_per_day": 1440},
            "M5": {"description": "5分足", "bars_per_day": 288},
            "M15": {"description": "15分足", "bars_per_day": 96},
            "M30": {"description": "30分足", "bars_per_day": 48},
            "H1": {"description": "1時間足", "bars_per_day": 24},
            "H4": {"description": "4時間足", "bars_per_day": 6},
            "D1": {"description": "日足", "bars_per_day": 1}
        },
        "recommended": "H1",
        "note": "バックテスト用には H1 (1時間足) を推奨します"
    }

@router.post("/mt5/bulk-download")
async def bulk_download_multiple_symbols(
    symbols: List[str],
    start_date: str,
    end_date: str,
    background_tasks: BackgroundTasks,
    timeframe: str = "H1"
):
    """
    複数通貨ペアの一括データダウンロード
    """
    try:
        if len(symbols) > 10:
            raise HTTPException(status_code=400, detail="一度に処理できる通貨ペアは10個までです")
        
        # 各通貨ペアのダウンロードタスクを追加
        for symbol in symbols:
            background_tasks.add_task(
                execute_mt5_data_download,
                symbol,
                start_date,
                end_date,
                timeframe,
                50000
            )
        
        return {
            "status": "started",
            "message": f"{len(symbols)}通貨ペアの一括データダウンロードを開始",
            "symbols": symbols,
            "period": f"{start_date} to {end_date}",
            "timeframe": timeframe
        }
        
    except Exception as e:
        logger.error(f"一括ダウンロードエラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"一括ダウンロードに失敗: {str(e)}")

async def execute_mt5_data_download(symbol: str, start_date: str, end_date: str, timeframe: str, max_bars: int):
    """
    MT5から実際にデータをダウンロードして保存
    """
    try:
        logger.info(f"MT5データダウンロード開始: {symbol} ({start_date} to {end_date})")
        
        # MT5に履歴データ要求を送信
        request_data = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "timeframe": timeframe,
            "max_bars": max_bars
        }
        
        result = await send_mt5_command("get_historical_data", request_data)
        
        if result.get("success", False):
            # 取得したデータをデータベースに保存
            data_records = result.get("data", [])
            saved_count = await save_mt5_historical_data(symbol, data_records)
            
            logger.info(f"MT5データ保存完了: {symbol} ({saved_count}件)")
        else:
            error_msg = result.get("error", "不明なエラー")
            logger.error(f"MT5データ取得失敗: {symbol} - {error_msg}")
            
    except Exception as e:
        logger.error(f"MT5データダウンロード実行エラー: {str(e)}")

async def send_mt5_command(command: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    MT5 EAにHTTPリクエストを送信してコマンドを実行
    """
    try:
        import aiohttp
        import asyncio
        
        # MT5 EA用の特別なエンドポイントにリクエスト送信
        url = "http://127.0.0.1:8000/api/mt5/execute"
        
        payload = {
            "command": command,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
                    
    except ImportError:
        # aiohttpがない場合のフォールバック
        logger.warning("aiohttp not available, using simulated response")
        return await simulate_mt5_response(command, data)
    except Exception as e:
        logger.error(f"MT5コマンド送信エラー: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

async def simulate_mt5_response(command: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    MT5レスポンスのシミュレーション（開発・テスト用）
    """
    if command == "test_connection":
        return {
            "connected": True,
            "message": "MT5接続テスト成功（シミュレーション）",
            "terminal_info": {
                "version": "5.0.37",
                "build": "3610"
            },
            "account_info": {
                "login": "12345678",
                "server": "Demo-Server"
            }
        }
    elif command == "get_symbols":
        return {
            "symbols": ["USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "EURJPY", "GBPJPY"],
            "success": True
        }
    elif command == "get_historical_data":
        # サンプルデータを生成
        import random
        sample_data = []
        
        start_dt = datetime.strptime(data["start_date"], "%Y-%m-%d")
        current_dt = start_dt
        base_price = 143.50  # USDJPY基準価格
        
        for i in range(min(100, data.get("max_bars", 100))):  # サンプル用に100件まで
            # ランダムな価格変動
            price_change = random.uniform(-0.5, 0.5)
            open_price = base_price + price_change
            high_price = open_price + random.uniform(0, 0.3)
            low_price = open_price - random.uniform(0, 0.3)
            close_price = open_price + random.uniform(-0.2, 0.2)
            
            sample_data.append({
                "timestamp": current_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "open": round(open_price, 5),
                "high": round(high_price, 5),
                "low": round(low_price, 5),
                "close": round(close_price, 5),
                "volume": random.randint(100, 1000)
            })
            
            # 次の時間に進む
            if data.get("timeframe") == "H1":
                current_dt += timedelta(hours=1)
            else:
                current_dt += timedelta(hours=1)  # デフォルト1時間
                
            base_price = close_price  # 次のバーの基準価格
        
        return {
            "success": True,
            "data": sample_data,
            "message": f"{len(sample_data)}件のサンプルデータを生成"
        }
    else:
        return {
            "success": False,
            "error": f"未対応のコマンド: {command}"
        }

async def save_mt5_historical_data_with_duplicate_check(symbol: str, data_records: List[Dict[str, Any]], check_duplicates: bool = True) -> Dict[str, int]:
    """
    MT5から取得した履歴データをデータベースに保存（重複チェック機能付き）
    """
    try:
        if not data_records:
            return {"saved": 0, "duplicates": 0}
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        saved_count = 0
        duplicate_count = 0
        
        # 重複チェックが有効な場合、既存のタイムスタンプを事前に取得
        existing_timestamps = set()
        if check_duplicates:
            cursor.execute("""
                SELECT DISTINCT timestamp FROM market_data 
                WHERE symbol = ?
            """, (symbol,))
            existing_timestamps = {row[0] for row in cursor.fetchall()}
            logger.info(f"既存データ確認: {symbol}で{len(existing_timestamps)}件のタイムスタンプ")
        
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
                        existing_timestamps.add(timestamp)  # 新しく追加したタイムスタンプを記録
                else:
                    duplicate_count += 1
                    
            except Exception as e:
                logger.warning(f"データ保存スキップ: {record.get('timestamp')} - {str(e)}")
        
        conn.commit()
        conn.close()
        
        return {
            "saved": saved_count,
            "duplicates": duplicate_count
        }
        
    except Exception as e:
        logger.error(f"MT5データ保存エラー: {str(e)}")
        return {"saved": 0, "duplicates": 0}

async def save_mt5_historical_data(symbol: str, data_records: List[Dict[str, Any]]) -> int:
    """
    MT5から取得した履歴データをデータベースに保存（後方互換性のため）
    """
    result = await save_mt5_historical_data_with_duplicate_check(symbol, data_records, False)
    return result["saved"]