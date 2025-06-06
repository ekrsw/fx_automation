from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime
from ..models.trading import (
    OrderRequest, OrderResponse, PositionInfo, AccountInfo,
    TradeSignal, ClosePositionRequest, ModifyPositionRequest,
    RiskCalculation
)
from ..services.risk_management import risk_manager
from ..core.database import db_manager
from ..core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["trading"])

@router.post("/orders", response_model=OrderResponse)
async def create_order(order: OrderRequest):
    """
    新規注文作成
    """
    try:
        # 模擬口座情報（実際にはMT5から取得）
        mock_account = {
            'balance': 100000.0,
            'equity': 100000.0,
            'margin': 0.0,
            'free_margin': 100000.0
        }
        
        # 現在のポジション取得
        current_positions = db_manager.get_active_trades()
        
        # 取引シグナル形式に変換
        signal = {
            'symbol': order.symbol,
            'side': order.side,
            'entry_price': order.price or 0.0,  # 成行の場合は現在価格を使用
            'stop_loss': order.stop_loss or 0.0,
            'take_profit': order.take_profit or 0.0
        }
        
        # リスク検証
        validation = risk_manager.validate_trade_signal(
            signal, mock_account, current_positions
        )
        
        if not validation['valid']:
            raise HTTPException(
                status_code=400,
                detail=f"Order validation failed: {', '.join(validation['errors'])}"
            )
        
        # 注文をMT5に送信（シミュレーション）
        # 実際の実装では、MQL5のEAに注文リクエストを送信
        order_result = await send_order_to_mt5(order, validation['recommended_lot_size'])
        
        # 取引履歴をデータベースに保存
        if order_result['success']:
            await save_trade_to_database(order, order_result)
        
        logger.info(f"Order created: {order.symbol} {order.side} {order.quantity} lots")
        return order_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Order creation failed: {str(e)}")

@router.get("/positions", response_model=List[PositionInfo])
async def get_positions():
    """
    現在のポジション一覧取得
    """
    try:
        # データベースからアクティブなトレード取得
        active_trades = db_manager.get_active_trades()
        
        # MT5から最新のポジション情報取得（シミュレーション）
        positions = []
        for trade in active_trades:
            position = PositionInfo(
                ticket=trade['id'],
                symbol=trade['symbol'],
                side=trade['side'],
                volume=trade['quantity'],
                entry_price=trade['entry_price'],
                current_price=trade['entry_price'],  # 実際にはMT5から現在価格取得
                stop_loss=trade.get('stop_loss'),
                take_profit=trade.get('take_profit'),
                profit=0.0,  # 実際にはMT5から損益計算
                swap=0.0,
                comment=f"FX Trading System",
                open_time=trade['entry_time']
            )
            positions.append(position)
        
        return positions
        
    except Exception as e:
        logger.error(f"Error getting positions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get positions: {str(e)}")

@router.post("/positions/{ticket}/close")
async def close_position(ticket: int, request: ClosePositionRequest):
    """
    ポジションクローズ
    """
    try:
        # ポジション存在確認
        positions = db_manager.get_active_trades()
        target_position = next((pos for pos in positions if pos['id'] == ticket), None)
        
        if not target_position:
            raise HTTPException(status_code=404, detail=f"Position {ticket} not found")
        
        # MT5でポジションクローズ（シミュレーション）
        close_result = await close_position_in_mt5(ticket, request.volume)
        
        if close_result['success']:
            # データベースの取引ステータス更新
            await update_trade_status(ticket, 'closed', close_result.get('exit_price'))
            logger.info(f"Position {ticket} closed successfully")
        
        return close_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing position {ticket}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to close position: {str(e)}")

