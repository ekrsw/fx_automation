"""
強化されたシグナル生成API
100点満点のスコアリングシステムとエリオット波動分析
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
import logging

from ..services.enhanced_signal_generator import enhanced_signal_generator
from ..services.elliott_wave_analyzer import elliott_wave_analyzer
from ..core.database import db_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/enhanced-signals", tags=["Enhanced Signals"])

@router.get("/comprehensive/{symbol}")
async def get_comprehensive_signal(
    symbol: str,
    timeframe: str = Query("H4", description="Primary timeframe for analysis"),
    min_score: float = Query(60.0, description="Minimum score threshold")
) -> Dict:
    """
    包括的なシグナル分析を実行
    
    Args:
        symbol: 通貨ペア (e.g., USDJPY, EURUSD)
        timeframe: メイン分析時間軸 (M5, M15, H1, H4, D1)
        min_score: 最小スコア閾値
        
    Returns:
        100点満点のスコアと詳細分析結果
    """
    try:
        # 市場データの存在確認
        market_data = db_manager.get_latest_market_data(symbol, 100)
        if not market_data:
            raise HTTPException(
                status_code=404,
                detail=f"No market data found for {symbol}"
            )
        
        # 包括的なシグナル生成
        result = enhanced_signal_generator.generate_comprehensive_signal(
            symbol=symbol.upper(),
            primary_timeframe=timeframe
        )
        
        if 'error' in result:
            raise HTTPException(
                status_code=500,
                detail=f"Signal generation failed: {result['error']}"
            )
        
        # スコア閾値フィルタリング
        if result.get('score', 0) < min_score:
            result['filtered'] = True
            result['filter_reason'] = f"Score {result['score']} below threshold {min_score}"
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating comprehensive signal for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/elliott-wave/{symbol}")
async def get_elliott_wave_analysis(
    symbol: str,
    data_points: int = Query(200, description="Number of data points to analyze")
) -> Dict:
    """
    エリオット波動分析を実行
    
    Args:
        symbol: 通貨ペア
        data_points: 分析するデータポイント数
        
    Returns:
        エリオット波動パターンと現在位置
    """
    try:
        # 市場データ取得
        market_data = db_manager.get_latest_market_data(symbol, data_points)
        if not market_data:
            raise HTTPException(
                status_code=404,
                detail=f"No market data found for {symbol}"
            )
        
        # テクニカル分析でZigZagを計算
        from ..services.technical_analysis import technical_analysis_service
        analysis = technical_analysis_service.analyze_market_data(market_data)
        
        if 'error' in analysis:
            raise HTTPException(
                status_code=500,
                detail=f"Technical analysis failed: {analysis['error']}"
            )
        
        zigzag_points = analysis.get('zigzag_points', [])
        
        if len(zigzag_points) < 5:
            return {
                'symbol': symbol,
                'warning': 'Insufficient ZigZag points for Elliott Wave analysis',
                'zigzag_points_count': len(zigzag_points),
                'wave_patterns': [],
                'current_position': None
            }
        
        # エリオット波動パターン検出
        wave_patterns = elliott_wave_analyzer.detect_elliott_waves(zigzag_points)
        current_position = elliott_wave_analyzer.get_current_wave_position(wave_patterns)
        
        # フィボナッチ計算
        fibonacci_data = {}
        if len(zigzag_points) >= 3:
            recent_points = zigzag_points[-3:]
            high = max(point['price'] for point in recent_points)
            low = min(point['price'] for point in recent_points)
            
            fibonacci_data = {
                'retracements': elliott_wave_analyzer.calculate_fibonacci_retracements(high, low),
                'high': high,
                'low': low
            }
        
        return {
            'symbol': symbol,
            'data_points_analyzed': len(market_data),
            'zigzag_points_count': len(zigzag_points),
            'wave_patterns_count': len(wave_patterns),
            'wave_patterns': [
                {
                    'wave_type': pattern.wave_type,
                    'confidence': pattern.confidence,
                    'start_price': pattern.start_price,
                    'end_price': pattern.end_price,
                    'fibonacci_ratios': pattern.fibonacci_ratios
                }
                for pattern in wave_patterns
            ],
            'current_position': current_position,
            'fibonacci_analysis': fibonacci_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Elliott Wave analysis for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/score-breakdown/{symbol}")
async def get_score_breakdown(
    symbol: str,
    timeframe: str = Query("H4", description="Analysis timeframe")
) -> Dict:
    """
    スコア内訳の詳細分析
    
    Args:
        symbol: 通貨ペア
        timeframe: 分析時間軸
        
    Returns:
        100点満点スコアの詳細内訳
    """
    try:
        # 包括的なシグナル生成
        result = enhanced_signal_generator.generate_comprehensive_signal(
            symbol=symbol.upper(),
            primary_timeframe=timeframe
        )
        
        if 'error' in result:
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {result['error']}"
            )
        
        score_breakdown = result.get('score_breakdown', {})
        
        # スコア詳細の説明を追加
        score_explanations = {
            'trend_strength': {
                'max_points': 30,
                'description': 'ダウ理論による連続的高値・安値更新と複数時間軸一致性',
                'components': [
                    'Higher highs & higher lows count (max 15 points)',
                    'Swing point angles (max 10 points)', 
                    'Multi-timeframe trend alignment (max 5 points)'
                ]
            },
            'elliott_wave': {
                'max_points': 40,
                'description': 'エリオット波動位置とフィボナッチ比率適合度',
                'scoring': {
                    'Wave 3': '40 points (strongest impulse wave)',
                    'Wave 1': '30 points (trend initiation)',
                    'Wave 5': '20 points (trend completion)',
                    'Corrective waves': '5-15 points'
                }
            },
            'technical_accuracy': {
                'max_points': 20,
                'description': 'フィボナッチ比率適合度と複数時間軸技術的一致性',
                'components': [
                    'Fibonacci ratio matching (max 10 points)',
                    'Multi-timeframe technical alignment (max 10 points)'
                ]
            },
            'market_environment': {
                'max_points': 10,
                'description': 'ボラティリティ適正性と流動性時間帯',
                'components': [
                    'Volatility appropriateness (max 5 points)',
                    'Trading session liquidity (max 5 points)'
                ]
            }
        }
        
        # 現在のスコアと説明を組み合わせ
        detailed_breakdown = {}
        for component, score in score_breakdown.items():
            if component != 'total_score':
                detailed_breakdown[component] = {
                    'current_score': score,
                    'explanation': score_explanations.get(component, {})
                }
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'total_score': score_breakdown.get('total_score', 0),
            'grade': _get_score_grade(score_breakdown.get('total_score', 0)),
            'detailed_breakdown': detailed_breakdown,
            'recommendation': result.get('recommendation', ''),
            'signal_strength': result.get('signal', {}).get('strength', 'weak')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting score breakdown for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/market-scan")
async def scan_all_markets(
    min_score: float = Query(60.0, description="Minimum score to include in results"),
    timeframe: str = Query("H4", description="Analysis timeframe"),
    limit: int = Query(10, description="Maximum number of results")
) -> Dict:
    """
    全通貨ペアのスキャン
    
    Args:
        min_score: 最小スコア閾値
        timeframe: 分析時間軸
        limit: 最大結果数
        
    Returns:
        高スコア通貨ペアのランキング
    """
    try:
        # 監視対象通貨ペア
        currency_pairs = ['USDJPY', 'EURUSD', 'GBPUSD', 'AUDUSD', 'USDCHF', 'USDCAD']
        
        results = []
        
        for symbol in currency_pairs:
            try:
                # 市場データの存在確認
                market_data = db_manager.get_latest_market_data(symbol, 50)
                if not market_data:
                    continue
                
                # シグナル生成
                signal_result = enhanced_signal_generator.generate_comprehensive_signal(
                    symbol=symbol,
                    primary_timeframe=timeframe
                )
                
                if 'error' not in signal_result:
                    score = signal_result.get('score', 0)
                    if score >= min_score:
                        results.append({
                            'symbol': symbol,
                            'score': score,
                            'signal': signal_result.get('signal', {}).get('action', 'hold'),
                            'confidence': signal_result.get('signal', {}).get('confidence', 0),
                            'recommendation': signal_result.get('recommendation', ''),
                            'score_breakdown': signal_result.get('score_breakdown', {})
                        })
                        
            except Exception as e:
                logger.warning(f"Error analyzing {symbol}: {str(e)}")
                continue
        
        # スコア順でソート
        results.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            'scan_time': enhanced_signal_generator.technical_service.dow_analyzer.__dict__.get('timestamp', ''),
            'timeframe': timeframe,
            'min_score_threshold': min_score,
            'total_pairs_analyzed': len(currency_pairs),
            'qualified_pairs': len(results),
            'results': results[:limit]
        }
        
    except Exception as e:
        logger.error(f"Error in market scan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def _get_score_grade(score: float) -> str:
    """スコアをグレードに変換"""
    if score >= 90:
        return "A+ (Excellent)"
    elif score >= 80:
        return "A (Very Good)"
    elif score >= 70:
        return "B (Good)"
    elif score >= 60:
        return "C (Fair)"
    elif score >= 50:
        return "D (Poor)"
    else:
        return "F (Very Poor)"