"""
パラメータ最適化API
取引戦略のパラメータを自動最適化する機能を提供
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import json
import logging

from app.core.database import get_db_connection
from app.services.optimization_engine import OptimizationEngine

router = APIRouter()
logger = logging.getLogger(__name__)

class OptimizationRequest(BaseModel):
    name: str
    symbol: str
    start_date: str
    end_date: str
    optimization_type: str = "genetic_algorithm"  # genetic_algorithm, grid_search, random_search
    objective_function: str = "sharpe_ratio"  # sharpe_ratio, total_profit, win_rate, profit_factor
    max_iterations: int = 100
    population_size: int = 50  # 遺伝的アルゴリズム用
    parameters: Dict[str, Dict[str, Union[float, int, List]]]  # パラメータ範囲定義

class ParameterRange(BaseModel):
    min_value: Union[float, int]
    max_value: Union[float, int]
    step: Optional[Union[float, int]] = None
    type: str = "float"  # float, int, choice

class OptimizationResult(BaseModel):
    id: Optional[int] = None
    name: str
    symbol: str
    optimization_type: str
    objective_function: str
    best_parameters: Dict[str, Any]
    best_score: float
    total_iterations: int
    status: str
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

@router.post("/optimization/run", response_model=Dict[str, Any])
async def run_optimization(request: OptimizationRequest, background_tasks: BackgroundTasks):
    """
    パラメータ最適化を実行
    """
    try:
        # リクエスト検証
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)
        
        if start_date >= end_date:
            raise HTTPException(status_code=400, detail="開始日は終了日より前である必要があります")
        
        # 最適化ジョブをデータベースに登録
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO optimization_jobs 
            (name, symbol, start_date, end_date, optimization_type, 
             objective_function, max_iterations, parameters, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)
        """, (
            request.name,
            request.symbol,
            request.start_date,
            request.end_date,
            request.optimization_type,
            request.objective_function,
            request.max_iterations,
            json.dumps(request.parameters),
            datetime.now()
        ))
        
        optimization_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # バックグラウンドで最適化実行
        background_tasks.add_task(
            execute_optimization,
            optimization_id,
            request
        )
        
        logger.info(f"最適化開始: {request.name} ({request.symbol})")
        
        return {
            "optimization_id": optimization_id,
            "status": "started",
            "message": f"パラメータ最適化 '{request.name}' をバックグラウンドで開始しました"
        }
        
    except Exception as e:
        logger.error(f"最適化開始エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"最適化開始に失敗しました: {str(e)}")

@router.get("/optimization/results", response_model=List[Dict[str, Any]])
async def get_optimization_results(
    symbol: Optional[str] = None,
    optimization_type: Optional[str] = None,
    limit: int = 50
):
    """
    最適化結果一覧を取得
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM optimization_jobs WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
            
        if optimization_type:
            query += " AND optimization_type = ?"
            params.append(optimization_type)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            result = {
                "id": row[0],
                "name": row[1],
                "symbol": row[2],
                "start_date": row[3],
                "end_date": row[4],
                "optimization_type": row[5],
                "objective_function": row[6],
                "max_iterations": row[7],
                "parameters": json.loads(row[8]) if row[8] else {},
                "status": row[9],
                "best_parameters": json.loads(row[10]) if row[10] else {},
                "best_score": row[11],
                "total_iterations": row[12],
                "created_at": row[13],
                "completed_at": row[14]
            }
            results.append(result)
        
        return results
        
    except Exception as e:
        logger.error(f"最適化結果取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"最適化結果取得に失敗しました: {str(e)}")

@router.get("/optimization/results/{optimization_id}", response_model=Dict[str, Any])
async def get_optimization_detail(optimization_id: int):
    """
    特定の最適化結果詳細を取得
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 最適化結果を取得
        cursor.execute("SELECT * FROM optimization_jobs WHERE id = ?", (optimization_id,))
        result_row = cursor.fetchone()
        
        if not result_row:
            raise HTTPException(status_code=404, detail="最適化結果が見つかりません")
        
        # 最適化履歴を取得
        cursor.execute("""
            SELECT * FROM optimization_history 
            WHERE optimization_id = ? 
            ORDER BY iteration
        """, (optimization_id,))
        
        history_rows = cursor.fetchall()
        conn.close()
        
        # 結果を構築
        result = {
            "id": result_row[0],
            "name": result_row[1],
            "symbol": result_row[2],
            "start_date": result_row[3],
            "end_date": result_row[4],
            "optimization_type": result_row[5],
            "objective_function": result_row[6],
            "max_iterations": result_row[7],
            "parameters": json.loads(result_row[8]) if result_row[8] else {},
            "status": result_row[9],
            "best_parameters": json.loads(result_row[10]) if result_row[10] else {},
            "best_score": result_row[11],
            "total_iterations": result_row[12],
            "created_at": result_row[13],
            "completed_at": result_row[14],
            "history": []
        }
        
        # 最適化履歴を追加
        for history_row in history_rows:
            history = {
                "iteration": history_row[2],
                "parameters": json.loads(history_row[3]),
                "score": history_row[4],
                "metrics": json.loads(history_row[5]) if history_row[5] else {}
            }
            result["history"].append(history)
        
        return result
        
    except Exception as e:
        logger.error(f"最適化詳細取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"最適化詳細取得に失敗しました: {str(e)}")

@router.get("/optimization/status/{optimization_id}")
async def get_optimization_status(optimization_id: int):
    """
    最適化の実行状況を取得
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT status, total_iterations, created_at, completed_at
            FROM optimization_jobs 
            WHERE id = ?
        """, (optimization_id,))
        
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="最適化ジョブが見つかりません")
        
        # 現在の進捗を取得
        cursor.execute("""
            SELECT COUNT(*) FROM optimization_history 
            WHERE optimization_id = ?
        """, (optimization_id,))
        
        completed_iterations = cursor.fetchone()[0]
        conn.close()
        
        created_at = datetime.fromisoformat(row[2])
        elapsed_time = datetime.now() - created_at
        
        progress = 0
        if row[1] and row[1] > 0:  # total_iterations
            progress = (completed_iterations / row[1]) * 100
        
        return {
            "optimization_id": optimization_id,
            "status": row[0],
            "progress_percentage": min(100, progress),
            "completed_iterations": completed_iterations,
            "total_iterations": row[1],
            "elapsed_time_seconds": elapsed_time.total_seconds(),
            "created_at": row[2],
            "completed_at": row[3]
        }
        
    except Exception as e:
        logger.error(f"最適化状況取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"最適化状況取得に失敗しました: {str(e)}")

@router.delete("/optimization/results/{optimization_id}")
async def delete_optimization_result(optimization_id: int):
    """
    最適化結果を削除
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 最適化履歴を削除
        cursor.execute("DELETE FROM optimization_history WHERE optimization_id = ?", (optimization_id,))
        
        # 最適化ジョブを削除
        cursor.execute("DELETE FROM optimization_jobs WHERE id = ?", (optimization_id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="最適化結果が見つかりません")
        
        conn.commit()
        conn.close()
        
        logger.info(f"最適化結果削除: ID={optimization_id}")
        
        return {
            "optimization_id": optimization_id,
            "status": "deleted",
            "message": "最適化結果が削除されました"
        }
        
    except Exception as e:
        logger.error(f"最適化結果削除エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"最適化結果削除に失敗しました: {str(e)}")

@router.post("/optimization/stop/{optimization_id}")
async def stop_optimization(optimization_id: int):
    """
    実行中の最適化を停止
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE optimization_jobs 
            SET status = 'stopped', completed_at = ?
            WHERE id = ? AND status = 'running'
        """, (datetime.now(), optimization_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="実行中の最適化が見つかりません")
        
        conn.commit()
        conn.close()
        
        logger.info(f"最適化停止: ID={optimization_id}")
        
        return {
            "optimization_id": optimization_id,
            "status": "stopped",
            "message": "最適化が停止されました"
        }
        
    except Exception as e:
        logger.error(f"最適化停止エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"最適化停止に失敗しました: {str(e)}")

@router.get("/optimization/templates")
async def get_optimization_templates():
    """
    最適化テンプレートを取得
    """
    try:
        templates = {
            "dow_elliott_basic": {
                "name": "ダウ理論・エリオット波動基本",
                "parameters": {
                    "ma_period": {"min_value": 10, "max_value": 50, "type": "int"},
                    "rsi_period": {"min_value": 10, "max_value": 20, "type": "int"},
                    "bb_period": {"min_value": 15, "max_value": 30, "type": "int"},
                    "bb_std": {"min_value": 1.5, "max_value": 2.5, "type": "float", "step": 0.1},
                    "atr_period": {"min_value": 10, "max_value": 20, "type": "int"},
                    "entry_threshold": {"min_value": 40, "max_value": 70, "type": "int"},
                    "swing_threshold": {"min_value": 0.3, "max_value": 0.8, "type": "float", "step": 0.1},
                    "max_hold_hours": {"min_value": 24, "max_value": 168, "type": "int"}
                }
            },
            "trend_following": {
                "name": "トレンドフォロー戦略",
                "parameters": {
                    "fast_ma": {"min_value": 5, "max_value": 20, "type": "int"},
                    "slow_ma": {"min_value": 20, "max_value": 100, "type": "int"},
                    "rsi_oversold": {"min_value": 20, "max_value": 40, "type": "int"},
                    "rsi_overbought": {"min_value": 60, "max_value": 80, "type": "int"},
                    "stop_loss_pct": {"min_value": 1, "max_value": 5, "type": "float", "step": 0.5},
                    "take_profit_pct": {"min_value": 2, "max_value": 10, "type": "float", "step": 0.5}
                }
            },
            "mean_reversion": {
                "name": "平均回帰戦略",
                "parameters": {
                    "bb_period": {"min_value": 15, "max_value": 40, "type": "int"},
                    "bb_std": {"min_value": 1.8, "max_value": 2.5, "type": "float", "step": 0.1},
                    "rsi_period": {"min_value": 10, "max_value": 25, "type": "int"},
                    "rsi_lower": {"min_value": 15, "max_value": 35, "type": "int"},
                    "rsi_upper": {"min_value": 65, "max_value": 85, "type": "int"},
                    "hold_time_hours": {"min_value": 4, "max_value": 48, "type": "int"}
                }
            }
        }
        
        return {
            "templates": templates,
            "objective_functions": [
                {"value": "sharpe_ratio", "label": "シャープレシオ"},
                {"value": "total_profit", "label": "総利益"},
                {"value": "win_rate", "label": "勝率"},
                {"value": "profit_factor", "label": "プロフィットファクター"},
                {"value": "max_drawdown", "label": "最大ドローダウン（最小化）"}
            ],
            "optimization_types": [
                {"value": "genetic_algorithm", "label": "遺伝的アルゴリズム"},
                {"value": "grid_search", "label": "グリッドサーチ"},
                {"value": "random_search", "label": "ランダムサーチ"},
                {"value": "bayesian_optimization", "label": "ベイズ最適化"}
            ]
        }
        
    except Exception as e:
        logger.error(f"最適化テンプレート取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"最適化テンプレート取得に失敗しました: {str(e)}")

# バックグラウンド処理関数
async def execute_optimization(optimization_id: int, request: OptimizationRequest):
    """
    最適化を実際に実行
    """
    try:
        logger.info(f"最適化実行開始: ID={optimization_id}")
        
        # 最適化エンジンを初期化
        engine = OptimizationEngine()
        
        # 最適化を実行
        result = await engine.run_optimization(
            optimization_id=optimization_id,
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            optimization_type=request.optimization_type,
            objective_function=request.objective_function,
            max_iterations=request.max_iterations,
            population_size=request.population_size,
            parameters=request.parameters
        )
        
        # 結果をデータベースに保存
        await save_optimization_result(optimization_id, result)
        
        logger.info(f"最適化完了: ID={optimization_id}, 最適スコア={result['best_score']}")
        
    except Exception as e:
        logger.error(f"最適化実行エラー: {str(e)}")
        
        # エラー情報をデータベースに記録
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE optimization_jobs 
            SET status = 'error', completed_at = ?
            WHERE id = ?
        """, (datetime.now(), optimization_id))
        conn.commit()
        conn.close()

async def save_optimization_result(optimization_id: int, result: Dict[str, Any]):
    """
    最適化結果をデータベースに保存
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # メイン結果を更新
        cursor.execute("""
            UPDATE optimization_jobs 
            SET status = 'completed', best_parameters = ?, best_score = ?,
                total_iterations = ?, completed_at = ?
            WHERE id = ?
        """, (
            json.dumps(result['best_parameters']),
            result['best_score'],
            result['total_iterations'],
            datetime.now(),
            optimization_id
        ))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"最適化結果保存エラー: {str(e)}")