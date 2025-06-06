from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta
from ..core.database import db_manager
from ..core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["reports"])

@router.get("/trading-summary")
async def get_trading_summary(days: int = Query(default=30, ge=1, le=365)):
    """
    取引サマリー取得
    """
    try:
        summary = db_manager.get_trading_summary(days)
        
        # 空の場合はデフォルト値を設定
        if not summary or summary.get('total_trades', 0) == 0:
            summary = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_profit': 0.0,
                'avg_profit': 0.0,
                'max_profit': 0.0,
                'max_loss': 0.0,
                'win_rate': 0.0
            }
        
        # 追加指標の計算
        if summary['winning_trades'] > 0 and summary['losing_trades'] > 0:
            # プロフィットファクター計算
            total_wins = summary.get('total_profit', 0) if summary.get('total_profit', 0) > 0 else 0
            total_losses = abs(summary.get('max_loss', 0)) * summary.get('losing_trades', 0)
            
            if total_losses > 0:
                summary['profit_factor'] = total_wins / total_losses
            else:
                summary['profit_factor'] = 0.0
        else:
            summary['profit_factor'] = 0.0
        
        # リスクリワード比率
        if summary.get('max_loss', 0) != 0:
            summary['risk_reward_ratio'] = abs(summary.get('max_profit', 0) / summary.get('max_loss', 1))
        else:
            summary['risk_reward_ratio'] = 0.0
        
        return {
            'period_days': days,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting trading summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get trading summary: {str(e)}")

@router.get("/trade-history")
async def get_trade_history(
    status: Optional[str] = Query(None, description="open, closed, cancelled"),
    symbol: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000)
):
    """
    取引履歴取得
    """
    try:
        if status:
            trades = db_manager.get_trades_by_status(status)
        else:
            # 全ての取引を取得（簡易実装）
            trades = db_manager.get_trades_by_status('open') + db_manager.get_trades_by_status('closed')
        
        # シンボルフィルター
        if symbol:
            trades = [trade for trade in trades if trade.get('symbol') == symbol]
        
        # 制限適用
        trades = trades[:limit]
        
        return {
            'trades': trades,
            'count': len(trades),
            'filters': {
                'status': status,
                'symbol': symbol,
                'limit': limit
            },
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting trade history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get trade history: {str(e)}")

@router.get("/performance-metrics")
async def get_performance_metrics(days: int = Query(default=30, ge=1, le=365)):
    """
    パフォーマンス指標取得
    """
    try:
        summary = db_manager.get_trading_summary(days)
        
        if not summary or summary.get('total_trades', 0) == 0:
            return {
                'period_days': days,
                'metrics': {
                    'total_return': 0.0,
                    'win_rate': 0.0,
                    'profit_factor': 0.0,
                    'max_drawdown': 0.0,
                    'sharpe_ratio': 0.0,
                    'total_trades': 0
                },
                'message': 'No trades found for the specified period',
                'timestamp': datetime.now().isoformat()
            }
        
        # パフォーマンス指標計算
        metrics = {
            'total_return': summary.get('total_profit', 0.0),
            'win_rate': summary.get('win_rate', 0.0),
            'profit_factor': summary.get('profit_factor', 0.0),
            'max_drawdown': 0.0,  # 実装要：ドローダウン履歴から計算
            'sharpe_ratio': 0.0,  # 実装要：リターンの標準偏差から計算
            'total_trades': summary.get('total_trades', 0),
            'average_profit': summary.get('avg_profit', 0.0),
            'best_trade': summary.get('max_profit', 0.0),
            'worst_trade': summary.get('max_loss', 0.0)
        }
        
        return {
            'period_days': days,
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")

@router.get("/risk-exposure")
async def get_risk_exposure():
    """
    現在のリスクエクスポージャー取得
    """
    try:
        active_trades = db_manager.get_active_trades()
        
        if not active_trades:
            return {
                'total_exposure': 0.0,
                'positions': [],
                'risk_summary': {
                    'total_positions': 0,
                    'total_lot_size': 0.0,
                    'symbols': []
                },
                'timestamp': datetime.now().isoformat()
            }
        
        # エクスポージャー計算
        total_exposure = 0.0
        total_lot_size = 0.0
        symbols = set()
        
        position_details = []
        
        for trade in active_trades:
            lot_size = trade.get('quantity', 0.0)
            entry_price = trade.get('entry_price', 0.0)
            symbol = trade.get('symbol', '')
            
            exposure = lot_size * entry_price * 100000  # 標準ロットサイズ仮定
            total_exposure += exposure
            total_lot_size += lot_size
            symbols.add(symbol)
            
            position_details.append({
                'id': trade.get('id'),
                'symbol': symbol,
                'side': trade.get('side'),
                'lot_size': lot_size,
                'entry_price': entry_price,
                'exposure': exposure,
                'stop_loss': trade.get('stop_loss'),
                'take_profit': trade.get('take_profit')
            })
        
        return {
            'total_exposure': total_exposure,
            'positions': position_details,
            'risk_summary': {
                'total_positions': len(active_trades),
                'total_lot_size': total_lot_size,
                'symbols': list(symbols)
            },
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting risk exposure: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get risk exposure: {str(e)}")

@router.get("/daily-pnl")
async def get_daily_pnl(days: int = Query(default=30, ge=1, le=365)):
    """
    日次損益取得
    """
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        # 簡易実装：取引履歴から日次損益を計算
        closed_trades = db_manager.get_trades_by_status('closed')
        
        # 日付別の損益を集計
        daily_pnl = {}
        
        for trade in closed_trades:
            exit_time = trade.get('exit_time')
            if not exit_time:
                continue
                
            try:
                trade_date = datetime.fromisoformat(exit_time).date()
                if trade_date >= start_date.date():
                    date_str = trade_date.isoformat()
                    if date_str not in daily_pnl:
                        daily_pnl[date_str] = 0.0
                    daily_pnl[date_str] += trade.get('profit_loss', 0.0)
            except ValueError:
                continue
        
        # 日付順でソート
        sorted_pnl = sorted(daily_pnl.items())
        
        return {
            'period_days': days,
            'daily_pnl': [
                {
                    'date': date,
                    'pnl': pnl,
                    'cumulative_pnl': sum(item[1] for item in sorted_pnl[:i+1])
                }
                for i, (date, pnl) in enumerate(sorted_pnl)
            ],
            'total_pnl': sum(daily_pnl.values()),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting daily PnL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get daily PnL: {str(e)}")