# FX自動売買システム 技術仕様書
**バージョン**: 5.0 Final  
**最終更新**: 2025年6月7日  
**ステータス**: 完全実装完了

## 📋 システム概要

### アーキテクチャ
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MetaTrader 5  │◄──►│   FastAPI       │◄──►│   SQLite DB     │
│   (MQL5 EA)     │    │   Python        │    │   (データ永続化) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐               │
         │              │ バックテスト    │               │
         │              │ エンジン        │               │
         │              └─────────────────┘               │
         │                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐               │
         └─────────────►│ パラメータ      │◄──────────────┘
                        │ 最適化エンジン  │
                        └─────────────────┘
```

### 技術スタック
- **バックエンド**: Python 3.9+, FastAPI 0.115.12
- **データベース**: SQLite 3
- **取引プラットフォーム**: MetaTrader 5
- **EA言語**: MQL5
- **分析ライブラリ**: pandas 2.3.0, numpy 2.2.6, TA-Lib 0.6.3
- **機械学習**: scikit-learn 1.5.2
- **通信**: HTTP REST API, WebSockets 15.0.1
- **非同期処理**: uvicorn, aiofiles, aiohttp

## 🏗️ システム構成

### コア モジュール

#### 1. データベース スキーマ (`app/core/database.py`)
```sql
-- 市場データテーブル
CREATE TABLE market_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timestamp)
);

-- 取引テーブル
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT CHECK(side IN ('buy', 'sell')) NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    entry_price REAL NOT NULL,
    exit_price REAL,
    quantity REAL NOT NULL,
    profit_loss REAL DEFAULT 0,
    status TEXT DEFAULT 'open',
    stop_loss REAL,
    take_profit REAL,
    exit_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- アラートテーブル
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    severity INTEGER NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP
);

-- バックテスト結果テーブル
CREATE TABLE backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    parameters TEXT NOT NULL,
    total_trades INTEGER NOT NULL,
    winning_trades INTEGER NOT NULL,
    total_profit REAL NOT NULL,
    max_drawdown REAL NOT NULL,
    sharpe_ratio REAL,
    win_rate REAL NOT NULL,
    profit_factor REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 最適化結果テーブル
CREATE TABLE optimization_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    optimization_type TEXT NOT NULL,
    objective_function TEXT NOT NULL,
    best_parameters TEXT NOT NULL,
    best_score REAL NOT NULL,
    total_iterations INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

#### 2. 設定管理 (`app/core/config.py`)
```python
class Settings(BaseSettings):
    # アプリケーション設定
    PROJECT_NAME: str = "FX Trading System"
    VERSION: str = "5.0"
    DESCRIPTION: str = "Advanced FX Trading System with AI-driven optimization"
    API_V1_STR: str = "/api/v1"
    
    # サーバー設定
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    
    # 取引設定
    CURRENCY_PAIRS: List[str] = ["USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD"]
    MAX_POSITIONS: int = 3
    RISK_PER_TRADE: float = 0.02  # 2%
    MAX_DRAWDOWN: float = 0.15    # 15%
    UPDATE_INTERVAL: int = 300    # 5分
    
    # CORS設定
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # データベース設定
    DATABASE_URL: str = "sqlite:///./fx_trading.db"
```

## 🧮 テクニカル分析エンジン

### ダウ理論実装 (`app/services/technical_analysis.py`)
```python
class DowTheoryAnalyzer:
    """ダウ理論に基づくトレンド分析"""
    
    async def analyze_trend(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        トレンド分析実行
        - 高値・安値の更新パターン分析
        - トレンド強度計算（0-30点）
        - 転換点の検出
        """
        swing_points = await self._detect_swing_points(data)
        trend_direction = self._determine_trend_direction(swing_points)
        trend_strength = self._calculate_trend_strength(swing_points)
        
        return {
            "trend_direction": trend_direction,  # 1: 上昇, -1: 下降, 0: 横ばい
            "trend_strength": trend_strength,    # 0-30点
            "swing_highs": swing_points["highs"],
            "swing_lows": swing_points["lows"],
            "last_reversal": swing_points["last_reversal"]
        }
    
    async def _detect_swing_points(self, data: pd.DataFrame, window: int = 5) -> Dict:
        """スイングポイント検出"""
        highs = []
        lows = []
        
        for i in range(window, len(data) - window):
            # スイングハイ検出
            if all(data.iloc[i]['high'] > data.iloc[j]['high'] 
                   for j in range(i-window, i+window+1) if j != i):
                highs.append({
                    "timestamp": data.index[i],
                    "price": data.iloc[i]['high']
                })
            
            # スイングロー検出
            if all(data.iloc[i]['low'] < data.iloc[j]['low'] 
                   for j in range(i-window, i+window+1) if j != i):
                lows.append({
                    "timestamp": data.index[i],
                    "price": data.iloc[i]['low']
                })
        
        return {"highs": highs, "lows": lows}
```

