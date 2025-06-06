"""
履歴データ取得API
外部データソースから過去のマーケットデータを取得・インポート
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import pandas as pd

from app.core.database import get_db_connection

router = APIRouter()
logger = logging.getLogger(__name__)

class HistoricalDataRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    timeframe: str = "H1"  # H1, D1, M5, M15, M30
    source: str = "mt5"    # mt5, yahoo, alpha_vantage

@router.post("/historical/import")
async def import_historical_data(request: HistoricalDataRequest, background_tasks: BackgroundTasks):
    """
    履歴データをインポート
    """
    try:
        # バックグラウンドでデータ取得を開始
        background_tasks.add_task(
            fetch_and_store_historical_data,
            request.symbol,
            request.start_date,
            request.end_date,
            request.timeframe,
            request.source
        )
        
        return {
            "status": "started",
            "message": f"{request.symbol} の履歴データ取得を開始しました",
            "symbol": request.symbol,
            "period": f"{request.start_date} to {request.end_date}",
            "timeframe": request.timeframe
        }
        
    except Exception as e:
        logger.error(f"履歴データ取得開始エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"履歴データ取得開始に失敗: {str(e)}")

@router.get("/historical/status/{symbol}")
async def get_import_status(symbol: str):
    """
    インポート状況を確認
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 指定シンボルのデータ状況を取得
        cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                MIN(timestamp) as earliest,
                MAX(timestamp) as latest
            FROM market_data 
            WHERE symbol = ?
        """, (symbol,))
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            "symbol": symbol,
            "total_records": result[0],
            "earliest_data": result[1],
            "latest_data": result[2],
            "has_data": result[0] > 0
        }
        
    except Exception as e:
        logger.error(f"データ状況確認エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"データ状況確認に失敗: {str(e)}")

@router.get("/historical/available-ranges")
async def get_available_ranges():
    """
    利用可能なデータ範囲を取得
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                symbol,
                COUNT(*) as records,
                MIN(timestamp) as start_date,
                MAX(timestamp) as end_date
            FROM market_data 
            GROUP BY symbol
            ORDER BY symbol
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        ranges = []
        for result in results:
            ranges.append({
                "symbol": result[0],
                "records": result[1],
                "start_date": result[2],
                "end_date": result[3]
            })
        
        return {
            "available_ranges": ranges,
            "total_symbols": len(ranges)
        }
        
    except Exception as e:
        logger.error(f"利用可能範囲取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"利用可能範囲取得に失敗: {str(e)}")

@router.delete("/historical/clear/{symbol}")
async def clear_historical_data(symbol: str, confirm: bool = False):
    """
    指定シンボルの履歴データを削除
    """
    if not confirm:
        raise HTTPException(status_code=400, detail="削除確認が必要です。confirm=true を指定してください")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM market_data WHERE symbol = ?", (symbol,))
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        logger.info(f"履歴データ削除完了: {symbol} ({deleted_count}件)")
        
        return {
            "symbol": symbol,
            "deleted_records": deleted_count,
            "status": "deleted"
        }
        
    except Exception as e:
        logger.error(f"履歴データ削除エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"履歴データ削除に失敗: {str(e)}")

async def fetch_and_store_historical_data(symbol: str, start_date: str, end_date: str, timeframe: str, source: str):
    """
    履歴データを取得してデータベースに保存
    """
    try:
        logger.info(f"履歴データ取得開始: {symbol} ({start_date} to {end_date})")
        
        if source == "mt5":
            # MT5からデータを取得（実装例）
            data = await fetch_from_mt5(symbol, start_date, end_date, timeframe)
        elif source == "yahoo":
            # Yahoo Financeからデータを取得
            data = await fetch_from_yahoo(symbol, start_date, end_date)
        else:
            raise ValueError(f"未対応のデータソース: {source}")
        
        if data is not None and len(data) > 0:
            # データベースに保存
            saved_count = await store_market_data(symbol, data)
            logger.info(f"履歴データ保存完了: {symbol} ({saved_count}件)")
        else:
            logger.warning(f"取得データが空です: {symbol}")
            
    except Exception as e:
        logger.error(f"履歴データ取得・保存エラー: {str(e)}")

async def fetch_from_mt5(symbol: str, start_date: str, end_date: str, timeframe: str):
    """
    MT5から履歴データを取得（要実装）
    """
    # この部分は実際のMT5 APIまたはファイルエクスポート機能と連携する必要があります
    logger.warning("MT5履歴データ取得は未実装です。MT5でデータをエクスポートしてCSVインポート機能を使用してください。")
    return None

async def fetch_from_yahoo(symbol: str, start_date: str, end_date: str):
    """
    Yahoo Financeから履歴データを取得（例）
    """
    try:
        # Yahoo Finance APIの例（実際には適切なAPIキーとエンドポイントが必要）
        logger.warning("Yahoo Finance履歴データ取得は未実装です。")
        return None
        
    except Exception as e:
        logger.error(f"Yahoo Finance取得エラー: {str(e)}")
        return None

async def store_market_data(symbol: str, data: pd.DataFrame) -> int:
    """
    マーケットデータをデータベースに保存
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        saved_count = 0
        for _, row in data.iterrows():
            cursor.execute("""
                INSERT OR IGNORE INTO market_data 
                (symbol, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                row['timestamp'],
                float(row['open']),
                float(row['high']),
                float(row['low']),
                float(row['close']),
                float(row.get('volume', 0))
            ))
            
            if cursor.rowcount > 0:
                saved_count += 1
        
        conn.commit()
        conn.close()
        
        return saved_count
        
    except Exception as e:
        logger.error(f"データ保存エラー: {str(e)}")
        return 0