"""
リスク管理サービス
ポジションサイズ計算、ドローダウン監視、リスク制限
"""

import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from ..core.config import settings
from ..core.logging import get_logger
from ..core.database import db_manager

logger = get_logger(__name__)

class RiskManager:
    """リスク管理クラス"""
    
    def __init__(self):
        self.max_risk_per_trade = settings.RISK_PER_TRADE  # 2%
        self.max_drawdown = settings.MAX_DRAWDOWN  # 15%
        self.max_positions = settings.MAX_POSITIONS  # 3
        
        # 通貨ペア別のピップ値（標準ロット当たり）
        self.pip_values = {
            'USDJPY': 1000,    # 1 pip = 1000 JPY for 1 standard lot
            'EURUSD': 10,      # 1 pip = 10 USD for 1 standard lot
            'GBPUSD': 10,      # 1 pip = 10 USD for 1 standard lot
            'AUDUSD': 10,      # 1 pip = 10 USD for 1 standard lot
            'USDCHF': 10,      # 1 pip = 10 CHF for 1 standard lot
            'USDCAD': 10,      # 1 pip = 10 CAD for 1 standard lot
        }
        
        # 小数点以下桁数
        self.decimal_places = {
            'USDJPY': 3,
            'EURUSD': 5,
            'GBPUSD': 5,
            'AUDUSD': 5,
            'USDCHF': 5,
            'USDCAD': 5,
        }
    
    def calculate_position_size(self, symbol: str, entry_price: float, 
                              stop_loss: float, account_balance: float,
                              risk_percentage: Optional[float] = None) -> Dict:
        """
        ポジションサイズ計算
        
        Args:
            symbol: 通貨ペア
            entry_price: エントリー価格
            stop_loss: ストップロス価格
            account_balance: 口座残高
            risk_percentage: リスク率（デフォルト: 設定値）
            
        Returns:
            Dict: 計算結果
        """
        try:
            if risk_percentage is None:
                risk_percentage = self.max_risk_per_trade
            
            # リスク金額計算
            risk_amount = account_balance * risk_percentage
            
            # ストップロス距離（pips）
            pip_size = 10 ** (-self.decimal_places[symbol])
            stop_loss_pips = abs(entry_price - stop_loss) / pip_size
            
            # ピップ値取得
            pip_value = self.get_pip_value(symbol, entry_price)
            
            # ロットサイズ計算
            if stop_loss_pips > 0 and pip_value > 0:
                lot_size = risk_amount / (stop_loss_pips * pip_value)
                
                # 最小・最大ロットサイズ制限
                lot_size = max(0.01, min(lot_size, 10.0))  # 0.01-10.0ロット制限
                lot_size = round(lot_size, 2)
            else:
                lot_size = 0.01  # 最小ロットサイズ
            
            result = {
                'symbol': symbol,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'risk_amount': risk_amount,
                'risk_percentage': risk_percentage,
                'calculated_lot_size': lot_size,
                'pip_value': pip_value,
                'stop_loss_pips': stop_loss_pips,
                'potential_loss': stop_loss_pips * pip_value * lot_size
            }
            
            logger.info(f"Position size calculated for {symbol}: {lot_size} lots, Risk: {risk_amount:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
            return {
                'error': str(e),
                'calculated_lot_size': 0.01
            }
    
    def get_pip_value(self, symbol: str, current_price: float) -> float:
        """
        ピップ値計算（1ロット当たり）
        
        Args:
            symbol: 通貨ペア
            current_price: 現在価格
            
        Returns:
            float: ピップ値（USD換算）
        """
        if symbol not in self.pip_values:
            logger.warning(f"Unknown symbol for pip value calculation: {symbol}")
            return 10.0  # デフォルト値
        
        base_pip_value = self.pip_values[symbol]
        
        # USD建て以外の場合の換算（簡易版）
        if symbol == 'USDJPY':
            # JPY建てなのでUSDに換算
            return base_pip_value / current_price
        elif symbol.endswith('USD'):
            # USD建てなのでそのまま
            return base_pip_value
        else:
            # その他の場合（簡易的にUSD換算）
            return base_pip_value
    
    def check_risk_limits(self, symbol: str, side: str, lot_size: float,
                         current_positions: List[Dict]) -> Dict:
        """
        リスク制限チェック
        
        Args:
            symbol: 通貨ペア
            side: 売買方向
            lot_size: ロットサイズ
            current_positions: 現在のポジション一覧
            
        Returns:
            Dict: チェック結果
        """
        checks = {
            'allowed': True,
            'reasons': [],
            'warnings': []
        }
        
        # 最大ポジション数チェック
        if len(current_positions) >= self.max_positions:
            checks['allowed'] = False
            checks['reasons'].append(f"Maximum positions exceeded: {len(current_positions)}/{self.max_positions}")
        
        # 同一通貨ペアのポジション重複チェック
        existing_positions = [pos for pos in current_positions if pos.get('symbol') == symbol]
        if existing_positions:
            checks['warnings'].append(f"Existing position found for {symbol}")
        
        # ロットサイズチェック
        if lot_size < 0.01:
            checks['allowed'] = False
            checks['reasons'].append("Lot size too small (minimum 0.01)")
        elif lot_size > 10.0:
            checks['allowed'] = False
            checks['reasons'].append("Lot size too large (maximum 10.0)")
        
        return checks
    
    def calculate_drawdown(self, account_balance: float, account_equity: float,
                          peak_equity: Optional[float] = None) -> Dict:
        """
        ドローダウン計算
        
        Args:
            account_balance: 口座残高
            account_equity: 口座有効証拠金
            peak_equity: 過去最高有効証拠金
            
        Returns:
            Dict: ドローダウン情報
        """
        if peak_equity is None:
            peak_equity = max(account_balance, account_equity)
        
        current_drawdown = (peak_equity - account_equity) / peak_equity if peak_equity > 0 else 0
        current_drawdown_amount = peak_equity - account_equity
        
        result = {
            'current_drawdown_percentage': current_drawdown,
            'current_drawdown_amount': current_drawdown_amount,
            'peak_equity': peak_equity,
            'current_equity': account_equity,
            'max_allowed_drawdown': self.max_drawdown,
            'drawdown_warning': current_drawdown > (self.max_drawdown * 0.8),  # 80%で警告
            'emergency_stop': current_drawdown >= self.max_drawdown
        }
        
        if result['emergency_stop']:
            logger.critical(f"EMERGENCY STOP: Drawdown {current_drawdown:.2%} exceeds limit {self.max_drawdown:.2%}")
        elif result['drawdown_warning']:
            logger.warning(f"Drawdown warning: {current_drawdown:.2%} approaching limit {self.max_drawdown:.2%}")
        
        return result
    
    def validate_trade_signal(self, signal: Dict, account_info: Dict,
                            current_positions: List[Dict]) -> Dict:
        """
        取引シグナルの総合検証
        
        Args:
            signal: 取引シグナル
            account_info: 口座情報
            current_positions: 現在のポジション
            
        Returns:
            Dict: 検証結果
        """
        validation = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'recommended_lot_size': 0.0,
            'risk_analysis': {}
        }
        
        try:
            # ポジションサイズ計算
            position_calc = self.calculate_position_size(
                signal['symbol'],
                signal['entry_price'],
                signal['stop_loss'],
                account_info['balance']
            )
            
            if 'error' in position_calc:
                validation['valid'] = False
                validation['errors'].append(f"Position size calculation failed: {position_calc['error']}")
                return validation
            
            validation['recommended_lot_size'] = position_calc['calculated_lot_size']
            validation['risk_analysis'] = position_calc
            
            # リスク制限チェック
            risk_check = self.check_risk_limits(
                signal['symbol'],
                signal['side'],
                position_calc['calculated_lot_size'],
                current_positions
            )
            
            if not risk_check['allowed']:
                validation['valid'] = False
                validation['errors'].extend(risk_check['reasons'])
            
            validation['warnings'].extend(risk_check['warnings'])
            
            # ドローダウンチェック
            drawdown = self.calculate_drawdown(
                account_info['balance'],
                account_info['equity']
            )
            
            if drawdown['emergency_stop']:
                validation['valid'] = False
                validation['errors'].append("Emergency stop due to excessive drawdown")
            elif drawdown['drawdown_warning']:
                validation['warnings'].append("High drawdown warning")
            
            validation['drawdown_info'] = drawdown
            
            logger.info(f"Trade signal validation for {signal['symbol']}: {'VALID' if validation['valid'] else 'INVALID'}")
            
        except Exception as e:
            logger.error(f"Error validating trade signal: {str(e)}")
            validation['valid'] = False
            validation['errors'].append(f"Validation error: {str(e)}")
        
        return validation

# サービスインスタンス
risk_manager = RiskManager()