### エリオット波動分析
```python
class ElliottWaveAnalyzer:
    """エリオット波動理論実装"""
    
    def analyze_wave_position(self, swing_points: Dict) -> Dict[str, Any]:
        """
        現在の波動位置分析
        - 第1波: 30点
        - 第3波: 40点（最強）
        - 第5波: 20点
        """
        waves = self._identify_waves(swing_points)
        current_wave = self._determine_current_wave(waves)
        wave_score = self._calculate_wave_score(current_wave)
        
        return {
            "current_wave": current_wave,
            "wave_score": wave_score,
            "wave_completion": self._calculate_completion_ratio(waves),
            "fibonacci_levels": self._calculate_fibonacci_levels(waves)
        }
```

## 🎯 高頻度スキャルピング戦略エンジン

### 最適化済みスキャルピング戦略 (`app/services/backtest_engine.py`)
```python
class OptimizedScalpingStrategy:
    """エントリー閾値とリスク・リワード比が最適化されたスキャルピング戦略"""
    
    async def _generate_signal(self, data: pd.DataFrame, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        改善されたシグナル生成ロジック
        """
        current = data.iloc[-1]
        prev = data.iloc[-2] if len(data) > 1 else current
        
        signal = {
            'action': 'hold',
            'score': 0,
            'stop_loss': None,
            'take_profit': None
        }
        
        # 高品質エントリー条件
        if len(data) >= 5:
            # 短期価格分析
            recent_prices = data['close'].tail(5)
            short_ma = recent_prices.mean()
            price_change = (current['close'] - prev['close']) / prev['close']
            ma_deviation = (current['close'] - short_ma) / short_ma
            volatility = recent_prices.std() / recent_prices.mean()
            
            score = 0
            
            # 厳選された取引条件（0.05%以上の明確な変動）
            if price_change > 0.0005:  # 0.05%上昇
                score += 50
            elif price_change < -0.0005:  # 0.05%下落
                score -= 50
            
            # 移動平均乖離（0.08%以上）
            if ma_deviation > 0.0008:
                score += 25
            elif ma_deviation < -0.0008:
                score -= 25
            
            # 勢いの継続性チェック
            if len(data) >= 3:
                prev_change = (prev['close'] - data['close'].iloc[-3]) / data['close'].iloc[-3]
                if price_change > 0 and prev_change > 0:  # 連続上昇
                    score += 15
                elif price_change < 0 and prev_change < 0:  # 連続下落
                    score -= 15
            
            # ボラティリティフィルター
            if 0.0008 < volatility < 0.003:  # 適度なボラティリティ
                score = int(score * 1.2)
            elif volatility > 0.005:  # 過度なボラティリティは減点
                score = int(score * 0.8)
        
        # シグナル判定
        entry_threshold = parameters.get('entry_threshold', 50)
        
        if score >= entry_threshold:
            signal['action'] = 'buy'
            signal['score'] = score
            # 最適化されたリスク・リワード比 1:6 (SL:0.05%, TP:0.30%)
            signal['stop_loss'] = current['close'] * 0.9995   # 0.05%
            signal['take_profit'] = current['close'] * 1.0030  # 0.30%
            
        elif score <= -entry_threshold:
            signal['action'] = 'sell'
            signal['score'] = abs(score)
            signal['stop_loss'] = current['close'] * 1.0005   # 0.05%
            signal['take_profit'] = current['close'] * 0.9970  # 0.30%
        
        return signal
```

