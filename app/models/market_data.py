from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class OHLCData(BaseModel):
    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class MarketDataRequest(BaseModel):
    symbol: str
    data: List[OHLCData]

class Signal(BaseModel):
    symbol: str
    signal_type: str = Field(..., description="buy, sell, or neutral")
    score: int = Field(..., ge=0, le=100, description="Signal strength score (0-100)")
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: str
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    
class SignalResponse(BaseModel):
    signals: List[Signal]
    timestamp: str
    total_count: int

class Trade(BaseModel):
    id: Optional[int] = None
    symbol: str
    side: str = Field(..., description="buy or sell")
    entry_price: float
    exit_price: Optional[float] = None
    quantity: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    profit_loss: float = 0.0
    status: str = "open"
    entry_time: str
    exit_time: Optional[str] = None

class SystemStatus(BaseModel):
    status: str
    timestamp: str
    service: str
    version: str
    active_trades: int = 0
    monitored_pairs: List[str]
    last_update: Optional[str] = None