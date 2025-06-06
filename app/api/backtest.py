"""
バックテストAPI
過去データを使用した取引戦略の検証機能を提供
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import logging

from app.core.database import get_db_connection
from app.services.backtest_engine import BacktestEngine

router = APIRouter()
logger = logging.getLogger(__name__)

class BacktestRequest(BaseModel):
    name: str
    symbol: str
    start_date: str
    end_date: str
    parameters: Dict[str, Any]
    strategy_type: str = "dow_elliott"
    initial_balance: float = 100000.0
    risk_per_trade: float = 0.02
    max_positions: int = 3

class BacktestResult(BaseModel):
    id: Optional[int] = None
    name: str
    symbol: str
    start_date: str
    end_date: str
    parameters: Dict[str, Any]
    total_trades: int
    winning_trades: int
    total_profit: float
    max_drawdown: float
    sharpe_ratio: Optional[float]
    win_rate: float
    profit_factor: Optional[float]
    created_at: Optional[datetime] = None

class BacktestTrade(BaseModel):
    symbol: str
    side: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    quantity: float
    profit_loss: float

@router.post("/backtest/run", response_model=Dict[str, Any])
async def run_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """
    バックテストを実行
    """
    try:
        # パラメータ検証
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)
        
        if start_date >= end_date:
            raise HTTPException(status_code=400, detail="開始日は終了日より前である必要があります")
        
        if end_date > datetime.now():
            raise HTTPException(status_code=400, detail="終了日は現在日時より前である必要があります")
        
        # バックテストIDを生成
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO backtest_results 
            (name, symbol, start_date, end_date, parameters, total_trades, 
             winning_trades, total_profit, max_drawdown, win_rate, created_at)
            VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?)
        """, (
            request.name,
            request.symbol,
            request.start_date,
            request.end_date,
            json.dumps(request.parameters),
            datetime.now()
        ))
        
        backtest_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # バックグラウンドでバックテスト実行
        background_tasks.add_task(
            execute_backtest, 
            backtest_id, 
            request
        )
        
        logger.info(f"バックテスト開始: {request.name} ({request.symbol})")
        
        return {
            "backtest_id": backtest_id,
            "status": "started",
            "message": f"バックテスト '{request.name}' をバックグラウンドで開始しました"
        }
        
    except Exception as e:
        logger.error(f"バックテスト開始エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"バックテスト開始に失敗しました: {str(e)}")

@router.get("/backtest/results", response_model=List[BacktestResult])
async def get_backtest_results(
    symbol: Optional[str] = None,
    limit: int = 50
):
    """
    バックテスト結果一覧を取得
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM backtest_results WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            result = BacktestResult(
                id=row[0],
                name=row[1],
                symbol=row[2],
                start_date=row[3],
                end_date=row[4],
                parameters=json.loads(row[5]),
                total_trades=row[6],
                winning_trades=row[7],
                total_profit=row[8],
                max_drawdown=row[9],
                sharpe_ratio=row[10],
                win_rate=row[11],
                profit_factor=row[12],
                created_at=row[13]
            )
            results.append(result)
        
        return results
        
    except Exception as e:
        logger.error(f"バックテスト結果取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"バックテスト結果取得に失敗しました: {str(e)}")

@router.get("/backtest/results/{backtest_id}", response_model=Dict[str, Any])
async def get_backtest_detail(backtest_id: int):
    """
    特定のバックテスト結果詳細を取得
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # バックテスト結果を取得
        cursor.execute("SELECT * FROM backtest_results WHERE id = ?", (backtest_id,))
        result_row = cursor.fetchone()
        
        if not result_row:
            raise HTTPException(status_code=404, detail="バックテスト結果が見つかりません")
        
        # 取引履歴を取得
        cursor.execute("""
            SELECT * FROM backtest_trades 
            WHERE backtest_id = ? 
            ORDER BY entry_time
        """, (backtest_id,))
        
        trade_rows = cursor.fetchall()
        conn.close()
        
        # 結果を構築
        result = {
            "id": result_row[0],
            "name": result_row[1],
            "symbol": result_row[2],
            "start_date": result_row[3],
            "end_date": result_row[4],
            "parameters": json.loads(result_row[5]),
            "total_trades": result_row[6],
            "winning_trades": result_row[7],
            "total_profit": result_row[8],
            "max_drawdown": result_row[9],
            "sharpe_ratio": result_row[10],
            "win_rate": result_row[11],
            "profit_factor": result_row[12],
            "created_at": result_row[13],
            "trades": []
        }
        
        # 取引履歴を追加
        for trade_row in trade_rows:
            trade = {
                "id": trade_row[0],
                "symbol": trade_row[2],
                "side": trade_row[3],
                "entry_time": trade_row[4],
                "exit_time": trade_row[5],
                "entry_price": trade_row[6],
                "exit_price": trade_row[7],
                "quantity": trade_row[8],
                "profit_loss": trade_row[9]
            }
            result["trades"].append(trade)
        
        return result
        
    except Exception as e:
        logger.error(f"バックテスト詳細取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"バックテスト詳細取得に失敗しました: {str(e)}")

@router.get("/backtest/status/{backtest_id}")
async def get_backtest_status(backtest_id: int):
    """
    バックテストの実行状況を取得
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT total_trades, created_at FROM backtest_results 
            WHERE id = ?
        """, (backtest_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="バックテストが見つかりません")
        
        # 実行状況を判定
        total_trades = row[0]
        created_at = datetime.fromisoformat(row[1])
        elapsed_time = datetime.now() - created_at
        
        if total_trades > 0:
            status = "completed"
        elif elapsed_time.total_seconds() > 3600:  # 1時間以上経過
            status = "timeout"
        else:
            status = "running"
        
        return {
            "backtest_id": backtest_id,
            "status": status,
            "total_trades": total_trades,
            "elapsed_time_seconds": elapsed_time.total_seconds(),
            "created_at": row[1]
        }
        
    except Exception as e:
        logger.error(f"バックテスト状況取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"バックテスト状況取得に失敗しました: {str(e)}")

@router.delete("/backtest/results/{backtest_id}")
async def delete_backtest_result(backtest_id: int):
    """
    バックテスト結果を削除
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 取引履歴を削除
        cursor.execute("DELETE FROM backtest_trades WHERE backtest_id = ?", (backtest_id,))
        
        # バックテスト結果を削除
        cursor.execute("DELETE FROM backtest_results WHERE id = ?", (backtest_id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="バックテスト結果が見つかりません")
        
        conn.commit()
        conn.close()
        
        logger.info(f"バックテスト結果削除: ID={backtest_id}")
        
        return {
            "backtest_id": backtest_id,
            "status": "deleted",
            "message": "バックテスト結果が削除されました"
        }
        
    except Exception as e:
        logger.error(f"バックテスト結果削除エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"バックテスト結果削除に失敗しました: {str(e)}")

@router.get("/backtest/compare")
async def compare_backtest_results(backtest_ids: str):
    """
    複数のバックテスト結果を比較
    """
    try:
        # IDリストを解析
        id_list = [int(id.strip()) for id in backtest_ids.split(',')]
        
        if len(id_list) < 2:
            raise HTTPException(status_code=400, detail="比較には2つ以上のバックテストIDが必要です")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        results = []
        for backtest_id in id_list:
            cursor.execute("SELECT * FROM backtest_results WHERE id = ?", (backtest_id,))
            row = cursor.fetchone()
            
            if row:
                result = {
                    "id": row[0],
                    "name": row[1],
                    "symbol": row[2],
                    "parameters": json.loads(row[5]),
                    "total_trades": row[6],
                    "winning_trades": row[7],
                    "total_profit": row[8],
                    "max_drawdown": row[9],
                    "sharpe_ratio": row[10],
                    "win_rate": row[11],
                    "profit_factor": row[12]
                }
                results.append(result)
        
        conn.close()
        
        # 比較分析
        if len(results) >= 2:
            comparison = analyze_backtest_comparison(results)
        else:
            comparison = {"error": "比較可能な結果が不足しています"}
        
        return {
            "results": results,
            "comparison": comparison
        }
        
    except Exception as e:
        logger.error(f"バックテスト比較エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"バックテスト比較に失敗しました: {str(e)}")

# バックグラウンド処理関数
async def execute_backtest(backtest_id: int, request: BacktestRequest):
    """
    バックテストを実際に実行
    """
    try:
        logger.info(f"バックテスト実行開始: ID={backtest_id}")
        
        # バックテストエンジンを初期化
        engine = BacktestEngine()
        
        # バックテストを実行
        result = await engine.run_backtest(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            parameters=request.parameters,
            initial_balance=request.initial_balance,
            risk_per_trade=request.risk_per_trade,
            max_positions=request.max_positions
        )
        
        # 結果をデータベースに保存
        await save_backtest_result(backtest_id, result)
        
        logger.info(f"バックテスト完了: ID={backtest_id}, 取引数={result['total_trades']}")
        
    except Exception as e:
        logger.error(f"バックテスト実行エラー: {str(e)}")
        
        # エラー情報をデータベースに記録
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE backtest_results 
            SET total_profit = -999999
            WHERE id = ?
        """, (backtest_id,))
        conn.commit()
        conn.close()

async def save_backtest_result(backtest_id: int, result: Dict[str, Any]):
    """
    バックテスト結果をデータベースに保存
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # メイン結果を更新
        cursor.execute("""
            UPDATE backtest_results 
            SET total_trades = ?, winning_trades = ?, total_profit = ?,
                max_drawdown = ?, sharpe_ratio = ?, win_rate = ?, profit_factor = ?
            WHERE id = ?
        """, (
            result['total_trades'],
            result['winning_trades'],
            result['total_profit'],
            result['max_drawdown'],
            result.get('sharpe_ratio'),
            result['win_rate'],
            result.get('profit_factor'),
            backtest_id
        ))
        
        # 取引履歴を保存
        for trade in result.get('trades', []):
            cursor.execute("""
                INSERT INTO backtest_trades 
                (backtest_id, symbol, side, entry_time, exit_time, 
                 entry_price, exit_price, quantity, profit_loss)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                backtest_id,
                trade['symbol'],
                trade['side'],
                trade['entry_time'],
                trade['exit_time'],
                trade['entry_price'],
                trade['exit_price'],
                trade['quantity'],
                trade['profit_loss']
            ))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"バックテスト結果保存エラー: {str(e)}")

def analyze_backtest_comparison(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    バックテスト結果の比較分析
    """
    try:
        best_profit = max(results, key=lambda x: x['total_profit'])
        best_win_rate = max(results, key=lambda x: x['win_rate'])
        best_sharpe = max(results, key=lambda x: x['sharpe_ratio'] or 0)
        lowest_drawdown = min(results, key=lambda x: x['max_drawdown'])
        
        return {
            "best_total_profit": {
                "name": best_profit['name'],
                "value": best_profit['total_profit']
            },
            "best_win_rate": {
                "name": best_win_rate['name'],
                "value": best_win_rate['win_rate']
            },
            "best_sharpe_ratio": {
                "name": best_sharpe['name'],
                "value": best_sharpe['sharpe_ratio']
            },
            "lowest_drawdown": {
                "name": lowest_drawdown['name'],
                "value": lowest_drawdown['max_drawdown']
            }
        }
        
    except Exception as e:
        logger.error(f"バックテスト比較分析エラー: {str(e)}")
        return {"error": str(e)}