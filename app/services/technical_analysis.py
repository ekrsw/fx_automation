"""
テクニカル分析サービス
ダウ理論とエリオット波動理論の実装
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import logging
from ..core.logging import get_logger

logger = get_logger(__name__)

class SwingPoint:
    """スイングポイントクラス"""
    def __init__(self, index: int, price: float, timestamp: str, point_type: str):
        self.index = index
        self.price = price
        self.timestamp = timestamp
        self.point_type = point_type  # 'high' or 'low'

class DowTheoryAnalyzer:
    """ダウ理論分析クラス"""
    
    def __init__(self, swing_sensitivity: int = 5, min_swing_distance: float = 0.001):
        self.swing_sensitivity = swing_sensitivity
        self.min_swing_distance = min_swing_distance
        
    def detect_swing_points(self, df: pd.DataFrame) -> List[SwingPoint]:
        """
        スイングポイント検出
        
        Args:
            df: OHLC データフレーム (columns: open, high, low, close, timestamp)
            
        Returns:
            List[SwingPoint]: 検出されたスイングポイントのリスト
        """
        swing_points = []
        
        if len(df) < self.swing_sensitivity * 2 + 1:
            logger.warning("Insufficient data for swing point detection")
            return swing_points
        
        # 高値のスイングポイント検出
        for i in range(self.swing_sensitivity, len(df) - self.swing_sensitivity):
            is_swing_high = True
            current_high = df.iloc[i]['high']
            
            # 前後の期間と比較
            for j in range(i - self.swing_sensitivity, i + self.swing_sensitivity + 1):
                if j != i and df.iloc[j]['high'] >= current_high:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                swing_points.append(SwingPoint(
                    index=i,
                    price=current_high,
                    timestamp=df.iloc[i]['timestamp'],
                    point_type='high'
                ))
        
        # 安値のスイングポイント検出
        for i in range(self.swing_sensitivity, len(df) - self.swing_sensitivity):
            is_swing_low = True
            current_low = df.iloc[i]['low']
            
            # 前後の期間と比較
            for j in range(i - self.swing_sensitivity, i + self.swing_sensitivity + 1):
                if j != i and df.iloc[j]['low'] <= current_low:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                swing_points.append(SwingPoint(
                    index=i,
                    price=current_low,
                    timestamp=df.iloc[i]['timestamp'],
                    point_type='low'
                ))
        
        # 時系列順にソート
        swing_points.sort(key=lambda x: x.index)
        
        # 最小距離フィルター適用
        filtered_points = self._filter_by_distance(swing_points)
        
        logger.info(f"Detected {len(filtered_points)} swing points from {len(df)} bars")
        return filtered_points
    
    def _filter_by_distance(self, swing_points: List[SwingPoint]) -> List[SwingPoint]:
        """最小価格距離でスイングポイントをフィルタリング"""
        if not swing_points:
            return swing_points
        
        filtered = [swing_points[0]]
        
        for point in swing_points[1:]:
            last_point = filtered[-1]
            
            # 同じタイプのポイント間の距離をチェック
            if point.point_type == last_point.point_type:
                price_diff = abs(point.price - last_point.price)
                if price_diff >= self.min_swing_distance:
                    filtered.append(point)
                elif (point.point_type == 'high' and point.price > last_point.price) or \
                     (point.point_type == 'low' and point.price < last_point.price):
                    # より極端な値の場合は置き換える
                    filtered[-1] = point
            else:
                filtered.append(point)
        
        return filtered
    
    def analyze_trend(self, swing_points: List[SwingPoint]) -> Dict:
        """
        トレンド分析（ダウ理論ベース）
        
        Args:
            swing_points: スイングポイントのリスト
            
        Returns:
            Dict: トレンド分析結果
        """
        if len(swing_points) < 4:
            return {
                'trend': 'insufficient_data',
                'strength': 0,
                'highs': [],
                'lows': [],
                'analysis': 'Insufficient swing points for trend analysis'
            }
        
        # 高値と安値を分離
        highs = [p for p in swing_points if p.point_type == 'high']
        lows = [p for p in swing_points if p.point_type == 'low']
        
        if len(highs) < 2 or len(lows) < 2:
            return {
                'trend': 'insufficient_data',
                'strength': 0,
                'highs': highs,
                'lows': lows,
                'analysis': 'Insufficient high/low points for trend analysis'
            }
        
        # 高値の推移を分析
        higher_highs = 0
        lower_highs = 0
        for i in range(1, len(highs)):
            if highs[i].price > highs[i-1].price:
                higher_highs += 1
            elif highs[i].price < highs[i-1].price:
                lower_highs += 1
        
        # 安値の推移を分析
        higher_lows = 0
        lower_lows = 0
        for i in range(1, len(lows)):
            if lows[i].price > lows[i-1].price:
                higher_lows += 1
            elif lows[i].price < lows[i-1].price:
                lower_lows += 1
        
        # トレンド判定
        trend = self._determine_trend(higher_highs, lower_highs, higher_lows, lower_lows)
        strength = self._calculate_trend_strength(higher_highs, lower_highs, higher_lows, lower_lows)
        
        analysis = f"HH:{higher_highs}, LH:{lower_highs}, HL:{higher_lows}, LL:{lower_lows}"
        
        return {
            'trend': trend,
            'strength': strength,
            'highs': highs,
            'lows': lows,
            'higher_highs': higher_highs,
            'lower_highs': lower_highs,
            'higher_lows': higher_lows,
            'lower_lows': lower_lows,
            'analysis': analysis
        }
    
    def _determine_trend(self, hh: int, lh: int, hl: int, ll: int) -> str:
        """トレンド方向の決定"""
        uptrend_score = hh + hl  # 高値切り上げ + 安値切り上げ
        downtrend_score = lh + ll  # 高値切り下げ + 安値切り下げ
        
        if uptrend_score > downtrend_score and uptrend_score >= 2:
            return 'uptrend'
        elif downtrend_score > uptrend_score and downtrend_score >= 2:
            return 'downtrend'
        else:
            return 'sideways'
    
    def _calculate_trend_strength(self, hh: int, lh: int, hl: int, ll: int) -> int:
        """トレンド強度の計算（0-30点）"""
        total_points = hh + lh + hl + ll
        
        if total_points == 0:
            return 0
        
        uptrend_score = hh + hl
        downtrend_score = lh + ll
        
        max_score = max(uptrend_score, downtrend_score)
        
        # 連続性ボーナス
        if uptrend_score > downtrend_score:
            consistency_bonus = min(hh * hl, 5)  # 高値と安値の両方が切り上がっている場合
        else:
            consistency_bonus = min(lh * ll, 5)  # 高値と安値の両方が切り下がっている場合
        
        strength = min(max_score * 5 + consistency_bonus, 30)
        return strength

class ZigZagIndicator:
    """ZigZagインジケータクラス"""
    
    def __init__(self, deviation: float = 0.1):
        """
        Args:
            deviation: 最小変動幅（パーセンテージ）
        """
        self.deviation = deviation / 100.0  # パーセンテージを小数に変換
    
    def calculate(self, df: pd.DataFrame) -> List[Dict]:
        """
        ZigZagを計算
        
        Args:
            df: OHLC データフレーム
            
        Returns:
            List[Dict]: ZigZagポイントのリスト
        """
        if len(df) < 3:
            return []
        
        zigzag_points = []
        
        # 最初のポイントを設定
        current_extreme = df.iloc[0]['high']
        current_direction = 'up'  # 上昇中
        current_index = 0
        
        for i in range(1, len(df)):
            high = df.iloc[i]['high']
            low = df.iloc[i]['low']
            
            if current_direction == 'up':
                # 上昇中の場合、より高い高値を探す
                if high > current_extreme:
                    current_extreme = high
                    current_index = i
                
                # 下落転換をチェック
                decline = (current_extreme - low) / current_extreme
                if decline >= self.deviation:
                    # ZigZagポイントを追加
                    zigzag_points.append({
                        'index': current_index,
                        'price': current_extreme,
                        'timestamp': df.iloc[current_index]['timestamp'],
                        'type': 'peak'
                    })
                    
                    # 方向転換
                    current_direction = 'down'
                    current_extreme = low
                    current_index = i
            
            else:  # current_direction == 'down'
                # 下降中の場合、より低い安値を探す
                if low < current_extreme:
                    current_extreme = low
                    current_index = i
                
                # 上昇転換をチェック
                rise = (high - current_extreme) / current_extreme
                if rise >= self.deviation:
                    # ZigZagポイントを追加
                    zigzag_points.append({
                        'index': current_index,
                        'price': current_extreme,
                        'timestamp': df.iloc[current_index]['timestamp'],
                        'type': 'trough'
                    })
                    
                    # 方向転換
                    current_direction = 'up'
                    current_extreme = high
                    current_index = i
        
        # 最後のポイントを追加
        if zigzag_points:
            zigzag_points.append({
                'index': current_index,
                'price': current_extreme,
                'timestamp': df.iloc[current_index]['timestamp'],
                'type': 'peak' if current_direction == 'up' else 'trough'
            })
        
        logger.info(f"ZigZag calculated: {len(zigzag_points)} points with {self.deviation*100}% deviation")
        return zigzag_points

class TechnicalAnalysisService:
    """テクニカル分析統合サービス"""
    
    def __init__(self):
        self.dow_analyzer = DowTheoryAnalyzer()
        self.zigzag = ZigZagIndicator()
    
    def analyze_market_data(self, market_data: List[Dict]) -> Dict:
        """
        市場データの包括的分析
        
        Args:
            market_data: 市場データのリスト
            
        Returns:
            Dict: 分析結果
        """
        if not market_data:
            return {'error': 'No market data provided'}
        
        # DataFrameに変換
        df = pd.DataFrame(market_data)
        
        # 必要なカラムの確認
        required_columns = ['open', 'high', 'low', 'close', 'timestamp']
        if not all(col in df.columns for col in required_columns):
            return {'error': f'Missing required columns: {required_columns}'}
        
        try:
            # スイングポイント検出
            swing_points = self.dow_analyzer.detect_swing_points(df)
            
            # トレンド分析
            trend_analysis = self.dow_analyzer.analyze_trend(swing_points)
            
            # ZigZag計算
            zigzag_points = self.zigzag.calculate(df)
            
            # 統合結果
            result = {
                'symbol': market_data[0].get('symbol', 'Unknown'),
                'analysis_timestamp': datetime.now().isoformat(),
                'data_points': len(market_data),
                'swing_points_count': len(swing_points),
                'zigzag_points_count': len(zigzag_points),
                'trend_analysis': trend_analysis,
                'swing_points': [
                    {
                        'index': sp.index,
                        'price': sp.price,
                        'timestamp': sp.timestamp,
                        'type': sp.point_type
                    } for sp in swing_points
                ],
                'zigzag_points': zigzag_points
            }
            
            logger.info(f"Technical analysis completed for {len(market_data)} data points")
            return result
            
        except Exception as e:
            logger.error(f"Error in technical analysis: {str(e)}")
            return {'error': f'Analysis failed: {str(e)}'}

# サービスインスタンス
technical_analysis_service = TechnicalAnalysisService()