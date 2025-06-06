from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime
from ..services.technical_analysis import technical_analysis_service
from ..core.database import db_manager
from ..core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["analysis"])

@router.get("/analysis/{symbol}")
async def analyze_symbol(
    symbol: str,
    limit: int = Query(default=100, ge=50, le=500, description="Number of data points to analyze")
):
    """
    指定通貨ペアのテクニカル分析実行
    """
    try:
        # 市場データ取得
        market_data = db_manager.get_latest_market_data(symbol, limit)
        
        if not market_data:
            raise HTTPException(
                status_code=404, 
                detail=f"No market data found for symbol: {symbol}"
            )
        
        # テクニカル分析実行
        analysis_result = technical_analysis_service.analyze_market_data(market_data)
        
        if 'error' in analysis_result:
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {analysis_result['error']}"
            )
        
        logger.info(f"Technical analysis completed for {symbol}")
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")

@router.get("/swing-points/{symbol}")
async def get_swing_points(
    symbol: str,
    limit: int = Query(default=100, ge=50, le=500)
):
    """
    スイングポイント取得
    """
    try:
        market_data = db_manager.get_latest_market_data(symbol, limit)
        
        if not market_data:
            raise HTTPException(
                status_code=404,
                detail=f"No market data found for symbol: {symbol}"
            )
        
        analysis_result = technical_analysis_service.analyze_market_data(market_data)
        
        if 'error' in analysis_result:
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {analysis_result['error']}"
            )
        
        return {
            "symbol": symbol,
            "swing_points": analysis_result.get("swing_points", []),
            "count": analysis_result.get("swing_points_count", 0),
            "trend_analysis": analysis_result.get("trend_analysis", {}),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting swing points for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Swing points error: {str(e)}")

@router.get("/zigzag/{symbol}")
async def get_zigzag(
    symbol: str,
    limit: int = Query(default=100, ge=50, le=500),
    deviation: Optional[float] = Query(default=0.1, ge=0.05, le=1.0, description="ZigZag deviation percentage")
):
    """
    ZigZagインジケータ取得
    """
    try:
        market_data = db_manager.get_latest_market_data(symbol, limit)
        
        if not market_data:
            raise HTTPException(
                status_code=404,
                detail=f"No market data found for symbol: {symbol}"
            )
        
        # カスタム偏差でZigZag計算
        if deviation != 0.1:
            from ..services.technical_analysis import ZigZagIndicator
            import pandas as pd
            
            zigzag = ZigZagIndicator(deviation=deviation)
            df = pd.DataFrame(market_data)
            zigzag_points = zigzag.calculate(df)
        else:
            analysis_result = technical_analysis_service.analyze_market_data(market_data)
            if 'error' in analysis_result:
                raise HTTPException(
                    status_code=500,
                    detail=f"Analysis failed: {analysis_result['error']}"
                )
            zigzag_points = analysis_result.get("zigzag_points", [])
        
        return {
            "symbol": symbol,
            "zigzag_points": zigzag_points,
            "count": len(zigzag_points),
            "deviation": deviation,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ZigZag for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ZigZag error: {str(e)}")

@router.get("/trend/{symbol}")
async def get_trend_analysis(
    symbol: str,
    limit: int = Query(default=100, ge=50, le=500)
):
    """
    トレンド分析取得
    """
    try:
        market_data = db_manager.get_latest_market_data(symbol, limit)
        
        if not market_data:
            raise HTTPException(
                status_code=404,
                detail=f"No market data found for symbol: {symbol}"
            )
        
        analysis_result = technical_analysis_service.analyze_market_data(market_data)
        
        if 'error' in analysis_result:
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {analysis_result['error']}"
            )
        
        trend_analysis = analysis_result.get("trend_analysis", {})
        
        return {
            "symbol": symbol,
            "trend": trend_analysis.get("trend", "unknown"),
            "strength": trend_analysis.get("strength", 0),
            "details": {
                "higher_highs": trend_analysis.get("higher_highs", 0),
                "lower_highs": trend_analysis.get("lower_highs", 0),
                "higher_lows": trend_analysis.get("higher_lows", 0),
                "lower_lows": trend_analysis.get("lower_lows", 0),
                "analysis": trend_analysis.get("analysis", "")
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trend analysis for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Trend analysis error: {str(e)}")