### 最適化パラメータ
```python
OPTIMIZED_SCALPING_PARAMETERS = {
    # エントリー条件
    "entry_threshold": 50,           # 厳選された取引のみ
    "price_change_min": 0.0005,      # 0.05%以上の変動
    "ma_deviation_min": 0.0008,      # 0.08%以上の乖離
    
    # リスク管理
    "stop_loss_pct": 0.0005,         # 0.05%ストップロス
    "take_profit_pct": 0.0030,       # 0.30%テイクプロフィット
    "risk_reward_ratio": 6.0,        # 1:6のリスクリワード
    
    # ボラティリティフィルター
    "min_volatility": 0.0008,        # 最小ボラティリティ
    "max_volatility": 0.003,         # 最大ボラティリティ
    "high_volatility_threshold": 0.005,  # 過度なボラティリティ
    
    # タイミング設定
    "max_hold_hours": 1,             # 最大保持時間
    "ma_period": 3,                  # 短期移動平均期間
    "rsi_period": 7,                 # RSI期間
    
    # バックテスト設定
    "min_data_points": 20,           # 最小データ数
    "start_index_offset": 10         # 開始インデックス
}
```

## 🔄 バックテストエンジン

### バックテスト実行フロー
```python
class BacktestEngine:
    """高性能バックテストエンジン"""
    
    async def run_backtest(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        parameters: Dict[str, Any],
        initial_balance: float = 100000,
        risk_per_trade: float = 0.02,
        max_positions: int = 3
    ) -> Dict[str, Any]:
        """
        バックテスト実行
        """
        # 1. データ取得
        market_data = await self._get_market_data(symbol, start_date, end_date)
        
        if len(market_data) < 20:
            raise ValueError(f"データが不足しています: {len(market_data)}件")
        
        # 2. バックテスト実行
        result = await self._execute_backtest(
            market_data, parameters, initial_balance, risk_per_trade, max_positions
        )
        
        return result
    
    async def _execute_backtest(self, data: pd.DataFrame, parameters: Dict, 
                               initial_balance: float, risk_per_trade: float, 
                               max_positions: int) -> Dict[str, Any]:
        """バックテストメイン実行ロジック"""
        
        # 初期設定
        balance = initial_balance
        positions = []
        trades = []
        equity_curve = []
        
        # テクニカル指標計算
        data = await self._calculate_technical_indicators(data, parameters)
        
        # シミュレーション実行
        start_index = min(10, len(data) - 5)  # スキャルピング用早期開始
        
        for i in range(start_index, len(data)):
            current_time = data.index[i]
            current_data = data.iloc[:i+1]
            current_price = data.iloc[i]
            
            # エントリーシグナルチェック
            if len(positions) < max_positions:
                signal = await self._generate_signal(current_data, parameters)
                
                if signal['action'] in ['buy', 'sell']:
                    # ポジション開始
                    position_size = self._calculate_position_size(
                        balance, current_price['close'], 
                        signal.get('stop_loss'), risk_per_trade
                    )
                    
                    position = {
                        'symbol': symbol,
                        'side': signal['action'],
                        'entry_time': current_time,
                        'entry_price': current_price['close'],
                        'quantity': position_size,
                        'stop_loss': signal.get('stop_loss'),
                        'take_profit': signal.get('take_profit'),
                        'score': signal.get('score', 50)
                    }
                    positions.append(position)
            
            # ポジション管理
            positions_to_close = []
            for pos_idx, position in enumerate(positions):
                should_close, exit_reason = await self._should_close_position(
                    position, current_price, current_data, parameters
                )
                
                if should_close:
                    # ポジション決済
                    exit_price = current_price['close']
                    
                    if position['side'] == 'buy':
                        profit = (exit_price - position['entry_price']) * position['quantity']
                    else:
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
            for idx in reversed(positions_to_close):
                positions.pop(idx)
            
            # エクイティカーブ記録
            unrealized_pnl = self._calculate_unrealized_pnl(positions, current_price)
            equity_curve.append({
                'timestamp': current_time.isoformat(),
                'balance': balance,
                'unrealized_pnl': unrealized_pnl,
                'total_equity': balance + unrealized_pnl
            })
        
        # 最終分析
        analysis = self._analyze_results(trades, equity_curve, initial_balance)
        return analysis
```

## 🤖 パラメータ最適化エンジン

