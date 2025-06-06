from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime
from ..models.market_data import (
    MarketDataRequest, OHLCData, Signal, SignalResponse, 
    Trade, SystemStatus
)
from ..core.database import db_manager
from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["market_data"])

@router.post("/market-data")
async def receive_market_data(request: MarketDataRequest):
    try:
        for data in request.data:
            db_manager.insert_market_data(
                symbol=data.symbol,
                timestamp=data.timestamp,
                open_price=data.open,
                high=data.high,
                low=data.low,
                close=data.close,
                volume=data.volume
            )
        
        logger.info(f"Received market data for {request.symbol}: {len(request.data)} records")
        return {"status": "success", "records_processed": len(request.data)}
    
    except Exception as e:
        logger.error(f"Error processing market data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing market data: {str(e)}")

@router.get("/market-data/{symbol}")
async def get_market_data(symbol: str, limit: int = 100):
    try:
        data = db_manager.get_latest_market_data(symbol, limit)
        return {"symbol": symbol, "data": data, "count": len(data)}
    
    except Exception as e:
        logger.error(f"Error retrieving market data for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving market data: {str(e)}")

@router.get("/signals", response_model=SignalResponse)
async def get_signals(symbol: Optional[str] = None):
    try:
        # TODO: Implement signal generation logic
        # This is a placeholder that returns empty signals
        signals = []
        
        return SignalResponse(
            signals=signals,
            timestamp=datetime.now().isoformat(),
            total_count=len(signals)
        )
    
    except Exception as e:
        logger.error(f"Error retrieving signals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving signals: {str(e)}")

@router.get("/trades")
async def get_active_trades():
    try:
        trades = db_manager.get_active_trades()
        return {"trades": trades, "count": len(trades)}
    
    except Exception as e:
        logger.error(f"Error retrieving trades: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving trades: {str(e)}")

@router.get("/system-status", response_model=SystemStatus)
async def get_system_status():
    try:
        active_trades = db_manager.get_active_trades()
        
        return SystemStatus(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            service=settings.PROJECT_NAME,
            version=settings.VERSION,
            active_trades=len(active_trades),
            monitored_pairs=settings.CURRENCY_PAIRS,
            last_update=datetime.now().isoformat()
        )
    
    except Exception as e:
        logger.error(f"Error retrieving system status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving system status: {str(e)}")