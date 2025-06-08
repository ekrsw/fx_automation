"""
エリオット波動分析サービス
エリオット波動理論に基づく波動パターン検出とフィボナッチ比率分析
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import logging
from ..core.logging import get_logger

logger = get_logger(__name__)

class WavePattern:
    """波動パターンクラス"""
    def __init__(self, wave_type: str, start_index: int, end_index: int, 
                 start_price: float, end_price: float, confidence: float):
        self.wave_type = wave_type  # '1', '2', '3', '4', '5', 'A', 'B', 'C'
        self.start_index = start_index
        self.end_index = end_index
        self.start_price = start_price
        self.end_price = end_price
        self.confidence = confidence
        self.fibonacci_ratios = {}
        
    def calculate_retracement(self, previous_wave: 'WavePattern') -> float:
        """前の波に対するリトレースメント率を計算"""
        previous_move = abs(previous_wave.end_price - previous_wave.start_price)
        current_move = abs(self.end_price - self.start_price)
        if previous_move > 0:
            return current_move / previous_move
        return 0

class ElliottWaveAnalyzer:
    """エリオット波動分析クラス"""
    
    def __init__(self):
        # エリオット波動の理想的なフィボナッチ比率
        self.ideal_ratios = {
            'wave2': {'min': 0.382, 'max': 0.618, 'ideal': 0.5},      # 第2波: 38.2%-61.8%リトレース
            'wave3': {'min': 1.618, 'max': 2.618, 'ideal': 1.618},    # 第3波: 161.8%-261.8%エクステンション
            'wave4': {'min': 0.236, 'max': 0.5, 'ideal': 0.382},      # 第4波: 23.6%-50%リトレース
            'wave5': {'min': 0.618, 'max': 1.0, 'ideal': 1.0},        # 第5波: 61.8%-100%
            'waveA': {'min': 0.382, 'max': 0.618, 'ideal': 0.5},      # A波
            'waveB': {'min': 0.382, 'max': 0.886, 'ideal': 0.618},    # B波
            'waveC': {'min': 0.618, 'max': 1.618, 'ideal': 1.0}       # C波
        }
        
        # フィボナッチレベル
        self.fibonacci_levels = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.0, 2.618]
        
    def detect_elliott_waves(self, zigzag_points: List[Dict]) -> List[WavePattern]:
        """
        ZigZagポイントからエリオット波動パターンを検出
        
        Args:
            zigzag_points: ZigZagポイントのリスト
            
        Returns:
            List[WavePattern]: 検出された波動パターン
        """
        if len(zigzag_points) < 5:
            logger.warning("Insufficient ZigZag points for Elliott Wave analysis")
            return []
        
        wave_patterns = []
        
        # インパルス波（5波動）パターンを検出
        impulse_patterns = self._detect_impulse_waves(zigzag_points)
        wave_patterns.extend(impulse_patterns)
        
        # 修正波（3波動）パターンを検出
        corrective_patterns = self._detect_corrective_waves(zigzag_points)
        wave_patterns.extend(corrective_patterns)
        
        logger.info(f"Detected {len(wave_patterns)} wave patterns")
        return wave_patterns
    
    def _detect_impulse_waves(self, zigzag_points: List[Dict]) -> List[WavePattern]:
        """インパルス波（5波動）パターンの検出"""
        patterns = []
        
        # 最低8ポイント必要（上昇5波: Low-High-Low-High-Low-High-Low-High)
        if len(zigzag_points) < 8:
            return patterns
        
        # 各起点から5波動パターンを探す
        for i in range(len(zigzag_points) - 7):
            # 上昇インパルスパターンチェック
            if zigzag_points[i]['type'] == 'trough':  # 谷から始まる
                upward_pattern = self._check_upward_impulse(zigzag_points[i:i+8])
                if upward_pattern:
                    patterns.extend(upward_pattern)
            
            # 下降インパルスパターンチェック
            elif zigzag_points[i]['type'] == 'peak':  # 山から始まる
                downward_pattern = self._check_downward_impulse(zigzag_points[i:i+8])
                if downward_pattern:
                    patterns.extend(downward_pattern)
        
        return patterns
    
    def _check_upward_impulse(self, points: List[Dict]) -> Optional[List[WavePattern]]:
        """上昇インパルス波の検証"""
        if len(points) < 8:
            return None
        
        waves = []
        confidence_total = 0
        
        # 波の価格を抽出
        p0 = points[0]['price']  # 起点（谷）
        p1 = points[1]['price']  # 第1波頂点（山）
        p2 = points[2]['price']  # 第2波底（谷）
        p3 = points[3]['price']  # 第3波頂点（山）
        p4 = points[4]['price']  # 第4波底（谷）
        p5 = points[5]['price']  # 第5波頂点（山）
        
        # エリオット波動のルールチェック
        # ルール1: 第2波は第1波の起点を下回らない
        if p2 <= p0:
            return None
        
        # ルール2: 第3波は最も短くない
        wave1_length = p1 - p0
        wave3_length = p3 - p2
        wave5_length = p5 - p4
        
        if wave3_length < wave1_length and wave3_length < wave5_length:
            return None
        
        # ルール3: 第4波は第1波の頂点と重ならない
        if p4 <= p1:
            return None
        
        # フィボナッチ比率の検証と信頼度計算
        # 第1波
        wave1 = WavePattern('1', points[0]['index'], points[1]['index'], p0, p1, 0.8)
        waves.append(wave1)
        
        # 第2波のリトレースメント
        wave2_retrace = (p1 - p2) / (p1 - p0) if p1 > p0 else 0
        wave2_confidence = self._calculate_ratio_confidence(wave2_retrace, 'wave2')
        wave2 = WavePattern('2', points[1]['index'], points[2]['index'], p1, p2, wave2_confidence)
        wave2.fibonacci_ratios['retracement'] = wave2_retrace
        waves.append(wave2)
        confidence_total += wave2_confidence
        
        # 第3波のエクステンション
        wave3_extension = (p3 - p2) / (p1 - p0) if p1 > p0 else 0
        wave3_confidence = self._calculate_ratio_confidence(wave3_extension, 'wave3')
        wave3 = WavePattern('3', points[2]['index'], points[3]['index'], p2, p3, wave3_confidence)
        wave3.fibonacci_ratios['extension'] = wave3_extension
        waves.append(wave3)
        confidence_total += wave3_confidence
        
        # 第4波のリトレースメント
        wave4_retrace = (p3 - p4) / (p3 - p2) if p3 > p2 else 0
        wave4_confidence = self._calculate_ratio_confidence(wave4_retrace, 'wave4')
        wave4 = WavePattern('4', points[3]['index'], points[4]['index'], p3, p4, wave4_confidence)
        wave4.fibonacci_ratios['retracement'] = wave4_retrace
        waves.append(wave4)
        confidence_total += wave4_confidence
        
        # 第5波の長さ（第1波に対する比率）
        wave5_ratio = (p5 - p4) / (p1 - p0) if p1 > p0 else 0
        wave5_confidence = self._calculate_ratio_confidence(wave5_ratio, 'wave5')
        wave5 = WavePattern('5', points[4]['index'], points[5]['index'], p4, p5, wave5_confidence)
        wave5.fibonacci_ratios['ratio_to_wave1'] = wave5_ratio
        waves.append(wave5)
        confidence_total += wave5_confidence
        
        # 全体の信頼度が閾値以上の場合のみ返す
        average_confidence = confidence_total / 4  # 第2-5波の平均
        if average_confidence >= 0.6:
            logger.info(f"Upward impulse wave detected with confidence {average_confidence:.2f}")
            return waves
        
        return None
    
    def _check_downward_impulse(self, points: List[Dict]) -> Optional[List[WavePattern]]:
        """下降インパルス波の検証"""
        if len(points) < 8:
            return None
        
        waves = []
        confidence_total = 0
        
        # 波の価格を抽出
        p0 = points[0]['price']  # 起点（山）
        p1 = points[1]['price']  # 第1波底（谷）
        p2 = points[2]['price']  # 第2波頂点（山）
        p3 = points[3]['price']  # 第3波底（谷）
        p4 = points[4]['price']  # 第4波頂点（山）
        p5 = points[5]['price']  # 第5波底（谷）
        
        # エリオット波動のルールチェック（下降版）
        # ルール1: 第2波は第1波の起点を上回らない
        if p2 >= p0:
            return None
        
        # ルール2: 第3波は最も短くない
        wave1_length = p0 - p1
        wave3_length = p2 - p3
        wave5_length = p4 - p5
        
        if wave3_length < wave1_length and wave3_length < wave5_length:
            return None
        
        # ルール3: 第4波は第1波の底と重ならない
        if p4 >= p1:
            return None
        
        # フィボナッチ比率の検証（下降版）
        # 第1波
        wave1 = WavePattern('1', points[0]['index'], points[1]['index'], p0, p1, 0.8)
        waves.append(wave1)
        
        # 第2波のリトレースメント
        wave2_retrace = (p2 - p1) / (p0 - p1) if p0 > p1 else 0
        wave2_confidence = self._calculate_ratio_confidence(wave2_retrace, 'wave2')
        wave2 = WavePattern('2', points[1]['index'], points[2]['index'], p1, p2, wave2_confidence)
        wave2.fibonacci_ratios['retracement'] = wave2_retrace
        waves.append(wave2)
        confidence_total += wave2_confidence
        
        # 第3波のエクステンション
        wave3_extension = (p2 - p3) / (p0 - p1) if p0 > p1 else 0
        wave3_confidence = self._calculate_ratio_confidence(wave3_extension, 'wave3')
        wave3 = WavePattern('3', points[2]['index'], points[3]['index'], p2, p3, wave3_confidence)
        wave3.fibonacci_ratios['extension'] = wave3_extension
        waves.append(wave3)
        confidence_total += wave3_confidence
        
        # 第4波のリトレースメント
        wave4_retrace = (p4 - p3) / (p2 - p3) if p2 > p3 else 0
        wave4_confidence = self._calculate_ratio_confidence(wave4_retrace, 'wave4')
        wave4 = WavePattern('4', points[3]['index'], points[4]['index'], p3, p4, wave4_confidence)
        wave4.fibonacci_ratios['retracement'] = wave4_retrace
        waves.append(wave4)
        confidence_total += wave4_confidence
        
        # 第5波の長さ
        wave5_ratio = (p4 - p5) / (p0 - p1) if p0 > p1 else 0
        wave5_confidence = self._calculate_ratio_confidence(wave5_ratio, 'wave5')
        wave5 = WavePattern('5', points[4]['index'], points[5]['index'], p4, p5, wave5_confidence)
        wave5.fibonacci_ratios['ratio_to_wave1'] = wave5_ratio
        waves.append(wave5)
        confidence_total += wave5_confidence
        
        # 全体の信頼度チェック
        average_confidence = confidence_total / 4
        if average_confidence >= 0.6:
            logger.info(f"Downward impulse wave detected with confidence {average_confidence:.2f}")
            return waves
        
        return None
    
    def _detect_corrective_waves(self, zigzag_points: List[Dict]) -> List[WavePattern]:
        """修正波（ABC）パターンの検出"""
        patterns = []
        
        # 最低4ポイント必要
        if len(zigzag_points) < 4:
            return patterns
        
        for i in range(len(zigzag_points) - 3):
            # 上昇修正波チェック
            if zigzag_points[i]['type'] == 'trough':
                upward_correction = self._check_corrective_pattern(zigzag_points[i:i+4], 'up')
                if upward_correction:
                    patterns.extend(upward_correction)
            
            # 下降修正波チェック
            elif zigzag_points[i]['type'] == 'peak':
                downward_correction = self._check_corrective_pattern(zigzag_points[i:i+4], 'down')
                if downward_correction:
                    patterns.extend(downward_correction)
        
        return patterns
    
    def _check_corrective_pattern(self, points: List[Dict], direction: str) -> Optional[List[WavePattern]]:
        """修正波パターンの検証"""
        if len(points) < 4:
            return None
        
        waves = []
        
        p0 = points[0]['price']
        p1 = points[1]['price']
        p2 = points[2]['price']
        p3 = points[3]['price']
        
        if direction == 'up':
            # A波
            waveA = WavePattern('A', points[0]['index'], points[1]['index'], p0, p1, 0.7)
            waves.append(waveA)
            
            # B波のリトレースメント
            waveB_retrace = (p1 - p2) / (p1 - p0) if p1 > p0 else 0
            waveB_confidence = self._calculate_ratio_confidence(waveB_retrace, 'waveB')
            waveB = WavePattern('B', points[1]['index'], points[2]['index'], p1, p2, waveB_confidence)
            waveB.fibonacci_ratios['retracement'] = waveB_retrace
            waves.append(waveB)
            
            # C波
            waveC_ratio = (p3 - p2) / (p1 - p0) if p1 > p0 else 0
            waveC_confidence = self._calculate_ratio_confidence(waveC_ratio, 'waveC')
            waveC = WavePattern('C', points[2]['index'], points[3]['index'], p2, p3, waveC_confidence)
            waveC.fibonacci_ratios['ratio_to_waveA'] = waveC_ratio
            waves.append(waveC)
            
        else:  # down
            # A波（下降）
            waveA = WavePattern('A', points[0]['index'], points[1]['index'], p0, p1, 0.7)
            waves.append(waveA)
            
            # B波のリトレースメント
            waveB_retrace = (p2 - p1) / (p0 - p1) if p0 > p1 else 0
            waveB_confidence = self._calculate_ratio_confidence(waveB_retrace, 'waveB')
            waveB = WavePattern('B', points[1]['index'], points[2]['index'], p1, p2, waveB_confidence)
            waveB.fibonacci_ratios['retracement'] = waveB_retrace
            waves.append(waveB)
            
            # C波
            waveC_ratio = (p2 - p3) / (p0 - p1) if p0 > p1 else 0
            waveC_confidence = self._calculate_ratio_confidence(waveC_ratio, 'waveC')
            waveC = WavePattern('C', points[2]['index'], points[3]['index'], p2, p3, waveC_confidence)
            waveC.fibonacci_ratios['ratio_to_waveA'] = waveC_ratio
            waves.append(waveC)
        
        # 平均信頼度チェック
        average_confidence = (waveB_confidence + waveC_confidence) / 2
        if average_confidence >= 0.5:
            return waves
        
        return None
    
    def _calculate_ratio_confidence(self, actual_ratio: float, wave_type: str) -> float:
        """フィボナッチ比率の信頼度を計算"""
        if wave_type not in self.ideal_ratios:
            return 0.5
        
        ideal_range = self.ideal_ratios[wave_type]
        ideal = ideal_range['ideal']
        min_val = ideal_range['min']
        max_val = ideal_range['max']
        
        # 理想値からの乖離度を計算
        if min_val <= actual_ratio <= max_val:
            # 範囲内の場合
            deviation = abs(actual_ratio - ideal) / (max_val - min_val)
            confidence = 1.0 - (deviation * 0.5)  # 最大50%減点
        else:
            # 範囲外の場合
            if actual_ratio < min_val:
                deviation = (min_val - actual_ratio) / min_val
            else:
                deviation = (actual_ratio - max_val) / max_val
            confidence = max(0.3, 0.7 - deviation)  # 最低30%
        
        return confidence
    
    def calculate_fibonacci_retracements(self, high: float, low: float) -> Dict[float, float]:
        """
        フィボナッチリトレースメントレベルを計算
        
        Args:
            high: 高値
            low: 安値
            
        Returns:
            Dict: フィボナッチレベルと価格
        """
        diff = high - low
        levels = {}
        
        for level in self.fibonacci_levels:
            if level <= 1.0:  # リトレースメント
                price = high - (diff * level)
            else:  # エクステンション
                price = low + (diff * level)
            levels[level] = price
        
        return levels
    
    def calculate_fibonacci_projections(self, wave1_start: float, wave1_end: float, 
                                      wave2_end: float) -> Dict[float, float]:
        """
        フィボナッチプロジェクション（目標値）を計算
        
        Args:
            wave1_start: 第1波の開始価格
            wave1_end: 第1波の終了価格
            wave2_end: 第2波の終了価格
            
        Returns:
            Dict: プロジェクションレベルと価格
        """
        wave1_length = abs(wave1_end - wave1_start)
        projections = {}
        
        projection_levels = [0.618, 1.0, 1.272, 1.618, 2.0, 2.618]
        
        for level in projection_levels:
            if wave1_end > wave1_start:  # 上昇波
                price = wave2_end + (wave1_length * level)
            else:  # 下降波
                price = wave2_end - (wave1_length * level)
            projections[level] = price
        
        return projections
    
    def get_current_wave_position(self, wave_patterns: List[WavePattern]) -> Dict:
        """
        現在の波動位置を判定
        
        Args:
            wave_patterns: 検出された波動パターン
            
        Returns:
            Dict: 現在の波動位置情報
        """
        if not wave_patterns:
            return {
                'current_wave': None,
                'wave_type': None,
                'confidence': 0,
                'next_target': None
            }
        
        # 最新の波動パターンを取得
        latest_pattern = max(wave_patterns, key=lambda x: x.end_index)
        
        # 波動タイプに応じたスコアリング
        wave_scores = {
            '1': 30,  # 第1波
            '2': 10,  # 第2波（調整）
            '3': 40,  # 第3波（最強）
            '4': 10,  # 第4波（調整）
            '5': 20,  # 第5波
            'A': 15,  # A波
            'B': 10,  # B波
            'C': 15   # C波
        }
        
        score = wave_scores.get(latest_pattern.wave_type, 10)
        
        # 次の目標値を計算
        next_target = None
        if latest_pattern.wave_type == '3':
            # 第3波の場合、1.618エクステンションを目標
            wave_length = abs(latest_pattern.end_price - latest_pattern.start_price)
            if latest_pattern.end_price > latest_pattern.start_price:
                next_target = latest_pattern.start_price + (wave_length * 1.618)
            else:
                next_target = latest_pattern.start_price - (wave_length * 1.618)
        
        return {
            'current_wave': latest_pattern.wave_type,
            'wave_type': 'impulse' if latest_pattern.wave_type in ['1','2','3','4','5'] else 'corrective',
            'confidence': latest_pattern.confidence,
            'score': score,
            'next_target': next_target,
            'fibonacci_ratios': latest_pattern.fibonacci_ratios
        }

# サービスインスタンス
elliott_wave_analyzer = ElliottWaveAnalyzer()