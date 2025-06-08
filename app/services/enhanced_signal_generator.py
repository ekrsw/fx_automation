"""
強化されたシグナル生成サービス
100点満点のスコアリングシステムと複数時間軸分析
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from ..core.logging import get_logger
from .technical_analysis import TechnicalAnalysisService, DowTheoryAnalyzer
from .elliott_wave_analyzer import ElliottWaveAnalyzer
from ..core.database import db_manager

logger = get_logger(__name__)

class EnhancedSignalGenerator:
    """強化されたシグナル生成クラス"""
    
    def __init__(self):
        self.technical_service = TechnicalAnalysisService()
        self.elliott_analyzer = ElliottWaveAnalyzer()
        self.dow_analyzer = DowTheoryAnalyzer()
        
        # 時間軸の定義（分）
        self.timeframes = {
            'M5': 5,      # 5分足（エントリータイミング）
            'M15': 15,    # 15分足
            'H1': 60,     # 1時間足
            'H4': 240,    # 4時間足（メイントレンド）
            'D1': 1440    # 日足（大局トレンド）
        }
        
        # スコアリング重み（合計100点）
        self.scoring_weights = {
            'trend_strength': 30,      # トレンド強度
            'elliott_wave': 40,        # エリオット波動位置
            'technical_accuracy': 20,  # 技術的確度
            'market_environment': 10   # 市場環境
        }
    
    def generate_comprehensive_signal(self, symbol: str, primary_timeframe: str = 'H4') -> Dict:
        """
        包括的なシグナル生成
        
        Args:
            symbol: 通貨ペア
            primary_timeframe: メイン分析時間軸
            
        Returns:
            Dict: シグナル情報と100点満点のスコア
        """
        try:
            # 複数時間軸のデータを取得
            mtf_data = self._get_multi_timeframe_data(symbol)
            
            if not mtf_data:
                return {
                    'symbol': symbol,
                    'error': 'Insufficient data for analysis',
                    'timestamp': datetime.now().isoformat()
                }
            
            # 各時間軸で分析を実行
            mtf_analysis = {}
            for tf, data in mtf_data.items():
                if len(data) >= 50:  # 最低限のデータ数
                    analysis = self._analyze_timeframe(data, tf)
                    mtf_analysis[tf] = analysis
            
            # プライマリ時間軸の分析を取得
            primary_analysis = mtf_analysis.get(primary_timeframe)
            if not primary_analysis:
                return {
                    'symbol': symbol,
                    'error': f'No analysis available for {primary_timeframe}',
                    'timestamp': datetime.now().isoformat()
                }
            
            # 100点満点のスコアを計算
            score_breakdown = self._calculate_comprehensive_score(
                symbol, primary_analysis, mtf_analysis
            )
            
            # シグナル判定
            signal = self._determine_signal(score_breakdown, primary_analysis)
            
            result = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'primary_timeframe': primary_timeframe,
                'score': score_breakdown['total_score'],
                'score_breakdown': score_breakdown,
                'signal': signal,
                'multi_timeframe_analysis': mtf_analysis,
                'recommendation': self._generate_recommendation(score_breakdown, signal)
            }
            
            logger.info(f"Signal generated for {symbol}: Score {score_breakdown['total_score']}, "
                       f"Signal: {signal['action']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {str(e)}")
            return {
                'symbol': symbol,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _get_multi_timeframe_data(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """複数時間軸のデータを取得"""
        mtf_data = {}
        
        try:
            # 各時間軸のデータを取得
            for tf_name, tf_minutes in self.timeframes.items():
                try:
                    # データベースから最新データを取得
                    raw_data = db_manager.get_latest_market_data(symbol, 500)
                    
                    if raw_data and len(raw_data) > 0:
                        # データフレームに変換
                        df = pd.DataFrame(raw_data)
                        
                        # 必要なカラムがあるかチェック
                        required_cols = ['open', 'high', 'low', 'close', 'timestamp']
                        if all(col in df.columns for col in required_cols):
                            # 時間軸に応じてリサンプリング（簡易版）
                            if tf_minutes > 5:  # 5分より大きい時間軸
                                # ここでは簡易的に間引く
                                step = max(1, tf_minutes // 5)
                                df_resampled = df.iloc[::step].copy()
                                
                                # 最低限のデータ数を保証
                                if len(df_resampled) < 50:
                                    df_resampled = df.tail(50).copy()
                            else:
                                df_resampled = df.copy()
                            
                            mtf_data[tf_name] = df_resampled
                            logger.info(f"Loaded {len(df_resampled)} bars for {symbol} {tf_name}")
                        else:
                            logger.warning(f"Missing required columns for {tf_name}: {df.columns.tolist()}")
                    else:
                        logger.warning(f"No data available for {symbol} {tf_name}")
                except Exception as e:
                    logger.error(f"Error loading data for {tf_name}: {str(e)}")
                    continue
            
            return mtf_data
            
        except Exception as e:
            logger.error(f"Error loading multi-timeframe data: {str(e)}")
            return {}
    
    def _analyze_timeframe(self, data: pd.DataFrame, timeframe: str) -> Dict:
        """単一時間軸の分析"""
        try:
            # テクニカル分析を実行
            analysis = self.technical_service.analyze_market_data(data.to_dict('records'))
            
            # エリオット波動分析を追加
            if 'zigzag_points' in analysis and analysis['zigzag_points']:
                wave_patterns = self.elliott_analyzer.detect_elliott_waves(
                    analysis['zigzag_points']
                )
                wave_position = self.elliott_analyzer.get_current_wave_position(wave_patterns)
                analysis['elliott_wave'] = {
                    'patterns': wave_patterns,
                    'current_position': wave_position
                }
            else:
                analysis['elliott_wave'] = {
                    'patterns': [],
                    'current_position': {'current_wave': None, 'score': 0}
                }
            
            # ATRとボラティリティ計算
            if len(data) >= 14:
                atr = self._calculate_atr(data)
                analysis['atr'] = atr
                analysis['volatility'] = atr / data['close'].iloc[-1] if data['close'].iloc[-1] > 0 else 0
            
            analysis['timeframe'] = timeframe
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing timeframe {timeframe}: {str(e)}")
            return {'error': str(e), 'timeframe': timeframe}
    
    def _calculate_comprehensive_score(self, symbol: str, primary_analysis: Dict, 
                                     mtf_analysis: Dict) -> Dict:
        """
        100点満点の包括的スコアを計算
        """
        scores = {
            'trend_strength': 0,
            'elliott_wave': 0,
            'technical_accuracy': 0,
            'market_environment': 0
        }
        
        # 1. トレンド強度スコア（30点）
        scores['trend_strength'] = self._calculate_trend_strength_score(
            primary_analysis, mtf_analysis
        )
        
        # 2. エリオット波動位置スコア（40点）
        scores['elliott_wave'] = self._calculate_elliott_wave_score(
            primary_analysis
        )
        
        # 3. 技術的確度スコア（20点）
        scores['technical_accuracy'] = self._calculate_technical_accuracy_score(
            primary_analysis, mtf_analysis
        )
        
        # 4. 市場環境スコア（10点）
        scores['market_environment'] = self._calculate_market_environment_score(
            symbol, primary_analysis
        )
        
        # 合計スコア
        total_score = sum(scores.values())
        
        return {
            'total_score': min(total_score, 100),
            'trend_strength': scores['trend_strength'],
            'elliott_wave': scores['elliott_wave'],
            'technical_accuracy': scores['technical_accuracy'],
            'market_environment': scores['market_environment']
        }
    
    def _calculate_trend_strength_score(self, primary_analysis: Dict, 
                                      mtf_analysis: Dict) -> float:
        """
        トレンド強度スコアの計算（30点満点）
        - ダウ理論での連続的な高値・安値更新回数
        - 直近のスイングポイント間の角度
        - 複数時間軸での方向一致
        """
        score = 0
        
        # ダウ理論分析結果を取得
        trend_analysis = primary_analysis.get('trend_analysis', {})
        
        # 連続的な高値・安値更新（最大15点）
        hh_count = trend_analysis.get('higher_highs', 0)
        ll_count = trend_analysis.get('lower_lows', 0)
        hl_count = trend_analysis.get('higher_lows', 0)
        lh_count = trend_analysis.get('lower_highs', 0)
        
        # 上昇トレンドの強さ
        uptrend_strength = min(hh_count + hl_count, 5) * 3  # 最大15点
        # 下降トレンドの強さ
        downtrend_strength = min(lh_count + ll_count, 5) * 3  # 最大15点
        
        score += max(uptrend_strength, downtrend_strength)
        
        # スイングポイント間の角度（最大10点）
        swing_points = primary_analysis.get('swing_points', [])
        if len(swing_points) >= 2:
            # 最新2つのスイングポイント間の角度を計算
            latest_points = swing_points[-2:]
            price_change = abs(latest_points[1]['price'] - latest_points[0]['price'])
            time_diff = latest_points[1]['index'] - latest_points[0]['index']
            
            if time_diff > 0:
                angle_score = min((price_change / latest_points[0]['price']) * 1000, 10)
                score += angle_score
        
        # 複数時間軸での方向一致（最大5点）
        trend_directions = []
        for tf, analysis in mtf_analysis.items():
            if 'trend_analysis' in analysis:
                trend_directions.append(analysis['trend_analysis'].get('trend'))
        
        if trend_directions:
            # 上昇トレンドの一致度
            uptrend_count = trend_directions.count('uptrend')
            downtrend_count = trend_directions.count('downtrend')
            
            if uptrend_count >= 3 or downtrend_count >= 3:
                score += 5
            elif uptrend_count >= 2 or downtrend_count >= 2:
                score += 3
        
        return min(score, 30)
    
    def _calculate_elliott_wave_score(self, primary_analysis: Dict) -> float:
        """
        エリオット波動位置スコアの計算（40点満点）
        - 第3波開始: 40点
        - 第1波開始: 30点
        - 第5波開始: 20点
        - 修正波: 10点
        """
        elliott_data = primary_analysis.get('elliott_wave', {})
        current_position = elliott_data.get('current_position', {})
        
        current_wave = current_position.get('current_wave')
        confidence = current_position.get('confidence', 0)
        
        # 波動タイプに応じた基本スコア
        base_scores = {
            '3': 40,  # 第3波（最も強い推進波）
            '1': 30,  # 第1波（新トレンドの開始）
            '5': 20,  # 第5波（トレンドの最終波）
            'C': 15,  # C波（修正波の推進部分）
            'A': 10,  # A波（修正の開始）
            '2': 5,   # 第2波（調整）
            '4': 5,   # 第4波（調整）
            'B': 5    # B波（調整）
        }
        
        base_score = base_scores.get(current_wave, 0)
        
        # 信頼度による調整
        adjusted_score = base_score * confidence
        
        return min(adjusted_score, 40)
    
    def _calculate_technical_accuracy_score(self, primary_analysis: Dict, 
                                          mtf_analysis: Dict) -> float:
        """
        技術的確度スコアの計算（20点満点）
        - フィボナッチ比率適合度
        - 複数時間軸での一致性
        """
        score = 0
        
        # フィボナッチ比率の適合度（最大10点）
        elliott_data = primary_analysis.get('elliott_wave', {})
        current_position = elliott_data.get('current_position', {})
        fibonacci_ratios = current_position.get('fibonacci_ratios', {})
        
        if fibonacci_ratios:
            # 理想的なフィボナッチ比率との一致度を評価
            for ratio_name, ratio_value in fibonacci_ratios.items():
                if 'retracement' in ratio_name:
                    # リトレースメントの理想値（38.2%, 50%, 61.8%）
                    ideal_ratios = [0.382, 0.5, 0.618]
                    min_diff = min(abs(ratio_value - ideal) for ideal in ideal_ratios)
                    if min_diff <= 0.05:  # 5%以内
                        score += 5
                    elif min_diff <= 0.1:  # 10%以内
                        score += 3
                elif 'extension' in ratio_name:
                    # エクステンションの理想値（161.8%, 261.8%）
                    ideal_ratios = [1.618, 2.618]
                    min_diff = min(abs(ratio_value - ideal) for ideal in ideal_ratios)
                    if min_diff <= 0.1:  # 10%以内
                        score += 5
                    elif min_diff <= 0.2:  # 20%以内
                        score += 3
        
        # 複数時間軸での技術的指標の一致性（最大10点）
        # 日足と4時間足の方向一致
        d1_analysis = mtf_analysis.get('D1', {})
        h4_analysis = mtf_analysis.get('H4', {})
        
        if d1_analysis and h4_analysis:
            d1_trend = d1_analysis.get('trend_analysis', {}).get('trend')
            h4_trend = h4_analysis.get('trend_analysis', {}).get('trend')
            
            if d1_trend == h4_trend and d1_trend in ['uptrend', 'downtrend']:
                score += 10
            elif d1_trend and h4_trend and d1_trend != 'sideways':
                score += 5
        
        return min(score, 20)
    
    def _calculate_market_environment_score(self, symbol: str, 
                                          primary_analysis: Dict) -> float:
        """
        市場環境スコアの計算（10点満点）
        - ボラティリティ適正性
        - 流動性時間帯
        """
        score = 0
        
        # ボラティリティ適正性（最大5点）
        volatility = primary_analysis.get('volatility', 0)
        atr = primary_analysis.get('atr', 0)
        
        # ATRが過去20日平均の80-120%が理想
        # ここでは簡易的に絶対値で判定
        if 0.008 <= volatility <= 0.012:  # 0.8%-1.2%
            score += 5
        elif 0.005 <= volatility <= 0.015:  # 0.5%-1.5%
            score += 3
        elif volatility > 0:
            score += 1
        
        # 流動性時間帯（最大5点）
        current_hour = datetime.now().hour
        
        # 東京時間（9:00-15:00 JST）
        if 9 <= current_hour <= 15:
            score += 2
        # ロンドン時間（16:00-24:00 JST）
        elif 16 <= current_hour <= 24:
            score += 3
        # NY時間（22:00-6:00 JST）
        elif 22 <= current_hour or current_hour <= 6:
            score += 5
        
        return min(score, 10)
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> float:
        """ATR（Average True Range）を計算"""
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift())
        low_close = np.abs(data['low'] - data['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean().iloc[-1]
        
        return atr
    
    def _determine_signal(self, score_breakdown: Dict, primary_analysis: Dict) -> Dict:
        """
        スコアに基づいてシグナルを決定
        """
        total_score = score_breakdown['total_score']
        trend_analysis = primary_analysis.get('trend_analysis', {})
        trend_direction = trend_analysis.get('trend', 'sideways')
        
        signal = {
            'action': 'hold',
            'strength': 'weak',
            'confidence': total_score / 100,
            'entry_price': None,
            'stop_loss': None,
            'take_profit': None
        }
        
        # スコアに基づくシグナル判定
        if total_score >= 80:
            signal['strength'] = 'strong'
            if trend_direction == 'uptrend':
                signal['action'] = 'buy'
            elif trend_direction == 'downtrend':
                signal['action'] = 'sell'
        elif total_score >= 60:
            signal['strength'] = 'moderate'
            if trend_direction == 'uptrend':
                signal['action'] = 'buy'
            elif trend_direction == 'downtrend':
                signal['action'] = 'sell'
        elif total_score >= 40:
            signal['strength'] = 'weak'
            # 弱いシグナルは保留
        
        # エントリー価格とストップ・利確の設定
        if signal['action'] != 'hold':
            latest_data = primary_analysis.get('data_points', [])
            if latest_data:
                current_price = latest_data[-1].get('close', 0)
                atr = primary_analysis.get('atr', current_price * 0.01)
                
                signal['entry_price'] = current_price
                
                if signal['action'] == 'buy':
                    signal['stop_loss'] = current_price - (atr * 2)
                    signal['take_profit'] = current_price + (atr * 3)
                else:  # sell
                    signal['stop_loss'] = current_price + (atr * 2)
                    signal['take_profit'] = current_price - (atr * 3)
        
        return signal
    
    def _generate_recommendation(self, score_breakdown: Dict, signal: Dict) -> str:
        """
        スコアとシグナルに基づく推奨事項を生成
        """
        total_score = score_breakdown['total_score']
        
        if total_score >= 80:
            return f"Strong {signal['action'].upper()} signal detected. High confidence entry recommended."
        elif total_score >= 60:
            return f"Moderate {signal['action'].upper()} signal. Consider entry with reduced position size."
        elif total_score >= 40:
            return "Weak signal detected. Wait for stronger confirmation before entry."
        else:
            return "No clear signal. Market conditions are not favorable for entry."

# サービスインスタンス
enhanced_signal_generator = EnhancedSignalGenerator()