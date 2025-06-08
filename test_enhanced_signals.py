#!/usr/bin/env python3
"""
強化されたシグナル生成コンポーネントのテストスクリプト
"""

import sys
import os
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# パスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.elliott_wave_analyzer import ElliottWaveAnalyzer
from app.services.enhanced_signal_generator import EnhancedSignalGenerator
from app.services.technical_analysis import TechnicalAnalysisService, ZigZagIndicator

def generate_sample_data(symbol: str = 'USDJPY', bars: int = 200) -> pd.DataFrame:
    """サンプルデータを生成"""
    # 基準日時
    start_date = datetime.now() - timedelta(days=bars//4)  # 5分足を想定
    
    # 価格データを生成（ランダムウォーク + トレンド）
    base_price = 150.0 if symbol == 'USDJPY' else 1.1000
    
    dates = [start_date + timedelta(minutes=5*i) for i in range(bars)]
    
    # トレンドとボラティリティを設定
    trend = 0.0001  # 微小な上昇トレンド
    volatility = 0.002
    
    prices = [base_price]
    for i in range(1, bars):
        # ランダムウォーク + トレンド
        change = np.random.normal(trend, volatility)
        prices.append(prices[-1] * (1 + change))
    
    # OHLC データを生成
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        # 簡易的なOHLCを生成
        noise = np.random.uniform(-0.0005, 0.0005)
        high = close * (1 + abs(noise))
        low = close * (1 - abs(noise))
        open_price = prices[i-1] if i > 0 else close
        
        data.append({
            'timestamp': date.isoformat(),
            'symbol': symbol,
            'open': round(open_price, 5),
            'high': round(high, 5),
            'low': round(low, 5),
            'close': round(close, 5),
            'volume': np.random.randint(100, 1000)
        })
    
    return pd.DataFrame(data)

def test_elliott_wave_analyzer():
    """エリオット波動分析のテスト"""
    print("=== エリオット波動分析テスト ===")
    
    analyzer = ElliottWaveAnalyzer()
    
    # サンプルデータを生成
    data = generate_sample_data()
    print(f"Generated {len(data)} sample data points")
    
    # ZigZag計算
    zigzag = ZigZagIndicator(deviation=0.5)  # 0.5%の変動
    zigzag_points = zigzag.calculate(data)
    print(f"ZigZag points detected: {len(zigzag_points)}")
    
    if len(zigzag_points) >= 5:
        # エリオット波動パターン検出
        wave_patterns = analyzer.detect_elliott_waves(zigzag_points)
        print(f"Wave patterns detected: {len(wave_patterns)}")
        
        for i, pattern in enumerate(wave_patterns[:5]):  # 最初の5パターン表示
            print(f"  Pattern {i+1}: Wave {pattern.wave_type}, "
                  f"Confidence: {pattern.confidence:.2f}, "
                  f"Price: {pattern.start_price:.5f} -> {pattern.end_price:.5f}")
        
        # 現在の波動位置
        current_position = analyzer.get_current_wave_position(wave_patterns)
        print(f"Current wave position: {current_position}")
        
        # フィボナッチ計算テスト
        if len(zigzag_points) >= 3:
            high = max(point['price'] for point in zigzag_points[-3:])
            low = min(point['price'] for point in zigzag_points[-3:])
            
            retracements = analyzer.calculate_fibonacci_retracements(high, low)
            print(f"Fibonacci retracements (High: {high:.5f}, Low: {low:.5f}):")
            for level, price in list(retracements.items())[:5]:
                print(f"  {level*100:.1f}%: {price:.5f}")
    else:
        print("Insufficient ZigZag points for Elliott Wave analysis")

def test_enhanced_signal_generator():
    """強化されたシグナル生成のテスト"""
    print("\n=== 強化されたシグナル生成テスト ===")
    
    # モックDBマネージャーを作成
    class MockDBManager:
        def __init__(self, data):
            self.data = data
            
        def get_latest_market_data(self, symbol, count):
            return self.data.to_dict('records')[-count:]
    
    # サンプルデータ
    data = generate_sample_data('USDJPY', 300)
    
    # 一時的にdb_managerを差し替え
    import app.core.database as db_module
    original_db = db_module.db_manager
    db_module.db_manager = MockDBManager(data)
    
    try:
        generator = EnhancedSignalGenerator()
        
        # シグナル生成テスト
        signal = generator.generate_comprehensive_signal('USDJPY', 'H4')
        
        if 'error' in signal:
            print(f"Error: {signal['error']}")
        else:
            print(f"Symbol: {signal['symbol']}")
            print(f"Total Score: {signal['score']}")
            print(f"Score Breakdown:")
            for component, score in signal['score_breakdown'].items():
                print(f"  {component}: {score}")
            
            print(f"Signal: {signal['signal']['action']} (Strength: {signal['signal']['strength']})")
            print(f"Recommendation: {signal['recommendation']}")
            
            # マルチタイムフレーム分析結果
            print(f"Multi-timeframe analysis available for: {list(signal['multi_timeframe_analysis'].keys())}")
    
    finally:
        # 元のdb_managerに戻す
        db_module.db_manager = original_db

def test_integration():
    """統合テスト"""
    print("\n=== 統合テスト ===")
    
    # バックテストエンジンでの使用テスト
    from app.services.backtest_engine import BacktestEngine
    
    engine = BacktestEngine()
    
    # サンプルデータでテスト
    data = generate_sample_data('USDJPY', 150)
    
    # スイングシグナル生成テスト
    parameters = {
        'strategy_type': 'swing',
        'symbol': 'USDJPY',
        'swing_entry_threshold': 60
    }
    
    async def test_signal():
        signal = await engine._generate_swing_signal(data, parameters)
        print(f"Backtest signal: {signal['action']} with score {signal['score']}")
        if 'analysis' in signal and 'score_breakdown' in signal['analysis']:
            print(f"Score breakdown: {signal['analysis']['score_breakdown']}")
        return signal
    
    # 非同期実行
    signal = asyncio.run(test_signal())
    
    print("\n=== テスト完了 ===")
    return signal

if __name__ == "__main__":
    print("強化されたシグナル生成コンポーネントのテスト開始")
    print("=" * 50)
    
    # 各コンポーネントのテスト
    test_elliott_wave_analyzer()
    test_enhanced_signal_generator()
    test_integration()
    
    print("\nすべてのテストが完了しました。")