@router.put("/positions/{ticket}/modify")
async def modify_position(ticket: int, request: ModifyPositionRequest):
    """
    ポジション修正（SL/TP変更）
    """
    try:
        # ポジション存在確認
        positions = db_manager.get_active_trades()
        target_position = next((pos for pos in positions if pos['id'] == ticket), None)
        
        if not target_position:
            raise HTTPException(status_code=404, detail=f"Position {ticket} not found")
        
        # MT5でポジション修正（シミュレーション）
        modify_result = await modify_position_in_mt5(ticket, request)
        
        return modify_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error modifying position {ticket}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to modify position: {str(e)}")

@router.get("/account", response_model=AccountInfo)
async def get_account_info():
    """
    口座情報取得
    """
    try:
        # MT5から口座情報取得（シミュレーション）
        account_info = AccountInfo(
            balance=100000.0,
            equity=100000.0,
            margin=0.0,
            free_margin=100000.0,
            margin_level=0.0,
            profit=0.0,
            currency="USD"
        )
        
        return account_info
        
    except Exception as e:
        logger.error(f"Error getting account info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get account info: {str(e)}")

@router.post("/risk/calculate", response_model=RiskCalculation)
async def calculate_risk(
    symbol: str,
    entry_price: float,
    stop_loss: float,
    account_balance: float = 100000.0,
    risk_percentage: float = 0.02
):
    """
    リスク計算
    """
    try:
        calculation = risk_manager.calculate_position_size(
            symbol, entry_price, stop_loss, account_balance, risk_percentage
        )
        
        if 'error' in calculation:
            raise HTTPException(status_code=400, detail=calculation['error'])
        
        return RiskCalculation(**calculation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating risk: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Risk calculation failed: {str(e)}")

@router.get("/signals/validate")
async def validate_signal(
    symbol: str,
    side: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float
):
    """
    シグナル検証
    """
    try:
        # 模擬口座情報
        mock_account = {
            'balance': 100000.0,
            'equity': 100000.0,
            'margin': 0.0,
            'free_margin': 100000.0
        }
        
        signal = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
        
        current_positions = db_manager.get_active_trades()
        validation = risk_manager.validate_trade_signal(signal, mock_account, current_positions)
        
        return {
            'valid': validation['valid'],
            'errors': validation['errors'],
            'warnings': validation['warnings'],
            'recommended_lot_size': validation['recommended_lot_size'],
            'risk_analysis': validation.get('risk_analysis', {}),
            'drawdown_info': validation.get('drawdown_info', {})
        }
        
    except Exception as e:
        logger.error(f"Error validating signal: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Signal validation failed: {str(e)}")

# MT5連携関数（シミュレーション）
async def send_order_to_mt5(order: OrderRequest, lot_size: float) -> OrderResponse:
    """MT5に注文送信（シミュレーション）"""
    # 実際の実装では、MQL5のEAにHTTPリクエストを送信
    return OrderResponse(
        success=True,
        message="Order executed successfully",
        order_id=12345,
        ticket=67890,
        entry_price=150.123,  # 実際にはMT5から取得
        timestamp=datetime.now().isoformat()
    )

async def close_position_in_mt5(ticket: int, volume: Optional[float]) -> dict:
    """MT5でポジションクローズ（シミュレーション）"""
    return {
        'success': True,
        'message': 'Position closed successfully',
        'ticket': ticket,
        'exit_price': 150.456,
        'timestamp': datetime.now().isoformat()
    }

async def modify_position_in_mt5(ticket: int, request: ModifyPositionRequest) -> dict:
    """MT5でポジション修正（シミュレーション）"""
    return {
        'success': True,
        'message': 'Position modified successfully',
        'ticket': ticket,
        'stop_loss': request.stop_loss,
        'take_profit': request.take_profit,
        'timestamp': datetime.now().isoformat()
    }

async def save_trade_to_database(order: OrderRequest, result: OrderResponse):
    """取引をデータベースに保存"""
    # 実際の実装では、データベースに取引情報を保存
    pass

async def update_trade_status(ticket: int, status: str, exit_price: Optional[float] = None):
    """取引ステータス更新"""
    # 実際の実装では、データベースの取引ステータスを更新
    pass