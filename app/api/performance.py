"""
パフォーマンス監視API
詳細なシステムパフォーマンスと取引成績の監視機能を提供
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from app.core.database import get_db_connection
from app.services.performance_monitor import PerformanceMonitor

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/performance/dashboard")
async def get_performance_dashboard():
    """
    パフォーマンスダッシュボードの総合情報を取得
    """
    try:
        monitor = PerformanceMonitor()
        dashboard_data = await monitor.get_dashboard_data()
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"ダッシュボードデータ取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ダッシュボードデータ取得に失敗しました: {str(e)}")

@router.get("/performance/trading-metrics")
async def get_trading_metrics(
    period_days: int = Query(30, description="期間（日数）"),
    symbol: Optional[str] = Query(None, description="通貨ペア（省略時は全ペア）")
):
    """
    取引パフォーマンス指標を取得
    """
    try:
        monitor = PerformanceMonitor()
        metrics = await monitor.get_trading_metrics(period_days, symbol)
        
        return metrics
        
    except Exception as e:
        logger.error(f"取引指標取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引指標取得に失敗しました: {str(e)}")

@router.get("/performance/system-metrics")
async def get_system_metrics():
    """
    システムパフォーマンス指標を取得
    """
    try:
        monitor = PerformanceMonitor()
        metrics = await monitor.get_system_metrics()
        
        return metrics
        
    except Exception as e:
        logger.error(f"システム指標取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"システム指標取得に失敗しました: {str(e)}")

@router.get("/performance/equity-curve")
async def get_equity_curve(
    period_days: int = Query(30, description="期間（日数）"),
    interval: str = Query("daily", description="集計間隔（hourly, daily, weekly）")
):
    """
    エクイティカーブを取得
    """
    try:
        monitor = PerformanceMonitor()
        equity_curve = await monitor.get_equity_curve(period_days, interval)
        
        return equity_curve
        
    except Exception as e:
        logger.error(f"エクイティカーブ取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"エクイティカーブ取得に失敗しました: {str(e)}")

@router.get("/performance/drawdown-analysis")
async def get_drawdown_analysis(
    period_days: int = Query(90, description="期間（日数）")
):
    """
    ドローダウン分析を取得
    """
    try:
        monitor = PerformanceMonitor()
        analysis = await monitor.get_drawdown_analysis(period_days)
        
        return analysis
        
    except Exception as e:
        logger.error(f"ドローダウン分析取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ドローダウン分析取得に失敗しました: {str(e)}")

@router.get("/performance/risk-metrics")
async def get_risk_metrics(
    period_days: int = Query(30, description="期間（日数）")
):
    """
    リスク指標を取得
    """
    try:
        monitor = PerformanceMonitor()
        metrics = await monitor.get_risk_metrics(period_days)
        
        return metrics
        
    except Exception as e:
        logger.error(f"リスク指標取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"リスク指標取得に失敗しました: {str(e)}")

@router.get("/performance/symbol-analysis")
async def get_symbol_analysis(
    period_days: int = Query(30, description="期間（日数）")
):
    """
    通貨ペア別分析を取得
    """
    try:
        monitor = PerformanceMonitor()
        analysis = await monitor.get_symbol_analysis(period_days)
        
        return analysis
        
    except Exception as e:
        logger.error(f"通貨ペア別分析取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"通貨ペア別分析取得に失敗しました: {str(e)}")

@router.get("/performance/time-analysis")
async def get_time_analysis(
    period_days: int = Query(30, description="期間（日数）")
):
    """
    時間帯別分析を取得
    """
    try:
        monitor = PerformanceMonitor()
        analysis = await monitor.get_time_analysis(period_days)
        
        return analysis
        
    except Exception as e:
        logger.error(f"時間帯別分析取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"時間帯別分析取得に失敗しました: {str(e)}")

@router.get("/performance/signal-analysis")
async def get_signal_analysis(
    period_days: int = Query(30, description="期間（日数）")
):
    """
    シグナル分析を取得
    """
    try:
        monitor = PerformanceMonitor()
        analysis = await monitor.get_signal_analysis(period_days)
        
        return analysis
        
    except Exception as e:
        logger.error(f"シグナル分析取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"シグナル分析取得に失敗しました: {str(e)}")

@router.get("/performance/correlation-analysis")
async def get_correlation_analysis(
    period_days: int = Query(30, description="期間（日数）")
):
    """
    相関分析を取得
    """
    try:
        monitor = PerformanceMonitor()
        analysis = await monitor.get_correlation_analysis(period_days)
        
        return analysis
        
    except Exception as e:
        logger.error(f"相関分析取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"相関分析取得に失敗しました: {str(e)}")

@router.get("/performance/monthly-summary")
async def get_monthly_summary(
    months: int = Query(12, description="月数")
):
    """
    月次サマリーを取得
    """
    try:
        monitor = PerformanceMonitor()
        summary = await monitor.get_monthly_summary(months)
        
        return summary
        
    except Exception as e:
        logger.error(f"月次サマリー取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"月次サマリー取得に失敗しました: {str(e)}")

@router.get("/performance/live-metrics")
async def get_live_metrics():
    """
    リアルタイムパフォーマンス指標を取得
    """
    try:
        monitor = PerformanceMonitor()
        metrics = await monitor.get_live_metrics()
        
        return metrics
        
    except Exception as e:
        logger.error(f"ライブ指標取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ライブ指標取得に失敗しました: {str(e)}")

@router.get("/performance/benchmark-comparison")
async def get_benchmark_comparison(
    period_days: int = Query(30, description="期間（日数）"),
    benchmark: str = Query("USDJPY", description="ベンチマーク（通貨ペア）")
):
    """
    ベンチマーク比較を取得
    """
    try:
        monitor = PerformanceMonitor()
        comparison = await monitor.get_benchmark_comparison(period_days, benchmark)
        
        return comparison
        
    except Exception as e:
        logger.error(f"ベンチマーク比較取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ベンチマーク比較取得に失敗しました: {str(e)}")

@router.post("/performance/generate-report")
async def generate_performance_report(
    period_days: int = Query(30, description="期間（日数）"),
    report_type: str = Query("comprehensive", description="レポートタイプ")
):
    """
    パフォーマンスレポートを生成
    """
    try:
        monitor = PerformanceMonitor()
        report = await monitor.generate_performance_report(period_days, report_type)
        
        return {
            "report_id": report["id"],
            "status": "generated",
            "message": "パフォーマンスレポートが生成されました",
            "report": report
        }
        
    except Exception as e:
        logger.error(f"レポート生成エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"レポート生成に失敗しました: {str(e)}")

@router.get("/performance/alerts-summary")
async def get_alerts_summary():
    """
    アラート要約を取得
    """
    try:
        monitor = PerformanceMonitor()
        summary = await monitor.get_alerts_summary()
        
        return summary
        
    except Exception as e:
        logger.error(f"アラート要約取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"アラート要約取得に失敗しました: {str(e)}")