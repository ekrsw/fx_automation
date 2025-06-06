from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from datetime import datetime
from ..services.signal_orchestrator import (
    signal_orchestrator, TradingSignal, SignalType, SignalSource, SignalPriority
)
from ..services.multi_pair_manager import multi_pair_manager
from ..core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["signals"])

@router.get("/signals/active")
async def get_active_signals():
    """
    アクティブシグナル取得
    """
    try:
        active_signals = signal_orchestrator.active_signals
        prioritized_signals = signal_orchestrator.get_prioritized_signals()
        
        return {
            'active_signals': [signal.to_dict() for signal in active_signals],
            'prioritized_signals': [signal.to_dict() for signal in prioritized_signals],
            'total_active': len(active_signals),
            'qualified_count': len(prioritized_signals),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting active signals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get active signals: {str(e)}")

@router.post("/signals/generate")
async def generate_signals(background_tasks: BackgroundTasks):
    """
    マルチペアシグナル生成と統合
    """
    try:
        # マルチペア分析実行
        multi_pair_result = multi_pair_manager.generate_multi_pair_signals()
        
        if 'error' in multi_pair_result:
            raise HTTPException(status_code=500, detail=multi_pair_result['error'])
        
        generated_signals = []
        
        # 新規エントリーシグナル生成
        for pair in multi_pair_result.get('selected_pairs', []):
            signal_id = f"entry_{pair['symbol']}_{int(datetime.now().timestamp())}"
            
            signal = TradingSignal(
                signal_id=signal_id,
                symbol=pair['symbol'],
                signal_type=SignalType.ENTRY,
                signal_source=SignalSource.MULTI_PAIR,
                priority=SignalPriority.HIGH if pair['score'] >= 80 else SignalPriority.MEDIUM,
                confidence=pair['score'] / 100.0,
                data={
                    'score': pair['score'],
                    'recommendation': pair['recommendation'],
                    'score_details': pair.get('score_details', {})
                }
            )
            
            if signal_orchestrator.add_signal(signal):
                generated_signals.append(signal.to_dict())
        
        # ポジション入替シグナル生成
        for replacement in multi_pair_result.get('replacement_recommendations', []):
            signal_id = f"replace_{replacement['open_position']['symbol']}_{int(datetime.now().timestamp())}"
            
            signal = TradingSignal(
                signal_id=signal_id,
                symbol=replacement['open_position']['symbol'],
                signal_type=SignalType.REPLACE,
                signal_source=SignalSource.MULTI_PAIR,
                priority=SignalPriority.HIGH,
                confidence=0.8,
                data={
                    'close_symbol': replacement['close_position']['symbol'],
                    'open_symbol': replacement['open_position']['symbol'],
                    'score_improvement': replacement['score_improvement']
                }
            )
            
            if signal_orchestrator.add_signal(signal):
                generated_signals.append(signal.to_dict())
        
        return {
            'generated_signals': generated_signals,
            'signal_count': len(generated_signals),
            'multi_pair_summary': multi_pair_result.get('summary', {}),
            'timestamp': datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating signals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Signal generation error: {str(e)}")

@router.post("/signals/process")
async def process_signals(background_tasks: BackgroundTasks):
    """
    シグナル処理実行
    """
    try:
        # バックグラウンドでシグナル処理実行
        background_tasks.add_task(execute_signal_processing)
        
        # 現在のシグナル状況を返す
        prioritized_signals = signal_orchestrator.get_prioritized_signals()
        
        return {
            'message': 'Signal processing started in background',
            'signals_to_process': len(prioritized_signals),
            'processing_queue': [signal.to_dict() for signal in prioritized_signals[:5]],  # 上位5件
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting signal processing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Signal processing error: {str(e)}")

async def execute_signal_processing():
    """シグナル処理実行（バックグラウンド）"""
    try:
        result = await signal_orchestrator.process_signals()
        logger.info(f"Signal processing completed: {result}")
    except Exception as e:
        logger.error(f"Background signal processing error: {str(e)}")

@router.post("/signals/manual")
async def add_manual_signal(
    symbol: str,
    signal_type: str,
    signal_source: str,
    priority: str,
    confidence: float,
    data: dict
):
    """
    手動シグナル追加
    """
    try:
        # Enum変換
        try:
            sig_type = SignalType(signal_type)
            sig_source = SignalSource(signal_source)
            sig_priority = SignalPriority[priority.upper()]
        except (ValueError, KeyError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid enum value: {str(e)}")
        
        # 信頼度チェック
        if not 0.0 <= confidence <= 1.0:
            raise HTTPException(status_code=400, detail="Confidence must be between 0.0 and 1.0")
        
        # シグナル作成
        signal_id = f"manual_{symbol}_{signal_type}_{int(datetime.now().timestamp())}"
        
        signal = TradingSignal(
            signal_id=signal_id,
            symbol=symbol,
            signal_type=sig_type,
            signal_source=sig_source,
            priority=sig_priority,
            confidence=confidence,
            data=data
        )
        
        # シグナル追加
        if signal_orchestrator.add_signal(signal):
            logger.info(f"Manual signal added: {signal_id}")
            return {
                'success': True,
                'signal': signal.to_dict(),
                'message': 'Manual signal added successfully'
            }
        else:
            return {
                'success': False,
                'message': 'Signal was not added (possibly duplicate or lower priority)'
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding manual signal: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Manual signal error: {str(e)}")

@router.delete("/signals/{signal_id}")
async def remove_signal(signal_id: str):
    """
    シグナル削除
    """
    try:
        if signal_orchestrator.remove_signal(signal_id):
            return {
                'success': True,
                'message': f'Signal {signal_id} removed successfully'
            }
        else:
            raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing signal: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Signal removal error: {str(e)}")

@router.get("/signals/statistics")
async def get_signal_statistics():
    """
    シグナル統計取得
    """
    try:
        stats = signal_orchestrator.get_signal_statistics()
        
        if 'error' in stats:
            raise HTTPException(status_code=500, detail=stats['error'])
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting signal statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Statistics error: {str(e)}")

@router.post("/signals/cleanup")
async def cleanup_signals(max_age_hours: int = 24):
    """
    古いシグナルのクリーンアップ
    """
    try:
        signal_orchestrator.cleanup_old_signals(max_age_hours)
        
        return {
            'success': True,
            'message': f'Signals older than {max_age_hours} hours cleaned up',
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up signals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup error: {str(e)}")

@router.get("/signals/config")
async def get_signal_config():
    """
    シグナル設定取得
    """
    try:
        return {
            'signal_types': [t.value for t in SignalType],
            'signal_sources': [s.value for s in SignalSource],
            'signal_priorities': [p.name for p in SignalPriority],
            'source_weights': {s.value: w for s, w in signal_orchestrator.source_weights.items()},
            'min_confidence': signal_orchestrator.min_confidence,
            'min_composite_score': signal_orchestrator.min_composite_score,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting signal config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Config error: {str(e)}")

@router.get("/signals/health")
async def check_signal_health():
    """
    シグナルシステムヘルスチェック
    """
    try:
        active_count = len(signal_orchestrator.active_signals)
        history_count = len(signal_orchestrator.signal_history)
        
        # ヘルス判定
        health_status = "healthy"
        issues = []
        
        if active_count > 50:
            health_status = "warning"
            issues.append("Too many active signals")
        
        if history_count > 1000:
            health_status = "warning"
            issues.append("Signal history growing large")
        
        # 古いシグナルチェック
        old_signals = [
            s for s in signal_orchestrator.active_signals
            if (datetime.now() - s.timestamp).total_seconds() > 3600  # 1時間以上
        ]
        
        if old_signals:
            health_status = "warning"
            issues.append(f"{len(old_signals)} signals are older than 1 hour")
        
        return {
            'status': health_status,
            'active_signals': active_count,
            'signal_history': history_count,
            'issues': issues,
            'recommendations': [
                'Run cleanup if signal count is high',
                'Check signal processing frequency',
                'Monitor signal generation rate'
            ] if issues else [],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking signal health: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check error: {str(e)}")