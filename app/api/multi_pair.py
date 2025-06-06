from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Optional
from datetime import datetime
from ..services.multi_pair_manager import multi_pair_manager
from ..services.risk_management import risk_manager
from ..core.database import db_manager
from ..core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["multi_pair"])

@router.get("/multi-pair/analysis")
async def get_multi_pair_analysis():
    """
    6ペア同時分析実行
    """
    try:
        logger.info("Starting multi-pair analysis")
        
        # マルチペア分析実行
        analysis_result = multi_pair_manager.generate_multi_pair_signals()
        
        if 'error' in analysis_result:
            raise HTTPException(
                status_code=500,
                detail=f"Multi-pair analysis failed: {analysis_result['error']}"
            )
        
        logger.info(f"Multi-pair analysis completed: {analysis_result['summary']}")
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in multi-pair analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")

@router.get("/multi-pair/scores")
async def get_pair_scores():
    """
    全ペアのスコア取得
    """
    try:
        # 全ペア分析
        all_analysis = multi_pair_manager.analyze_all_pairs()
        
        # スコアのみを抽出
        scores = {}
        for symbol, data in all_analysis.items():
            scores[symbol] = data.get('score', {'total_score': 0})
        
        # 現在のポジションを考慮した相関調整
        current_positions = db_manager.get_active_trades()
        adjusted_scores = multi_pair_manager.apply_correlation_adjustment(scores, current_positions)
        
        return {
            'raw_scores': scores,
            'adjusted_scores': adjusted_scores,
            'current_positions': len(current_positions),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting pair scores: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Score calculation error: {str(e)}")

@router.get("/multi-pair/recommendations")
async def get_trading_recommendations():
    """
    取引推奨ペア取得
    """
    try:
        # マルチペア分析実行
        analysis_result = multi_pair_manager.generate_multi_pair_signals()
        
        if 'error' in analysis_result:
            raise HTTPException(status_code=500, detail=analysis_result['error'])
        
        recommendations = {
            'selected_pairs': analysis_result.get('selected_pairs', []),
            'replacement_recommendations': analysis_result.get('replacement_recommendations', []),
            'summary': analysis_result.get('summary', {}),
            'timestamp': analysis_result.get('timestamp')
        }
        
        return recommendations
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recommendation error: {str(e)}")

@router.get("/multi-pair/correlation-matrix")
async def get_correlation_matrix():
    """
    通貨ペア相関マトリックス取得
    """
    try:
        return {
            'correlation_matrix': multi_pair_manager.correlation_matrix,
            'description': 'Currency pair correlation coefficients (-1 to 1)',
            'note': 'Negative values indicate inverse correlation, positive values indicate direct correlation',
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting correlation matrix: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Correlation matrix error: {str(e)}")

@router.post("/multi-pair/execute-recommendations")
async def execute_recommendations(background_tasks: BackgroundTasks):
    """
    推奨取引の自動実行
    """
    try:
        # 推奨取得
        analysis_result = multi_pair_manager.generate_multi_pair_signals()
        
        if 'error' in analysis_result:
            raise HTTPException(status_code=500, detail=analysis_result['error'])
        
        selected_pairs = analysis_result.get('selected_pairs', [])
        replacements = analysis_result.get('replacement_recommendations', [])
        
        execution_results = []
        
        # 新規ポジション実行
        for pair in selected_pairs:
            try:
                # リスク計算
                risk_calc = risk_manager.calculate_position_size(
                    pair['symbol'],
                    150.0,  # 仮のエントリー価格
                    149.0,  # 仮のストップロス
                    100000.0  # 仮の口座残高
                )
                
                execution_results.append({
                    'action': 'new_position',
                    'symbol': pair['symbol'],
                    'score': pair['score'],
                    'recommended_lot_size': risk_calc.get('calculated_lot_size', 0),
                    'status': 'simulated'  # 実際の実行は別途実装
                })
                
            except Exception as e:
                logger.error(f"Error executing recommendation for {pair['symbol']}: {str(e)}")
                execution_results.append({
                    'action': 'new_position',
                    'symbol': pair['symbol'],
                    'status': 'error',
                    'error': str(e)
                })
        
        # ポジション入替実行
        for replacement in replacements:
            execution_results.append({
                'action': 'replacement',
                'close_symbol': replacement['close_position']['symbol'],
                'open_symbol': replacement['open_position']['symbol'],
                'score_improvement': replacement['score_improvement'],
                'status': 'simulated'  # 実際の実行は別途実装
            })
        
        return {
            'execution_results': execution_results,
            'total_actions': len(execution_results),
            'timestamp': datetime.now().isoformat(),
            'note': 'This is a simulation. Actual trading requires manual confirmation.'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

@router.get("/multi-pair/pair-comparison")
async def compare_pairs(
    symbols: List[str] = Query(..., description="List of symbols to compare"),
    metric: str = Query(default="total_score", description="Comparison metric")
):
    """
    通貨ペア比較
    """
    try:
        if len(symbols) < 2:
            raise HTTPException(status_code=400, detail="At least 2 symbols required for comparison")
        
        # 指定ペアの分析
        comparison_data = {}
        
        for symbol in symbols:
            if symbol not in multi_pair_manager.currency_pairs:
                raise HTTPException(status_code=400, detail=f"Unsupported symbol: {symbol}")
            
            # 市場データ取得
            market_data = db_manager.get_latest_market_data(symbol, 100)
            if market_data:
                from ..services.technical_analysis import technical_analysis_service
                analysis = technical_analysis_service.analyze_market_data(market_data)
                score = multi_pair_manager.calculate_pair_score(symbol, analysis)
                
                comparison_data[symbol] = {
                    'analysis': analysis,
                    'score': score,
                    'current_price': market_data[0].get('close', 0) if market_data else 0
                }
            else:
                comparison_data[symbol] = {
                    'error': 'No market data available'
                }
        
        # メトリック別ランキング
        ranking = []
        for symbol, data in comparison_data.items():
            if 'error' not in data:
                value = data['score'].get(metric, 0)
                ranking.append({
                    'symbol': symbol,
                    'value': value,
                    'score_details': data['score']
                })
        
        ranking.sort(key=lambda x: x['value'], reverse=True)
        
        return {
            'comparison_data': comparison_data,
            'ranking': ranking,
            'metric': metric,
            'timestamp': datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing pairs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Comparison error: {str(e)}")

@router.get("/multi-pair/optimization-status")
async def get_optimization_status():
    """
    最適化状況取得
    """
    try:
        current_positions = db_manager.get_active_trades()
        
        # 現在のポートフォリオ分析
        portfolio_analysis = {
            'total_positions': len(current_positions),
            'max_positions': multi_pair_manager.max_positions,
            'utilization_rate': len(current_positions) / multi_pair_manager.max_positions,
            'symbols': [pos.get('symbol') for pos in current_positions]
        }
        
        # 相関分析
        if len(current_positions) > 1:
            correlation_risks = []
            symbols = portfolio_analysis['symbols']
            
            for i, symbol1 in enumerate(symbols):
                for symbol2 in symbols[i+1:]:
                    if symbol1 in multi_pair_manager.correlation_matrix:
                        correlation = multi_pair_manager.correlation_matrix[symbol1].get(symbol2, 0)
                        if abs(correlation) > 0.7:
                            correlation_risks.append({
                                'pair1': symbol1,
                                'pair2': symbol2,
                                'correlation': correlation,
                                'risk_level': 'high' if abs(correlation) > 0.8 else 'medium'
                            })
            
            portfolio_analysis['correlation_risks'] = correlation_risks
        
        # 最適化推奨
        optimization_recommendations = []
        
        if portfolio_analysis['utilization_rate'] < 0.8:
            optimization_recommendations.append({
                'type': 'increase_exposure',
                'message': 'Portfolio utilization is low. Consider adding more positions.',
                'priority': 'medium'
            })
        
        if len(portfolio_analysis.get('correlation_risks', [])) > 0:
            optimization_recommendations.append({
                'type': 'reduce_correlation',
                'message': 'High correlation detected between positions. Consider diversification.',
                'priority': 'high'
            })
        
        return {
            'portfolio_analysis': portfolio_analysis,
            'optimization_recommendations': optimization_recommendations,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting optimization status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Optimization status error: {str(e)}")