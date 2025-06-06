"""
シグナル統合・優先順位付けサービス
複数のシグナルソースを統合し、最適な取引機会を選択
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import asyncio
from ..core.config import settings
from ..core.database import db_manager
from ..core.logging import get_logger
from .multi_pair_manager import multi_pair_manager
from .risk_management import risk_manager

logger = get_logger(__name__)

class SignalPriority(Enum):
    """シグナル優先度"""
    CRITICAL = 1    # 緊急（即座に実行）
    HIGH = 2        # 高優先度
    MEDIUM = 3      # 中優先度
    LOW = 4         # 低優先度

class SignalType(Enum):
    """シグナルタイプ"""
    ENTRY = "entry"           # 新規エントリー
    EXIT = "exit"             # 決済
    MODIFY = "modify"         # 修正
    REPLACE = "replace"       # 入替

class SignalSource(Enum):
    """シグナルソース"""
    DOW_THEORY = "dow_theory"
    ELLIOTT_WAVE = "elliott_wave"
    MULTI_PAIR = "multi_pair"
    RISK_MANAGEMENT = "risk_management"
    CORRELATION = "correlation"

class TradingSignal:
    """取引シグナルクラス"""
    
    def __init__(self, signal_id: str, symbol: str, signal_type: SignalType,
                 signal_source: SignalSource, priority: SignalPriority,
                 confidence: float, data: Dict):
        self.signal_id = signal_id
        self.symbol = symbol
        self.signal_type = signal_type
        self.signal_source = signal_source
        self.priority = priority
        self.confidence = confidence
        self.data = data
        self.timestamp = datetime.now()
        self.processed = False
        self.execution_result = None
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            'signal_id': self.signal_id,
            'symbol': self.symbol,
            'signal_type': self.signal_type.value,
            'signal_source': self.signal_source.value,
            'priority': self.priority.value,
            'confidence': self.confidence,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'processed': self.processed
        }

class SignalOrchestrator:
    """シグナル統合・優先順位付けクラス"""
    
    def __init__(self):
        self.active_signals: List[TradingSignal] = []
        self.signal_history: List[TradingSignal] = []
        self.max_signals_cache = 100
        
        # シグナルソース別重み
        self.source_weights = {
            SignalSource.RISK_MANAGEMENT: 1.0,    # リスク管理最優先
            SignalSource.MULTI_PAIR: 0.9,         # マルチペア分析
            SignalSource.ELLIOTT_WAVE: 0.8,       # エリオット波動
            SignalSource.DOW_THEORY: 0.7,         # ダウ理論
            SignalSource.CORRELATION: 0.6         # 相関分析
        }
        
        # 実行条件
        self.min_confidence = 0.6
        self.min_composite_score = 70
    
    def add_signal(self, signal: TradingSignal) -> bool:
        """
        シグナルを追加
        
        Args:
            signal: 追加するシグナル
            
        Returns:
            bool: 追加成功フラグ
        """
        try:
            # 重複チェック
            existing = self.find_signal(signal.symbol, signal.signal_type)
            if existing:
                # 既存シグナルと比較して優先度が高い場合は更新
                if self.compare_signals(signal, existing) > 0:
                    self.remove_signal(existing.signal_id)
                    self.active_signals.append(signal)
                    logger.info(f"Signal updated: {signal.signal_id} for {signal.symbol}")
                    return True
                else:
                    logger.info(f"Signal ignored (lower priority): {signal.signal_id}")
                    return False
            else:
                self.active_signals.append(signal)
                logger.info(f"Signal added: {signal.signal_id} for {signal.symbol}")
                return True
                
        except Exception as e:
            logger.error(f"Error adding signal: {str(e)}")
            return False
    
    def find_signal(self, symbol: str, signal_type: SignalType) -> Optional[TradingSignal]:
        """シグナル検索"""
        for signal in self.active_signals:
            if signal.symbol == symbol and signal.signal_type == signal_type:
                return signal
        return None
    
    def remove_signal(self, signal_id: str) -> bool:
        """シグナル削除"""
        for i, signal in enumerate(self.active_signals):
            if signal.signal_id == signal_id:
                removed = self.active_signals.pop(i)
                self.signal_history.append(removed)
                logger.info(f"Signal removed: {signal_id}")
                return True
        return False
    
    def compare_signals(self, signal1: TradingSignal, signal2: TradingSignal) -> int:
        """
        シグナル比較
        
        Returns:
            int: 1 if signal1 > signal2, -1 if signal1 < signal2, 0 if equal
        """
        # 優先度比較
        if signal1.priority.value < signal2.priority.value:
            return 1
        elif signal1.priority.value > signal2.priority.value:
            return -1
        
        # 信頼度比較
        if signal1.confidence > signal2.confidence:
            return 1
        elif signal1.confidence < signal2.confidence:
            return -1
        
        # タイムスタンプ比較（新しい方が優先）
        if signal1.timestamp > signal2.timestamp:
            return 1
        elif signal1.timestamp < signal2.timestamp:
            return -1
        
        return 0
    
    def get_prioritized_signals(self) -> List[TradingSignal]:
        """優先順位付きシグナル取得"""
        # 複合スコア計算とソート
        scored_signals = []
        
        for signal in self.active_signals:
            composite_score = self.calculate_composite_score(signal)
            if composite_score >= self.min_composite_score:
                scored_signals.append((signal, composite_score))
        
        # スコア順でソート
        scored_signals.sort(key=lambda x: x[1], reverse=True)
        
        return [signal for signal, score in scored_signals]
    
    def calculate_composite_score(self, signal: TradingSignal) -> float:
        """
        複合スコア計算
        
        Args:
            signal: 評価対象シグナル
            
        Returns:
            float: 複合スコア（0-100）
        """
        try:
            # ベーススコア（信頼度ベース）
            base_score = signal.confidence * 100
            
            # ソース重み適用
            source_weight = self.source_weights.get(signal.signal_source, 0.5)
            weighted_score = base_score * source_weight
            
            # 優先度ボーナス
            priority_bonus = {
                SignalPriority.CRITICAL: 20,
                SignalPriority.HIGH: 15,
                SignalPriority.MEDIUM: 10,
                SignalPriority.LOW: 5
            }.get(signal.priority, 0)
            
            # タイミングボーナス（新しいシグナルほど高評価）
            time_diff = (datetime.now() - signal.timestamp).total_seconds()
            timing_bonus = max(0, 10 - (time_diff / 600))  # 10分で減衰
            
            # 市場環境ボーナス
            market_bonus = self.calculate_market_environment_bonus(signal.symbol)
            
            total_score = weighted_score + priority_bonus + timing_bonus + market_bonus
            
            return min(total_score, 100)
            
        except Exception as e:
            logger.error(f"Error calculating composite score: {str(e)}")
            return 0
    
    def calculate_market_environment_bonus(self, symbol: str) -> float:
        """市場環境ボーナス計算"""
        try:
            current_time = datetime.now()
            hour = current_time.hour
            
            # 流動性時間帯ボーナス
            if 22 <= hour or hour <= 6:  # NY時間（JST）
                return 5
            elif 15 <= hour <= 21:  # ロンドン時間
                return 3
            elif 8 <= hour <= 15:   # 東京時間
                return 2
            else:
                return 0
                
        except Exception as e:
            logger.error(f"Error calculating market environment bonus: {str(e)}")
            return 0
    
    async def process_signals(self) -> Dict:
        """
        シグナル処理実行
        
        Returns:
            Dict: 処理結果
        """
        try:
            prioritized_signals = self.get_prioritized_signals()
            
            if not prioritized_signals:
                return {
                    'processed_count': 0,
                    'message': 'No signals to process',
                    'timestamp': datetime.now().isoformat()
                }
            
            # 現在のポジション状況確認
            current_positions = db_manager.get_active_trades()
            account_info = {'balance': 100000.0, 'equity': 100000.0}  # Mock data
            
            processed_signals = []
            execution_results = []
            
            for signal in prioritized_signals:
                try:
                    # シグナルタイプ別処理
                    if signal.signal_type == SignalType.ENTRY:
                        result = await self.process_entry_signal(signal, current_positions, account_info)
                    elif signal.signal_type == SignalType.EXIT:
                        result = await self.process_exit_signal(signal, current_positions)
                    elif signal.signal_type == SignalType.MODIFY:
                        result = await self.process_modify_signal(signal, current_positions)
                    elif signal.signal_type == SignalType.REPLACE:
                        result = await self.process_replace_signal(signal, current_positions, account_info)
                    else:
                        result = {'success': False, 'message': 'Unknown signal type'}
                    
                    signal.execution_result = result
                    signal.processed = True
                    processed_signals.append(signal)
                    execution_results.append(result)
                    
                    logger.info(f"Signal processed: {signal.signal_id} - {result}")
                    
                except Exception as e:
                    logger.error(f"Error processing signal {signal.signal_id}: {str(e)}")
                    execution_results.append({
                        'success': False,
                        'signal_id': signal.signal_id,
                        'error': str(e)
                    })
            
            # 処理済みシグナルを履歴に移動
            for signal in processed_signals:
                self.remove_signal(signal.signal_id)
            
            return {
                'processed_count': len(processed_signals),
                'execution_results': execution_results,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing signals: {str(e)}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def process_entry_signal(self, signal: TradingSignal, 
                                 current_positions: List, account_info: Dict) -> Dict:
        """エントリーシグナル処理"""
        try:
            # リスク検証
            validation = risk_manager.validate_trade_signal(
                signal.data, account_info, current_positions
            )
            
            if not validation['valid']:
                return {
                    'success': False,
                    'signal_id': signal.signal_id,
                    'message': f"Risk validation failed: {validation['errors']}"
                }
            
            # 模擬実行（実際にはMT5に注文送信）
            return {
                'success': True,
                'signal_id': signal.signal_id,
                'action': 'entry',
                'symbol': signal.symbol,
                'recommended_lot_size': validation['recommended_lot_size'],
                'message': 'Entry signal processed (simulation)'
            }
            
        except Exception as e:
            return {
                'success': False,
                'signal_id': signal.signal_id,
                'error': str(e)
            }
    
    async def process_exit_signal(self, signal: TradingSignal, current_positions: List) -> Dict:
        """決済シグナル処理"""
        try:
            # 対象ポジション検索
            target_position = None
            for pos in current_positions:
                if pos.get('symbol') == signal.symbol:
                    target_position = pos
                    break
            
            if not target_position:
                return {
                    'success': False,
                    'signal_id': signal.signal_id,
                    'message': f'No position found for {signal.symbol}'
                }
            
            # 模擬決済
            return {
                'success': True,
                'signal_id': signal.signal_id,
                'action': 'exit',
                'symbol': signal.symbol,
                'position_id': target_position.get('id'),
                'message': 'Exit signal processed (simulation)'
            }
            
        except Exception as e:
            return {
                'success': False,
                'signal_id': signal.signal_id,
                'error': str(e)
            }
    
    async def process_modify_signal(self, signal: TradingSignal, current_positions: List) -> Dict:
        """修正シグナル処理"""
        try:
            # 対象ポジション検索
            target_position = None
            for pos in current_positions:
                if pos.get('symbol') == signal.symbol:
                    target_position = pos
                    break
            
            if not target_position:
                return {
                    'success': False,
                    'signal_id': signal.signal_id,
                    'message': f'No position found for {signal.symbol}'
                }
            
            # 模擬修正
            return {
                'success': True,
                'signal_id': signal.signal_id,
                'action': 'modify',
                'symbol': signal.symbol,
                'position_id': target_position.get('id'),
                'modifications': signal.data,
                'message': 'Modify signal processed (simulation)'
            }
            
        except Exception as e:
            return {
                'success': False,
                'signal_id': signal.signal_id,
                'error': str(e)
            }
    
    async def process_replace_signal(self, signal: TradingSignal, 
                                   current_positions: List, account_info: Dict) -> Dict:
        """入替シグナル処理"""
        try:
            replace_data = signal.data
            close_symbol = replace_data.get('close_symbol')
            open_symbol = replace_data.get('open_symbol')
            
            # 決済対象ポジション検索
            close_position = None
            for pos in current_positions:
                if pos.get('symbol') == close_symbol:
                    close_position = pos
                    break
            
            if not close_position:
                return {
                    'success': False,
                    'signal_id': signal.signal_id,
                    'message': f'No position found to close for {close_symbol}'
                }
            
            # 模擬入替実行
            return {
                'success': True,
                'signal_id': signal.signal_id,
                'action': 'replace',
                'close_symbol': close_symbol,
                'open_symbol': open_symbol,
                'position_id': close_position.get('id'),
                'message': 'Replace signal processed (simulation)'
            }
            
        except Exception as e:
            return {
                'success': False,
                'signal_id': signal.signal_id,
                'error': str(e)
            }
    
    def get_signal_statistics(self) -> Dict:
        """シグナル統計取得"""
        try:
            active_count = len(self.active_signals)
            history_count = len(self.signal_history)
            
            # ソース別統計
            source_stats = {}
            for source in SignalSource:
                source_stats[source.value] = {
                    'active': len([s for s in self.active_signals if s.signal_source == source]),
                    'history': len([s for s in self.signal_history if s.signal_source == source])
                }
            
            # タイプ別統計
            type_stats = {}
            for signal_type in SignalType:
                type_stats[signal_type.value] = {
                    'active': len([s for s in self.active_signals if s.signal_type == signal_type]),
                    'history': len([s for s in self.signal_history if s.signal_type == signal_type])
                }
            
            return {
                'total_active': active_count,
                'total_history': history_count,
                'source_statistics': source_stats,
                'type_statistics': type_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting signal statistics: {str(e)}")
            return {'error': str(e)}
    
    def cleanup_old_signals(self, max_age_hours: int = 24):
        """古いシグナルのクリーンアップ"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            # アクティブシグナルから古いものを削除
            self.active_signals = [
                s for s in self.active_signals 
                if s.timestamp > cutoff_time
            ]
            
            # 履歴の制限
            if len(self.signal_history) > self.max_signals_cache:
                self.signal_history = self.signal_history[-self.max_signals_cache:]
            
            logger.info("Signal cleanup completed")
            
        except Exception as e:
            logger.error(f"Error cleaning up signals: {str(e)}")

# サービスインスタンス
signal_orchestrator = SignalOrchestrator()