### 遺伝的アルゴリズム実装
```python
class GeneticOptimizer:
    """遺伝的アルゴリズムによるパラメータ最適化"""
    
    async def optimize(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        parameter_ranges: Dict[str, Dict],
        objective_function: str = "sharpe_ratio",
        population_size: int = 50,
        generations: int = 100,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.8
    ) -> Dict[str, Any]:
        """
        遺伝的アルゴリズムによる最適化実行
        """
        
        # 初期個体群生成
        population = await self._generate_initial_population(
            parameter_ranges, population_size
        )
        
        best_individual = None
        best_score = float('-inf')
        generation_scores = []
        
        for generation in range(generations):
            # 個体評価
            fitness_scores = []
            
            for individual in population:
                # バックテスト実行
                backtest_result = await self.backtest_engine.run_backtest(
                    symbol, start_date, end_date, individual
                )
                
                # 目的関数計算
                score = self._calculate_objective_score(
                    backtest_result, objective_function
                )
                fitness_scores.append(score)
                
                # 最良個体更新
                if score > best_score:
                    best_score = score
                    best_individual = individual.copy()
            
            generation_scores.append(max(fitness_scores))
            
            # 次世代生成
            population = await self._create_next_generation(
                population, fitness_scores, crossover_rate, mutation_rate
            )
            
            logger.info(f"Generation {generation}: Best Score = {max(fitness_scores):.4f}")
        
        return {
            "best_parameters": best_individual,
            "best_score": best_score,
            "generation_scores": generation_scores,
            "total_generations": generations
        }
```

### グリッドサーチ実装
```python
class GridSearchOptimizer:
    """グリッドサーチによる全探索最適化"""
    
    async def optimize(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        parameter_ranges: Dict[str, Dict],
        objective_function: str = "profit_factor"
    ) -> Dict[str, Any]:
        """
        グリッドサーチによる最適化実行
        """
        
        # パラメータ組み合わせ生成
        parameter_combinations = self._generate_parameter_grid(parameter_ranges)
        
        best_parameters = None
        best_score = float('-inf')
        all_results = []
        
        total_combinations = len(parameter_combinations)
        logger.info(f"Grid Search: {total_combinations} combinations to test")
        
        for i, parameters in enumerate(parameter_combinations):
            try:
                # バックテスト実行
                backtest_result = await self.backtest_engine.run_backtest(
                    symbol, start_date, end_date, parameters
                )
                
                # 目的関数計算
                score = self._calculate_objective_score(
                    backtest_result, objective_function
                )
                
                all_results.append({
                    "parameters": parameters,
                    "score": score,
                    "backtest_result": backtest_result
                })
                
                # 最良結果更新
                if score > best_score:
                    best_score = score
                    best_parameters = parameters
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i+1}/{total_combinations} ({((i+1)/total_combinations)*100:.1f}%)")
                
            except Exception as e:
                logger.error(f"Error in combination {i}: {str(e)}")
                continue
        
        return {
            "best_parameters": best_parameters,
            "best_score": best_score,
            "all_results": all_results,
            "total_tested": len(all_results)
        }
```

## 📊 パフォーマンス分析エンジン

### リスク指標計算
```python
class PerformanceAnalyzer:
    """包括的なパフォーマンス分析"""
    
    def calculate_risk_metrics(self, trades: List[Dict], equity_curve: List[Dict]) -> Dict[str, float]:
        """
        リスク指標の計算
        """
        if not trades or not equity_curve:
            return {}
        
        # データフレーム作成
        df_trades = pd.DataFrame(trades)
        df_equity = pd.DataFrame(equity_curve)
        
        # 基本統計
        total_trades = len(df_trades)
        winning_trades = len(df_trades[df_trades['profit_loss'] > 0])
        losing_trades = len(df_trades[df_trades['profit_loss'] < 0])
        
        # 収益性指標
        total_profit = df_trades['profit_loss'].sum()
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        gross_profit = df_trades[df_trades['profit_loss'] > 0]['profit_loss'].sum()
        gross_loss = abs(df_trades[df_trades['profit_loss'] < 0]['profit_loss'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # リスク指標
        returns = df_equity['total_equity'].pct_change().dropna()
        
        # シャープレシオ
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        
        # 最大ドローダウン
        max_drawdown = self._calculate_max_drawdown(df_equity['total_equity'])
        
        # ソルティーノレシオ
        sortino_ratio = self._calculate_sortino_ratio(returns)
        
        # カルマーレシオ
        calmar_ratio = self._calculate_calmar_ratio(returns, max_drawdown)
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_profit": total_profit,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown * 100
        }
```

## 🚨 監視・アラートシステム

