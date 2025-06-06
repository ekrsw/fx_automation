from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"

class TradeStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"

class OrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    quantity: float = Field(..., gt=0, description="Position size in lots")
    order_type: OrderType = OrderType.MARKET
    price: Optional[float] = Field(None, description="Price for limit/stop orders")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    comment: Optional[str] = Field(None, max_length=100)

class OrderResponse(BaseModel):
    success: bool
    message: str
    order_id: Optional[int] = None
    ticket: Optional[int] = None
    entry_price: Optional[float] = None
    timestamp: str

class PositionInfo(BaseModel):
    ticket: int
    symbol: str
    side: OrderSide
    volume: float
    entry_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    profit: float
    swap: float = 0.0
    comment: Optional[str] = None
    open_time: str

class AccountInfo(BaseModel):
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    profit: float
    currency: str = "USD"

class RiskCalculation(BaseModel):
    symbol: str
    entry_price: float
    stop_loss: float
    risk_amount: float
    risk_percentage: float = Field(..., le=0.1, description="Max 10% risk")
    calculated_lot_size: float
    pip_value: float
    stop_loss_pips: float

class TradeSignal(BaseModel):
    symbol: str
    side: OrderSide
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    confidence: float = Field(..., ge=0.0, le=1.0)
    signal_source: str = Field(..., description="dow_theory, elliott_wave, etc.")
    timestamp: str
    
class ClosePositionRequest(BaseModel):
    ticket: int
    volume: Optional[float] = Field(None, description="Partial close volume. If None, close all")
    
class ModifyPositionRequest(BaseModel):
    ticket: int
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None