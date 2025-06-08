"""
マルチペア管理サービス
6通貨ペア同時監視、相関調整、スコアリングシステム
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from ..core.config import settings
from ..core.database import db_manager
from ..core.logging import get_logger
from .technical_analysis import technical_analysis_service
from .risk_management import risk_manager
from .enhanced_signal_generator import enhanced_signal_generator
from .elliott_wave_analyzer import elliott_wave_analyzer

logger = get_logger(__name__)

class MultiPairManager:
    """マルチペア管理クラス"""
    
    def __init__(self):
        self.currency_pairs = settings.CURRENCY_PAIRS
        self.max_positions = settings.MAX_POSITIONS
        
        # 通貨ペア間相関係数（経験的値）
        self.correlation_matrix = {
            'USDJPY': {'EURUSD': -0.7, 'GBPUSD': -0.6, 'AUDUSD': -0.5, 'USDCHF': 0.8, 'USDCAD': 0.7},
            'EURUSD': {'USDJPY': -0.7, 'GBPUSD': 0.8, 'AUDUSD': 0.6, 'USDCHF': -0.9, 'USDCAD': -0.4},
            'GBPUSD': {'USDJPY': -0.6, 'EURUSD': 0.8, 'AUDUSD': 0.7, 'USDCHF': -0.8, 'USDCAD': -0.3},
            'AUDUSD': {'USDJPY': -0.5, 'EURUSD': 0.6, 'GBPUSD': 0.7, 'USDCHF': -0.6, 'USDCAD': 0.4},
            'USDCHF': {'USDJPY': 0.8, 'EURUSD': -0.9, 'GBPUSD': -0.8, 'AUDUSD': -0.6, 'USDCAD': 0.5},
            'USDCAD': {'USDJPY': 0.7, 'EURUSD': -0.4, 'GBPUSD': -0.3, 'AUDUSD': 0.4, 'USDCHF': 0.5}
        }
        
        # スコアリング重み
        self.scoring_weights = {
            'trend_strength': 30,      # トレンド強度（30点）
            'elliott_position': 40,    # エリオット波動位置（40点）
            'technical_accuracy': 20,  # 技術的確度（20点）
            'market_environment': 10   # 市場環境（10点）
        }
    
    def analyze_all_pairs(self) -> Dict[str, Dict]:
        """
        全通貨ペアの分析実行
        
        Returns:
            Dict: 各通貨ペアの分析結果
        """
        analysis_results = {}
        
        for symbol in self.currency_pairs:
            try:
                # 市場データ取得
                market_data = db_manager.get_latest_market_data(symbol, 200)
                
                if not market_data:
                    logger.warning(f"No market data available for {symbol}")
                    continue
                
                # 強化されたシグナル生成を使用
                comprehensive_signal = enhanced_signal_generator.generate_comprehensive_signal(
                    symbol=symbol,
                    primary_timeframe='H4'  # 4時間足をメインに使用
                )
                
                if 'error' in comprehensive_signal:
                    logger.error(f"Signal generation failed for {symbol}: {comprehensive_signal['error']}")
                    continue
                
                # テクニカル分析結果を取得
                analysis = comprehensive_signal.get('multi_timeframe_analysis', {}).get('H4', {})
                if not analysis:
                    # フォールバック：従来の分析を使用
                    analysis = technical_analysis_service.analyze_market_data(market_data)
                
                # スコアリング計算（強化版のスコアを優先）
                if 'score_breakdown' in comprehensive_signal:
                    score = comprehensive_signal['score_breakdown']
                else:
                    score = self.calculate_pair_score(symbol, analysis)
                
                analysis_results[symbol] = {
                    'analysis': analysis,
                    'score': score,
                    'timestamp': datetime.now().isoformat()
                }
                
                logger.info(f"Analysis completed for {symbol}: Score {score}")
                
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {str(e)}")
                continue
        
        return analysis_results
    
    def calculate_pair_score(self, symbol: str, analysis: Dict) -> Dict:
        """
        通貨ペアのスコア計算（100点満点）
        
        Args:
            symbol: 通貨ペア
            analysis: テクニカル分析結果
            
        Returns:
            Dict: スコア詳細
        """
        try:
            trend_analysis = analysis.get('trend_analysis', {})
            swing_points = analysis.get('swing_points', [])
            zigzag_points = analysis.get('zigzag_points', [])
            
            # 1. トレンド強度スコア（30点）
            trend_strength_score = min(trend_analysis.get('strength', 0), 30)
            
            # 2. エリオット波動位置スコア（40点）
            elliott_score = self.calculate_elliott_score(swing_points, zigzag_points)
            
            # 3. 技術的確度スコア（20点）
            technical_score = self.calculate_technical_accuracy(analysis)
            
            # 4. 市場環境スコア（10点）
            market_score = self.calculate_market_environment_score(symbol)
            
            total_score = trend_strength_score + elliott_score + technical_score + market_score
            
            return {
                'total_score': min(total_score, 100),
                'trend_strength': trend_strength_score,
                'elliott_position': elliott_score,
                'technical_accuracy': technical_score,
                'market_environment': market_score,
                'breakdown': {
                    'trend_direction': trend_analysis.get('trend', 'unknown'),
                    'swing_points_count': len(swing_points),
                    'zigzag_points_count': len(zigzag_points)
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating score for {symbol}: {str(e)}")
            return {'total_score': 0, 'error': str(e)}
    
    def calculate_elliott_score(self, swing_points: List, zigzag_points: List) -> int:
        """エリオット波動位置スコア計算（強化版）"""
        if len(zigzag_points) < 5:
            return 10  # データ不足
        
        try:
            # エリオット波動分析器を使用
            wave_patterns = elliott_wave_analyzer.detect_elliott_waves(zigzag_points)
            current_position = elliott_wave_analyzer.get_current_wave_position(wave_patterns)
            
            # 現在の波動位置からスコアを取得
            return current_position.get('score', 10)
            
        except Exception as e:
            logger.error(f"Elliott wave score calculation error: {str(e)}")
            # フォールバック：簡易的な計算
            recent_points = zigzag_points[-5:]
            price_moves = []
            for i in range(1, len(recent_points)):
                move = abs(recent_points[i]['price'] - recent_points[i-1]['price'])
                price_moves.append(move)
            
            if len(price_moves) >= 2:
                if price_moves[-1] > max(price_moves[:-1]) * 1.2:
                    return 40
                elif len(price_moves) >= 3 and price_moves[-2] > max(price_moves) * 1.1:
                    return 30
                else:
                    return 20
            
            return 15
    
    def calculate_technical_accuracy(self, analysis: Dict) -> int:
        """技術的確度スコア計算（強化版）"""
        score = 0
        
        # フィボナッチ比率の適合度（最大10点）
        elliott_data = analysis.get('elliott_wave', {})
        current_position = elliott_data.get('current_position', {})
        fibonacci_ratios = current_position.get('fibonacci_ratios', {})
        
        if fibonacci_ratios:
            # 理想的なフィボナッチ比率との一致度を評価
            for ratio_name, ratio_value in fibonacci_ratios.items():
                if 'retracement' in ratio_name:
                    ideal_ratios = [0.382, 0.5, 0.618]
                    min_diff = min(abs(ratio_value - ideal) for ideal in ideal_ratios)
                    if min_diff <= 0.05:
                        score += 5
                    elif min_diff <= 0.1:
                        score += 3
                elif 'extension' in ratio_name:
                    ideal_ratios = [1.618, 2.618]
                    min_diff = min(abs(ratio_value - ideal) for ideal in ideal_ratios)
                    if min_diff <= 0.1:
                        score += 5
                    elif min_diff <= 0.2:
                        score += 3
        
        # データ品質と一貫性（最大10点）
        swing_points_count = analysis.get('swing_points_count', 0)
        zigzag_count = analysis.get('zigzag_points_count', 0)
        data_points = analysis.get('data_points', 0)
        
        quality_score = 0
        if swing_points_count >= 4 and zigzag_count >= 6:
            quality_score += 5
        elif swing_points_count >= 2 and zigzag_count >= 3:
            quality_score += 3
        
        if data_points >= 100:
            quality_score += 5
        elif data_points >= 50:
            quality_score += 3
        
        score += quality_score
        
        return min(score, 20)
    
    def calculate_market_environment_score(self, symbol: str) -> int:
        """市場環境スコア計算"""
        score = 0
        current_time = datetime.now()
        
        # 流動性時間帯チェック（NY時間：日本時間22:00-06:00）
        jst_hour = (current_time.hour + 9) % 24  # JST変換
        if 22 <= jst_hour or jst_hour <= 6:
            score += 5  # NY時間帯
        
        # スプレッド状況（簡易判定）
        # 実際の実装では、リアルタイムスプレッドを取得
        if symbol in ['USDJPY', 'EURUSD']:
            score += 3  # 主要ペア
        else:
            score += 2  # その他
        
        # ボラティリティ適正性
        # 実際の実装では、ATRの過去平均との比較
        score += 2  # 仮の値
        
        return min(score, 10)
    
    def apply_correlation_adjustment(self, pair_scores: Dict[str, Dict], 
                                   current_positions: List[Dict]) -> Dict[str, Dict]:
        """
        相関調整を適用
        
        Args:
            pair_scores: 各ペアのスコア
            current_positions: 現在のポジション
            
        Returns:
            Dict: 調整後のスコア
        """
        adjusted_scores = pair_scores.copy()
        
        # 現在のポジションから保有通貨ペアを取得
        held_symbols = [pos.get('symbol') for pos in current_positions]
        
        for symbol, score_data in pair_scores.items():
            if symbol in held_symbols:
                continue  # 既に保有中のペアはスキップ
            
            # 保有ペアとの相関を考慮した調整
            for held_symbol in held_symbols:
                if held_symbol in self.correlation_matrix.get(symbol, {}):
                    correlation = self.correlation_matrix[symbol][held_symbol]
                    
                    # 強い逆相関（-0.7以下）の場合は減点
                    if correlation <= -0.7:
                        adjustment_factor = 0.7
                        adjusted_scores[symbol]['total_score'] *= adjustment_factor
                        logger.info(f"Correlation adjustment applied to {symbol} "
                                  f"due to strong negative correlation with {held_symbol}")
                    
                    # 強い正相関（0.7以上）の場合も減点（リスク分散のため）
                    elif correlation >= 0.7:
                        adjustment_factor = 0.8
                        adjusted_scores[symbol]['total_score'] *= adjustment_factor
                        logger.info(f"Correlation adjustment applied to {symbol} "
                                  f"due to strong positive correlation with {held_symbol}")
        
        return adjusted_scores
    
    def select_top_pairs(self, adjusted_scores: Dict[str, Dict], 
                        current_positions: List[Dict]) -> List[Dict]:
        """
        上位ペア選択
        
        Args:
            adjusted_scores: 調整後スコア
            current_positions: 現在のポジション
            
        Returns:
            List: 選択されたペア情報
        """
        # スコア順でソート
        sorted_pairs = sorted(
            adjusted_scores.items(),
            key=lambda x: x[1].get('total_score', 0),
            reverse=True
        )
        
        current_symbols = [pos.get('symbol') for pos in current_positions]
        available_slots = self.max_positions - len(current_positions)
        
        selected_pairs = []
        
        for symbol, score_data in sorted_pairs:
            if symbol in current_symbols:
                continue  # 既に保有中
            
            if len(selected_pairs) >= available_slots:
                break  # 最大ポジション数に到達
            
            # 最小スコア閾値チェック
            if score_data.get('total_score', 0) >= 60:  # 60点以上
                selected_pairs.append({
                    'symbol': symbol,
                    'score': score_data.get('total_score', 0),
                    'score_details': score_data,
                    'recommendation': 'buy' if score_data.get('breakdown', {}).get('trend_direction') == 'uptrend' else 'sell'
                })
        
        logger.info(f"Selected {len(selected_pairs)} pairs for trading: "
                   f"{[p['symbol'] for p in selected_pairs]}")
        
        return selected_pairs
    
    def check_position_replacement(self, current_positions: List[Dict], 
                                 new_candidates: List[Dict]) -> List[Dict]:
        """
        ポジション入替検討
        
        Args:
            current_positions: 現在のポジション
            new_candidates: 新候補ペア
            
        Returns:
            List: 入替推奨リスト
        """
        replacements = []
        
        if not current_positions or not new_candidates:
            return replacements
        
        # 現在のポジションの平均スコアを計算（仮想的）
        for position in current_positions:
            symbol = position.get('symbol')
            
            # 現在のスコアを再計算
            market_data = db_manager.get_latest_market_data(symbol, 100)
            if market_data:
                analysis = technical_analysis_service.analyze_market_data(market_data)
                current_score = self.calculate_pair_score(symbol, analysis)
                position['current_score'] = current_score.get('total_score', 0)
            else:
                position['current_score'] = 30  # データ不足時のデフォルト
        
        # 最低スコアのポジションを特定
        lowest_position = min(current_positions, key=lambda x: x.get('current_score', 0))
        lowest_score = lowest_position.get('current_score', 0)
        
        # 新候補の最高スコア
        if new_candidates:
            highest_candidate = max(new_candidates, key=lambda x: x.get('score', 0))
            highest_score = highest_candidate.get('score', 0)
            
            # 15点以上の差があれば入替推奨
            if highest_score - lowest_score >= 15:
                replacements.append({
                    'action': 'replace',
                    'close_position': lowest_position,
                    'open_position': highest_candidate,
                    'score_improvement': highest_score - lowest_score
                })
                
                logger.info(f"Position replacement recommended: "
                           f"Close {lowest_position.get('symbol')} (score: {lowest_score}) "
                           f"-> Open {highest_candidate.get('symbol')} (score: {highest_score})")
        
        return replacements
    
    def generate_multi_pair_signals(self) -> Dict:
        """
        マルチペアシグナル生成
        
        Returns:
            Dict: 統合シグナル情報
        """
        try:
            # 1. 全ペア分析
            all_analysis = self.analyze_all_pairs()
            
            # 2. スコア計算
            pair_scores = {}
            for symbol, data in all_analysis.items():
                pair_scores[symbol] = data.get('score', {'total_score': 0})
            
            # 3. 現在のポジション取得
            current_positions = db_manager.get_active_trades()
            
            # 4. 相関調整適用
            adjusted_scores = self.apply_correlation_adjustment(pair_scores, current_positions)
            
            # 5. 上位ペア選択
            selected_pairs = self.select_top_pairs(adjusted_scores, current_positions)
            
            # 6. ポジション入替検討
            replacements = self.check_position_replacement(current_positions, selected_pairs)
            
            result = {
                'timestamp': datetime.now().isoformat(),
                'analysis_results': all_analysis,
                'pair_scores': adjusted_scores,
                'selected_pairs': selected_pairs,
                'current_positions': len(current_positions),
                'replacement_recommendations': replacements,
                'summary': {
                    'analyzed_pairs': len(all_analysis),
                    'qualified_pairs': len([p for p in adjusted_scores.values() 
                                          if p.get('total_score', 0) >= 60]),
                    'selected_for_trading': len(selected_pairs),
                    'replacement_opportunities': len(replacements)
                }
            }
            
            logger.info(f"Multi-pair analysis completed: "
                       f"{result['summary']['analyzed_pairs']} pairs analyzed, "
                       f"{result['summary']['selected_for_trading']} selected for trading")
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating multi-pair signals: {str(e)}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

# サービスインスタンス
multi_pair_manager = MultiPairManager()