### システムヘルス監視
```python
class SystemMonitor:
    """リアルタイムシステム監視"""
    
    async def check_system_health(self) -> Dict[str, Any]:
        """
        システム全体のヘルスチェック
        """
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "components": {}
        }
        
        # データベース接続チェック
        db_status = await self._check_database_health()
        health_status["components"]["database"] = db_status
        
        # API応答時間チェック
        api_status = await self._check_api_response_time()
        health_status["components"]["api"] = api_status
        
        # メモリ使用量チェック
        memory_status = self._check_memory_usage()
        health_status["components"]["memory"] = memory_status
        
        # ディスク容量チェック
        disk_status = self._check_disk_usage()
        health_status["components"]["disk"] = disk_status
        
        # 全体ステータス判定
        if any(comp["status"] == "unhealthy" for comp in health_status["components"].values()):
            health_status["overall_status"] = "unhealthy"
        elif any(comp["status"] == "warning" for comp in health_status["components"].values()):
            health_status["overall_status"] = "warning"
        
        return health_status
    
    async def create_alert(self, alert_type: str, title: str, message: str, severity: int) -> int:
        """
        アラート作成
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO alerts (type, title, message, severity, status, created_at)
            VALUES (?, ?, ?, ?, 'active', ?)
        """, (alert_type, title, message, severity, datetime.now()))
        
        alert_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 重要なアラートの場合は即座に通知
        if severity >= 8:
            await self._send_emergency_notification(alert_id, title, message)
        
        return alert_id
```

## 🔗 MT5統合システム

### 履歴データ取得
```python
# MT5 EAからの履歴データ受信エンドポイント
@router.post("/mt5/receive-historical-batch")
async def receive_historical_batch(batch_data: Dict[str, Any]):
    """
    MT5 EAからの履歴データバッチを受信
    """
    try:
        symbol = batch_data.get("symbol")
        batch_number = batch_data.get("batch_number", 0)
        data_records = batch_data.get("data", [])
        
        if not symbol or not data_records:
            raise HTTPException(status_code=400, detail="シンボルまたはデータが不足しています")
        
        # データベースに保存
        saved_count = await save_mt5_historical_data(symbol, data_records)
        
        logger.info(f"MT5バッチデータ受信: {symbol} バッチ#{batch_number} ({saved_count}/{len(data_records)}件保存)")
        
        return {
            "status": "success",
            "symbol": symbol,
            "batch_number": batch_number,
            "received_records": len(data_records),
            "saved_records": saved_count
        }
        
    except Exception as e:
        logger.error(f"MT5バッチデータ受信エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"バッチデータ受信に失敗: {str(e)}")
```

### MQL5 EA拡張機能
```mql5
//+------------------------------------------------------------------+
//|                           MT5_Historical_Data_EA.mq5            |
//|                        履歴データ取得専用EA                      |
//+------------------------------------------------------------------+

// 履歴データ取得・送信関数（メイン処理）
bool GetAndSendHistoricalData(string symbol, datetime start_date, datetime end_date, ENUM_TIMEFRAMES timeframe)
{
    if(is_processing)
    {
        Print("Already processing historical data request");
        return false;
    }
    
    is_processing = true;
    
    Print("Starting historical data collection for ", symbol);
    Print("Period: ", TimeToString(start_date), " to ", TimeToString(end_date));
    Print("Timeframe: ", EnumToString(timeframe));
    
    // バー数を計算
    int total_bars = Bars(symbol, timeframe, start_date, end_date);
    if(total_bars <= 0)
    {
        Print("ERROR: No bars found for the specified period");
        is_processing = false;
        return false;
    }
    
    Print("Total bars to process: ", total_bars);
    WriteLog("Historical data request: " + symbol + " (" + IntegerToString(total_bars) + " bars)");
    
    // バッチ処理でデータを取得・送信
    int processed_bars = 0;
    int batch_count = 0;
    
    while(processed_bars < total_bars)
    {
        int bars_to_get = MathMin(BATCH_SIZE, total_bars - processed_bars);
        
        // 履歴データを取得
        MqlRates rates[];
        int copied = CopyRates(symbol, timeframe, start_date, bars_to_get, rates);
        
        if(copied <= 0)
        {
            Print("ERROR: Failed to copy rates. Bars requested: ", bars_to_get);
            Sleep(1000); // 1秒待機して再試行
            continue;
        }
        
        // データをJSON形式で送信
        string json_data = BuildHistoricalDataJSON(symbol, rates, copied, batch_count);
        
        if(SendHistoricalDataBatch(json_data, symbol, batch_count))
        {
            processed_bars += copied;
            batch_count++;
            
            Print("Batch ", batch_count, " sent successfully. Progress: ", processed_bars, "/", total_bars);
            
            // 進捗をログに記録
            if(batch_count % 10 == 0)
            {
                WriteLog("Progress: " + IntegerToString(processed_bars) + "/" + IntegerToString(total_bars) + " bars");
            }
        }
        else
        {
            Print("ERROR: Failed to send batch ", batch_count);
            WriteLog("ERROR: Failed to send batch " + IntegerToString(batch_count));
        }
        
        // 次のバッチの開始時刻を更新
        if(copied > 0)
        {
            start_date = rates[copied-1].time + PeriodSeconds(timeframe);
        }
        
        // サーバー負荷を考慮して少し待機
        Sleep(DELAY_MS);
    }
    
    Print("Historical data collection completed. Total processed: ", processed_bars);
    WriteLog("Historical data collection completed: " + IntegerToString(processed_bars) + " bars");
    
    is_processing = false;
    return true;
}
```

