"""
バックテストエンジン
過去データを使用した取引戦略の検証を実行
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging

from app.core.database import get_db_connection
from app.services.technical_analysis import TechnicalAnalysisService
from app.services.risk_management import RiskManager

logger = logging.getLogger(__name__)

class BacktestEngine:
    def __init__(self):
        self.technical_service = TechnicalAnalysisService()
        self.risk_service = RiskManager()
        
    async def run_backtest(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        parameters: Dict[str, Any],
        initial_balance: float = 100000.0,
        risk_per_trade: float = 0.02,
        max_positions: int = 3
    ) -> Dict[str, Any]:
        """
        バックテストを実行
        """
        try:
            # 市場データを取得
            market_data = await self._get_market_data(symbol, start_date, end_date)
            
            if len(market_data) < 20:  # スキャルピング戦略では少ないデータでもテスト可能
                raise ValueError(f"データが不足しています: {len(market_data)}件")
            
            # バックテスト実行
            result = await self._execute_backtest(
                market_data,
                parameters,
                initial_balance,
                risk_per_trade,
                max_positions
            )
            
            return result
            
        except Exception as e:
            logger.error(f"バックテスト実行エラー: {str(e)}")
            raise
    
    async def _get_market_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        指定期間の市場データを取得
        """
        try:
            conn = get_db_connection()
            
            # Handle mixed timestamp formats by using a more flexible query
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM market_data
                WHERE symbol = ?
                ORDER BY timestamp
            """
            
            df = pd.read_sql_query(query, conn, params=(symbol,))
            conn.close()
            
            if df.empty:
                raise ValueError(f"指定期間のデータが見つかりません: {symbol} ({start_date} - {end_date})")
            
            # データタイプを調整（混在する形式に対応）
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce')
            df = df.set_index('timestamp')
            
            # 日付範囲でフィルタリング
            start_dt = pd.to_datetime(start_date, format='mixed', errors='coerce')
            end_dt = pd.to_datetime(end_date, format='mixed', errors='coerce')
            
            logger.info(f"データフィルタリング前: {len(df)}件")
            logger.info(f"要求期間: {start_date} - {end_date}")
            logger.info(f"変換後期間: {start_dt} - {end_dt}")
            logger.info(f"データ範囲: {df.index.min()} - {df.index.max()}")
            
            if not pd.isna(start_dt) and not pd.isna(end_dt):
                df = df[(df.index >= start_dt) & (df.index <= end_dt)]
                logger.info(f"フィルタリング後: {len(df)}件")
            
            # 数値型に変換
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 欠損値を削除
            df = df.dropna()
            
            logger.info(f"市場データ取得完了: {len(df)}件 ({symbol})")
            return df
            
        except Exception as e:
            logger.error(f"市場データ取得エラー: {str(e)}")
            raise
    
    async def _execute_backtest(
        self,
        data: pd.DataFrame,
        parameters: Dict[str, Any],
        initial_balance: float,
        risk_per_trade: float,
        max_positions: int
    ) -> Dict[str, Any]:
        """
        バックテストのメイン実行ロジック
        """
        try:
            # 初期設定
            balance = initial_balance
            positions = []
            trades = []
            equity_curve = []
            
            # テクニカル指標を計算
            data = await self._calculate_technical_indicators(data, parameters)
            
            # 各時点でのシミュレーション
            start_index = min(10, len(data) - 5)  # スキャルピング用に開始を早める
            logger.info(f"バックテスト開始インデックス: {start_index}, 総データ数: {len(data)}")
            
            for i in range(start_index, len(data)):
                current_time = data.index[i]
                current_data = data.iloc[:i+1]  # 現在までのデータ
                current_price = data.iloc[i]
                
                # エントリーシグナルをチェック
                if len(positions) < max_positions:
                    signal = await self._generate_signal(current_data, parameters)
                    
                    if signal['action'] == 'buy' or signal['action'] == 'sell':
                        # ポジションサイズを計算
                        position_size = self._calculate_position_size(
                            balance, 
                            current_price['close'], 
                            signal.get('stop_loss', current_price['close'] * 0.98),
                            risk_per_trade
                        )
                        
                        if position_size > 0:
                            # 新しいポジションを開始
                            position = {
                                'symbol': data.columns[0] if len(data.columns) > 0 else 'UNKNOWN',
                                'side': signal['action'],
                                'entry_time': current_time,
                                'entry_price': current_price['close'],
                                'quantity': position_size,
                                'stop_loss': signal.get('stop_loss'),
                                'take_profit': signal.get('take_profit'),
                                'score': signal.get('score', 50)
                            }
                            positions.append(position)
                
                # 既存ポジションの管理
                positions_to_close = []
                
                for pos_idx, position in enumerate(positions):
                    should_close, exit_reason = await self._should_close_position(
                        position, current_price, current_data, parameters
                    )
                    
                    if should_close:
                        # ポジションを決済
                        exit_price = current_price['close']
                        
                        if position['side'] == 'buy':
                            profit = (exit_price - position['entry_price']) * position['quantity']
                        else:  # sell
                            profit = (position['entry_price'] - exit_price) * position['quantity']
                        
                        trade = {
                            'symbol': position['symbol'],
                            'side': position['side'],
                            'entry_time': position['entry_time'].isoformat(),
                            'exit_time': current_time.isoformat(),
                            'entry_price': position['entry_price'],
                            'exit_price': exit_price,
                            'quantity': position['quantity'],
                            'profit_loss': profit,
                            'exit_reason': exit_reason
                        }
                        
                        trades.append(trade)
                        balance += profit
                        positions_to_close.append(pos_idx)
                
                # 決済したポジションを削除
                for idx in sorted(positions_to_close, reverse=True):
                    positions.pop(idx)
                
                # エクイティカーブを記録
                unrealized_pnl = self._calculate_unrealized_pnl(positions, current_price)
                equity_curve.append({
                    'timestamp': current_time,
                    'balance': balance,
                    'unrealized_pnl': unrealized_pnl,
                    'total_equity': balance + unrealized_pnl
                })
            
            # 残りのポジションを強制決済
            final_price = data.iloc[-1]
            for position in positions:
                if position['side'] == 'buy':
                    profit = (final_price['close'] - position['entry_price']) * position['quantity']
                else:
                    profit = (position['entry_price'] - final_price['close']) * position['quantity']
                
                trade = {
                    'symbol': position['symbol'],
                    'side': position['side'],
                    'entry_time': position['entry_time'].isoformat(),
                    'exit_time': data.index[-1].isoformat(),
                    'entry_price': position['entry_price'],
                    'exit_price': final_price['close'],
                    'quantity': position['quantity'],
                    'profit_loss': profit,
                    'exit_reason': 'backtest_end'
                }
                
                trades.append(trade)
                balance += profit
            
            # 結果を分析
            analysis = self._analyze_results(trades, equity_curve, initial_balance)
            
            return analysis
            
        except Exception as e:
            logger.error(f"バックテスト実行エラー: {str(e)}")
            raise
    
    async def _calculate_technical_indicators(self, data: pd.DataFrame, parameters: Dict[str, Any]) -> pd.DataFrame:
        """
        テクニカル指標を計算
        """
        try:
            # 移動平均
            ma_period = parameters.get('ma_period', 20)
            data['ma'] = data['close'].rolling(window=ma_period).mean()
            
            # RSI
            rsi_period = parameters.get('rsi_period', 14)
            data['rsi'] = self._calculate_rsi(data['close'], rsi_period)
            
            # ボリンジャーバンド
            bb_period = parameters.get('bb_period', 20)
            bb_std = parameters.get('bb_std', 2)
            data['bb_upper'], data['bb_lower'] = self._calculate_bollinger_bands(
                data['close'], bb_period, bb_std
            )
            
            # ATR (Average True Range)
            atr_period = parameters.get('atr_period', 14)
            data['atr'] = self._calculate_atr(data, atr_period)
            
            # ダウ理論関連
            swing_threshold = parameters.get('swing_threshold', 0.5)
            data = await self._calculate_dow_theory_signals(data, swing_threshold)
            
            return data
            
        except Exception as e:
            logger.error(f"テクニカル指標計算エラー: {str(e)}")
            return data
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """RSIを計算"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2) -> Tuple[pd.Series, pd.Series]:
        """ボリンジャーバンドを計算"""
        ma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = ma + (std * std_dev)
        lower = ma - (std * std_dev)
        return upper, lower
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """ATRを計算"""
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift())
        low_close = np.abs(data['low'] - data['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        return atr
    
    async def _calculate_dow_theory_signals(self, data: pd.DataFrame, threshold: float) -> pd.DataFrame:
        """
        ダウ理論に基づくシグナルを計算
        """
        try:
            # スイングポイントを検出
            data['swing_high'] = False
            data['swing_low'] = False
            
            window = 5  # 前後5本のローソク足でスイングポイントを判定
            
            for i in range(window, len(data) - window):
                # スイングハイの判定
                is_swing_high = True
                for j in range(i - window, i + window + 1):
                    if j != i and data.iloc[j]['high'] >= data.iloc[i]['high']:
                        is_swing_high = False
                        break
                
                if is_swing_high:
                    data.iloc[i, data.columns.get_loc('swing_high')] = True
                
                # スイングローの判定
                is_swing_low = True
                for j in range(i - window, i + window + 1):
                    if j != i and data.iloc[j]['low'] <= data.iloc[i]['low']:
                        is_swing_low = False
                        break
                
                if is_swing_low:
                    data.iloc[i, data.columns.get_loc('swing_low')] = True
            
            # トレンド方向を判定
            data['trend'] = 0  # 0: 横ばい, 1: 上昇, -1: 下降
            
            swing_highs = data[data['swing_high']]['high']
            swing_lows = data[data['swing_low']]['low']
            
            # 最近のスイングポイントからトレンドを判定
            if len(swing_highs) >= 2 and len(swing_lows) >= 2:
                recent_highs = swing_highs.tail(2)
                recent_lows = swing_lows.tail(2)
                
                if len(recent_highs) >= 2 and recent_highs.iloc[-1] > recent_highs.iloc[-2]:
                    if len(recent_lows) >= 2 and recent_lows.iloc[-1] > recent_lows.iloc[-2]:
                        data.iloc[-50:, data.columns.get_loc('trend')] = 1  # 上昇トレンド
                
                if len(recent_highs) >= 2 and recent_highs.iloc[-1] < recent_highs.iloc[-2]:
                    if len(recent_lows) >= 2 and recent_lows.iloc[-1] < recent_lows.iloc[-2]:
                        data.iloc[-50:, data.columns.get_loc('trend')] = -1  # 下降トレンド
            
            return data
            
        except Exception as e:
            logger.error(f"ダウ理論シグナル計算エラー: {str(e)}")
            return data
    
    async def _generate_signal(self, data: pd.DataFrame, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        エントリーシグナルを生成（戦略選択対応）
        """
        try:
            # 戦略タイプを取得（デフォルトはスキャルピング）
            strategy_type = parameters.get('strategy_type', 'scalping')
            
            if strategy_type == 'swing':
                return await self._generate_swing_signal(data, parameters)
            else:
                return await self._generate_scalping_signal(data, parameters)
                
        except Exception as e:
            logger.error(f"シグナル生成エラー: {str(e)}")
            return {'action': 'hold', 'score': 0}
    
    async def _generate_swing_signal(self, data: pd.DataFrame, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        スイングトレード戦略のシグナル生成
        ダウ理論とエリオット波動を活用
        """
        try:
            signal = {
                'action': 'hold',
                'score': 0,
                'stop_loss': None,
                'take_profit': None,
                'analysis': {}
            }
            
            # 最低限必要なデータ数チェック
            if len(data) < 50:
                return signal
            
            # ダウ理論によるトレンド分析
            market_data_list = data.reset_index().to_dict('records')
            for record in market_data_list:
                record['timestamp'] = record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            
            analysis_result = self.technical_service.analyze_market_data(market_data_list)
            
            if 'error' in analysis_result:
                logger.error(f"Technical analysis error: {analysis_result['error']}")
                return signal
            
            trend_analysis = analysis_result.get('trend_analysis', {})
            swing_points = analysis_result.get('swing_points', [])
            
            # トレンド判定
            trend = trend_analysis.get('trend', 'sideways')
            trend_strength = trend_analysis.get('strength', 0)
            
            # 最新価格
            current = data.iloc[-1]
            current_price = current['close']
            
            # スコア計算
            score = 0
            
            # 1. トレンド強度（0-30点）
            score += trend_strength
            
            # 2. トレンド方向の確認（+/-20点）
            if trend == 'uptrend':
                score += 20
            elif trend == 'downtrend':
                score -= 20
            
            # 3. 直近のスイングポイントとの位置関係（+/-30点）
            if swing_points:
                recent_highs = [sp for sp in swing_points[-10:] if sp['type'] == 'high']
                recent_lows = [sp for sp in swing_points[-10:] if sp['type'] == 'low']
                
                if recent_lows:
                    last_low = recent_lows[-1]['price']
                    # 直近安値からの上昇率
                    rise_from_low = (current_price - last_low) / last_low
                    
                    if trend == 'uptrend' and 0.001 < rise_from_low < 0.01:  # 0.1%～1%の上昇
                        score += 30  # 押し目買いチャンス
                    elif trend == 'downtrend' and rise_from_low > 0.01:
                        score -= 20  # 下降トレンドでの戻りは売りシグナル
                
                if recent_highs:
                    last_high = recent_highs[-1]['price']
                    # 直近高値からの下落率
                    fall_from_high = (last_high - current_price) / last_high
                    
                    if trend == 'downtrend' and 0.001 < fall_from_high < 0.01:  # 0.1%～1%の下落
                        score -= 30  # 戻り売りチャンス
                    elif trend == 'uptrend' and fall_from_high > 0.01:
                        score += 20  # 上昇トレンドでの押し目は買いシグナル
            
            # 4. RSIによる過熱感チェック（+/-20点）
            if 'rsi' in current and not pd.isna(current['rsi']):
                rsi = current['rsi']
                if rsi < 30 and trend == 'uptrend':
                    score += 20  # 売られすぎからの反発期待
                elif rsi > 70 and trend == 'downtrend':
                    score -= 20  # 買われすぎからの下落期待
                elif 30 <= rsi <= 50 and trend == 'uptrend':
                    score += 10  # 適正レンジでの上昇トレンド
                elif 50 <= rsi <= 70 and trend == 'downtrend':
                    score -= 10  # 適正レンジでの下降トレンド
            
            # 5. ボラティリティチェック（ATRベース）
            if 'atr' in current and not pd.isna(current['atr']):
                atr = current['atr']
                atr_ratio = atr / current_price
                
                # 適度なボラティリティ（0.2%～1%）を好む
                if 0.002 < atr_ratio < 0.01:
                    score = int(score * 1.2)  # 20%ボーナス
                elif atr_ratio > 0.02:
                    score = int(score * 0.7)  # 高ボラティリティはリスク
            
            # シグナル判定
            entry_threshold = parameters.get('swing_entry_threshold', 60)
            
            if score >= entry_threshold:
                signal['action'] = 'buy'
                signal['score'] = score
                
                # ストップロスとテイクプロフィット設定
                if recent_lows:
                    # 直近スイングローの少し下にストップロス
                    signal['stop_loss'] = recent_lows[-1]['price'] * 0.998
                else:
                    # ATRベースのストップロス（2ATR）
                    if 'atr' in current:
                        signal['stop_loss'] = current_price - (current['atr'] * 2)
                    else:
                        signal['stop_loss'] = current_price * 0.99  # 1%下
                
                # リスクリワード比 1:2
                risk = current_price - signal['stop_loss']
                signal['take_profit'] = current_price + (risk * 2)
                
            elif score <= -entry_threshold:
                signal['action'] = 'sell'
                signal['score'] = abs(score)
                
                # ストップロスとテイクプロフィット設定
                if recent_highs:
                    # 直近スイングハイの少し上にストップロス
                    signal['stop_loss'] = recent_highs[-1]['price'] * 1.002
                else:
                    # ATRベースのストップロス（2ATR）
                    if 'atr' in current:
                        signal['stop_loss'] = current_price + (current['atr'] * 2)
                    else:
                        signal['stop_loss'] = current_price * 1.01  # 1%上
                
                # リスクリワード比 1:2
                risk = signal['stop_loss'] - current_price
                signal['take_profit'] = current_price - (risk * 2)
            
            # 分析情報を追加
            signal['analysis'] = {
                'trend': trend,
                'trend_strength': trend_strength,
                'swing_points_count': len(swing_points),
                'last_high': recent_highs[-1]['price'] if recent_highs else None,
                'last_low': recent_lows[-1]['price'] if recent_lows else None,
                'rsi': current.get('rsi'),
                'atr': current.get('atr')
            }
            
            if signal['action'] != 'hold':
                logger.info(f"Swing signal generated: {signal['action']} with score {signal['score']}")
                logger.info(f"Analysis: {signal['analysis']}")
            
            return signal
            
        except Exception as e:
            logger.error(f"スイングシグナル生成エラー: {str(e)}")
            return {'action': 'hold', 'score': 0}
    
    async def _generate_scalping_signal(self, data: pd.DataFrame, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        スキャルピング戦略のシグナル生成（既存のロジック）
        """
        try:
            current = data.iloc[-1]
            prev = data.iloc[-2] if len(data) > 1 else current
            
            signal = {
                'action': 'hold',
                'score': 0,
                'stop_loss': None,
                'take_profit': None
            }
            
            # 高頻度スキャルピング戦略
            score = 0
            
            # 短期価格変動ベースの高頻度戦略
            if len(data) >= 5:
                # 直近5期間の価格変動を分析
                recent_prices = data['close'].tail(5)
                short_ma = recent_prices.mean()
                current_price_val = current['close']
                
                # 短期移動平均からの乖離率
                ma_deviation = (current_price_val - short_ma) / short_ma
                
                # 直前の価格変動（スキャルピング用の小さな値）
                price_change = (current['close'] - prev['close']) / prev['close']
                
                # ボラティリティ（直近5期間の標準偏差）
                volatility = recent_prices.std() / recent_prices.mean()
                
                # 厳選された取引条件（質重視のスキャルピング）
                # 0.05%以上の明確な変動で反応（より厳格に）
                if price_change > 0.0005:  # 0.05%上昇
                    score += 50
                elif price_change < -0.0005:  # 0.05%下落  
                    score -= 50
                
                # 移動平均乖離による追加シグナル（より厳格に）
                if ma_deviation > 0.0008:  # 0.08%以上上乖離
                    score += 25
                elif ma_deviation < -0.0008:  # 0.08%以上下乖離
                    score -= 25
                
                # 勢いの継続性チェック（連続する方向性）
                if len(data) >= 3:
                    prev_change = (prev['close'] - data['close'].iloc[-3]) / data['close'].iloc[-3]
                    if price_change > 0 and prev_change > 0:  # 連続上昇
                        score += 15
                    elif price_change < 0 and prev_change < 0:  # 連続下落
                        score -= 15
                
                # ボラティリティフィルター（適度なボラティリティのみ）
                if 0.0008 < volatility < 0.003:  # 適度なボラティリティ範囲
                    score = int(score * 1.2)  # 1.2倍に調整
                elif volatility > 0.005:  # 過度なボラティリティは減点
                    score = int(score * 0.8)
            
            # RSIがある場合はそれも考慮
            if not pd.isna(current.get('rsi', float('nan'))):
                if current['rsi'] < 40:  # 売られすぎ
                    score += 20
                elif current['rsi'] > 60:  # 買われすぎ
                    score -= 20
            
            # 移動平均との関係
            if not pd.isna(current.get('ma', float('nan'))):
                if current['close'] > current['ma']:
                    score += 10
                elif current['close'] < current['ma']:
                    score -= 10
            
            logger.info(f"Signal debug - Price change: {price_change if len(data) >= 2 else 'N/A'}, Score: {score}, RSI: {current.get('rsi', 'N/A')}, MA: {current.get('ma', 'N/A')}, Close: {current['close']}")
            
            # シグナル判定
            entry_threshold = parameters.get('entry_threshold', 50)
            
            if score >= entry_threshold:
                signal['action'] = 'buy'
                signal['score'] = score
                # スプレッド考慮の改善されたリスク・リワード比 1:6 (SL:0.05%, TP:0.30%)
                signal['stop_loss'] = current['close'] * 0.9995  # 0.05%のストップロス
                signal['take_profit'] = current['close'] * 1.0030  # 0.30%のテイクプロフィット
                logger.info(f"BUY signal generated - Score: {score}, Entry: {current['close']}, SL: {signal['stop_loss']:.5f}, TP: {signal['take_profit']:.5f}")
                
            elif score <= -entry_threshold:
                signal['action'] = 'sell'
                signal['score'] = abs(score)
                signal['stop_loss'] = current['close'] * 1.0005  # 0.05%のストップロス
                signal['take_profit'] = current['close'] * 0.9970  # 0.30%のテイクプロフィット
                logger.info(f"SELL signal generated - Score: {score}, Entry: {current['close']}, SL: {signal['stop_loss']:.5f}, TP: {signal['take_profit']:.5f}")
            
            return signal
            
        except Exception as e:
            logger.error(f"シグナル生成エラー: {str(e)}")
            return {'action': 'hold', 'score': 0}
    
    def _calculate_position_size(self, balance: float, entry_price: float, stop_loss: float, risk_per_trade: float) -> float:
        """
        ポジションサイズを計算
        """
        try:
            risk_amount = balance * risk_per_trade
            price_diff = abs(entry_price - stop_loss)
            
            if price_diff > 0:
                position_size = risk_amount / price_diff
                return max(0.01, position_size)  # 最小0.01ロット
            else:
                return 0.01
                
        except Exception as e:
            logger.error(f"ポジションサイズ計算エラー: {str(e)}")
            return 0.01
    
    async def _should_close_position(
        self, 
        position: Dict[str, Any], 
        current_price: pd.Series, 
        data: pd.DataFrame, 
        parameters: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        ポジションを決済すべきかを判定
        """
        try:
            # ストップロス・テイクプロフィットチェック
            if position['side'] == 'buy':
                if position['stop_loss'] and current_price['close'] <= position['stop_loss']:
                    return True, 'stop_loss'
                if position['take_profit'] and current_price['close'] >= position['take_profit']:
                    return True, 'take_profit'
            else:  # sell
                if position['stop_loss'] and current_price['close'] >= position['stop_loss']:
                    return True, 'stop_loss'
                if position['take_profit'] and current_price['close'] <= position['take_profit']:
                    return True, 'take_profit'
            
            # 時間ベースの決済（最大保持期間）
            strategy_type = parameters.get('strategy_type', 'scalping')
            if strategy_type == 'swing':
                max_hold_hours = parameters.get('swing_max_hold_hours', 24 * 5)  # スイングは5日
            else:
                max_hold_hours = parameters.get('max_hold_hours', 1)  # スキャルピングは1時間
                
            hold_time = data.index[-1] - position['entry_time']
            
            if hold_time.total_seconds() / 3600 > max_hold_hours:
                return True, 'time_limit'
            
            # スイング戦略の場合、トレーリングストップを実装
            if strategy_type == 'swing' and parameters.get('use_trailing_stop', True):
                trailing_stop_updated = await self._update_trailing_stop(position, current_price, parameters)
                if trailing_stop_updated:
                    position['stop_loss'] = trailing_stop_updated
            
            # トレンド転換チェック
            current = data.iloc[-1]
            if position['side'] == 'buy' and current.get('trend', 0) == -1:
                return True, 'trend_reversal'
            elif position['side'] == 'sell' and current.get('trend', 0) == 1:
                return True, 'trend_reversal'
            
            return False, ''
            
        except Exception as e:
            logger.error(f"ポジション決済判定エラー: {str(e)}")
            return False, 'error'
    
    async def _update_trailing_stop(self, position: Dict[str, Any], current_price: pd.Series, parameters: Dict[str, Any]) -> Optional[float]:
        """
        トレーリングストップの更新
        """
        try:
            trailing_stop_distance = parameters.get('trailing_stop_distance', 0.005)  # 0.5%
            current_close = current_price['close']
            
            if position['side'] == 'buy':
                # 買いポジション：価格が上昇したらストップロスを引き上げる
                new_stop_loss = current_close * (1 - trailing_stop_distance)
                if new_stop_loss > position['stop_loss']:
                    logger.info(f"Trailing stop updated for BUY: {position['stop_loss']:.5f} -> {new_stop_loss:.5f}")
                    return new_stop_loss
            else:
                # 売りポジション：価格が下落したらストップロスを引き下げる
                new_stop_loss = current_close * (1 + trailing_stop_distance)
                if new_stop_loss < position['stop_loss']:
                    logger.info(f"Trailing stop updated for SELL: {position['stop_loss']:.5f} -> {new_stop_loss:.5f}")
                    return new_stop_loss
            
            return None
            
        except Exception as e:
            logger.error(f"トレーリングストップ更新エラー: {str(e)}")
            return None
    
    def _calculate_unrealized_pnl(self, positions: List[Dict[str, Any]], current_price: pd.Series) -> float:
        """
        未実現損益を計算
        """
        try:
            total_unrealized = 0
            
            for position in positions:
                if position['side'] == 'buy':
                    unrealized = (current_price['close'] - position['entry_price']) * position['quantity']
                else:  # sell
                    unrealized = (position['entry_price'] - current_price['close']) * position['quantity']
                
                total_unrealized += unrealized
            
            return total_unrealized
            
        except Exception as e:
            logger.error(f"未実現損益計算エラー: {str(e)}")
            return 0
    
    def _analyze_results(self, trades: List[Dict[str, Any]], equity_curve: List[Dict[str, Any]], initial_balance: float) -> Dict[str, Any]:
        """
        バックテスト結果を分析
        """
        try:
            if not trades:
                return {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'total_profit': 0,
                    'max_drawdown': 0,
                    'win_rate': 0,
                    'trades': []
                }
            
            # 基本統計
            total_trades = len(trades)
            winning_trades = sum(1 for trade in trades if trade['profit_loss'] > 0)
            total_profit = sum(trade['profit_loss'] for trade in trades)
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            # 利益・損失の分析
            profits = [trade['profit_loss'] for trade in trades if trade['profit_loss'] > 0]
            losses = [trade['profit_loss'] for trade in trades if trade['profit_loss'] < 0]
            
            avg_profit = np.mean(profits) if profits else 0
            avg_loss = np.mean(losses) if losses else 0
            profit_factor = abs(sum(profits) / sum(losses)) if losses else float('inf')
            
            # 最大ドローダウンを計算
            max_drawdown = self._calculate_max_drawdown(equity_curve, initial_balance)
            
            # シャープレシオを計算
            sharpe_ratio = self._calculate_sharpe_ratio(equity_curve)
            
            # 最終残高と収益率の計算
            final_balance = initial_balance + total_profit
            return_percentage = (total_profit / initial_balance) * 100
            
            result = {
                # 資金関連情報
                'initial_balance': round(initial_balance, 2),
                'final_balance': round(final_balance, 2),
                'total_profit': round(total_profit, 2),
                'return_percentage': round(return_percentage, 2),
                'leverage': 1.0,  # デフォルトレバレッジ（将来的に拡張可能）
                
                # 取引統計
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': total_trades - winning_trades,
                'win_rate': round(win_rate, 4),
                
                # 損益分析
                'avg_profit': round(avg_profit, 2),
                'avg_loss': round(avg_loss, 2),
                'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else None,
                
                # リスク指標
                'max_drawdown': round(max_drawdown, 2),
                'sharpe_ratio': round(sharpe_ratio, 4) if sharpe_ratio else None,
                
                # 詳細データ
                'trades': trades
            }
            
            return result
            
        except Exception as e:
            logger.error(f"結果分析エラー: {str(e)}")
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'total_profit': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'error': str(e),
                'trades': trades
            }
    
    def _calculate_max_drawdown(self, equity_curve: List[Dict[str, Any]], initial_balance: float) -> float:
        """
        最大ドローダウンを計算
        """
        try:
            if not equity_curve:
                return 0
            
            peak = initial_balance
            max_dd = 0
            
            for point in equity_curve:
                equity = point['total_equity']
                if equity > peak:
                    peak = equity
                
                drawdown = (peak - equity) / peak
                if drawdown > max_dd:
                    max_dd = drawdown
            
            return max_dd * 100  # パーセンテージで返す
            
        except Exception as e:
            logger.error(f"最大ドローダウン計算エラー: {str(e)}")
            return 0
    
    def _calculate_sharpe_ratio(self, equity_curve: List[Dict[str, Any]]) -> Optional[float]:
        """
        シャープレシオを計算
        """
        try:
            if len(equity_curve) < 2:
                return None
            
            returns = []
            for i in range(1, len(equity_curve)):
                prev_equity = equity_curve[i-1]['total_equity']
                curr_equity = equity_curve[i]['total_equity']
                
                if prev_equity > 0:
                    daily_return = (curr_equity - prev_equity) / prev_equity
                    returns.append(daily_return)
            
            if not returns:
                return None
            
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            
            if std_return > 0:
                return avg_return / std_return * np.sqrt(252)  # 年率化
            else:
                return None
                
        except Exception as e:
            logger.error(f"シャープレシオ計算エラー: {str(e)}")
            return None