## 📈 最適化結果

### スキャルピング戦略パフォーマンス
```json
{
  "strategy_name": "Optimized High-Frequency Scalping",
  "optimization_results": {
    "before_optimization": {
      "total_profit": -31529.17,
      "profit_factor": 0.87,
      "win_rate": 0.2791,
      "total_trades": 86,
      "max_drawdown": 77.06
    },
    "after_optimization": {
      "total_profit": -12918.08,
      "profit_factor": 0.95,
      "win_rate": 0.2763,
      "total_trades": 76,
      "max_drawdown": 74.58
    },
    "improvement": {
      "profit_improvement": "59% loss reduction",
      "profit_factor_improvement": "9% increase",
      "trade_quality_improvement": "More selective entries"
    }
  },
  "optimized_parameters": {
    "entry_threshold": 50,
    "price_change_minimum": 0.0005,
    "ma_deviation_minimum": 0.0008,
    "stop_loss_percentage": 0.0005,
    "take_profit_percentage": 0.0030,
    "risk_reward_ratio": 6.0,
    "max_hold_hours": 1,
    "volatility_filter": {
      "min_volatility": 0.0008,
      "max_volatility": 0.003,
      "high_volatility_threshold": 0.005
    }
  }
}
```

## 🔧 API仕様

### 主要エンドポイント
- **総エンドポイント数**: 58個
- **バックテスト関連**: 6個
- **最適化関連**: 6個  
- **監視・アラート関連**: 8個
- **パフォーマンス分析関連**: 7個
- **MT5統合関連**: 10個

### 認証・セキュリティ
- CORS設定によるクロスオリジン制御
- リクエストレート制限（将来実装予定）
- データ検証によるSQLインジェクション防止
- ログベースの操作追跡

## 📊 システム要件

### 最小動作環境
- **OS**: Windows 10/11, macOS 10.15+, Ubuntu 18.04+
- **Python**: 3.9以上
- **メモリ**: 4GB以上
- **ディスク**: 10GB以上の空き容量
- **MetaTrader 5**: Build 3610以上

### 推奨動作環境
- **OS**: Windows 11, macOS 12+
- **Python**: 3.11
- **メモリ**: 8GB以上
- **ディスク**: 50GB以上（履歴データ保存用）
- **CPU**: 4コア以上（並列処理用）

## 🔍 開発・運用ガイド

### デバッグ設定
```python
# ログレベル設定
LOG_LEVEL = "DEBUG"  # 開発時はDEBUG、本番はINFO

# バックテストデバッグ
BACKTEST_DEBUG = True  # シグナル生成の詳細ログ出力

# パフォーマンス監視
PERFORMANCE_MONITORING = True  # システムメトリクス収集
```

### 本番運用設定
```python
# 本番環境設定
LOG_LEVEL = "INFO"
MAX_LOG_FILES = 30  # ログローテーション
DATABASE_BACKUP_INTERVAL = 86400  # 1日毎のバックアップ
ALERT_WEBHOOK_URL = "https://your-notification-service"
```

---

**📝 文書バージョン**: 5.0 Final  
**✅ 実装完了日**: 2025年6月7日  
**🔧 開発者**: FX Trading System Team  
**📞 サポート**: システムログ参照 (`logs/fx_trading.log`)