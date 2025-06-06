import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from .config import settings
from .logging import get_logger

logger = get_logger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "fx_trading.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".", exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    timestamp TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    quantity REAL NOT NULL,
                    stop_loss REAL,
                    take_profit REAL,
                    profit_loss REAL DEFAULT 0,
                    status TEXT DEFAULT 'open',
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    module TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp 
                ON market_data(symbol, timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_signals_symbol_timestamp 
                ON signals(symbol, timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_trades_symbol_status 
                ON trades(symbol, status)
            ''')
            
            # アラート関連テーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    symbol TEXT,
                    severity INTEGER NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    acknowledged_at TEXT,
                    resolved_at TEXT,
                    metadata TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    condition TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity INTEGER NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    cooldown_minutes INTEGER DEFAULT 5,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alert_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    total_severity INTEGER DEFAULT 0,
                    UNIQUE(date, alert_type)
                )
            ''')
            
            # バックテスト関連テーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backtest_results (
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
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backtest_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backtest_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    profit_loss REAL NOT NULL,
                    FOREIGN KEY (backtest_id) REFERENCES backtest_results (id)
                )
            ''')
            
            # インデックス追加
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_alerts_status_type 
                ON alerts(status, type)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_backtest_results_symbol 
                ON backtest_results(symbol, created_at)
            ''')
            
            # 最適化関連テーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS optimization_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    optimization_type TEXT NOT NULL,
                    objective_function TEXT NOT NULL,
                    max_iterations INTEGER NOT NULL,
                    parameters TEXT NOT NULL,
                    status TEXT DEFAULT 'running',
                    best_parameters TEXT,
                    best_score REAL,
                    total_iterations INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS optimization_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    optimization_id INTEGER NOT NULL,
                    iteration INTEGER NOT NULL,
                    parameters TEXT NOT NULL,
                    score REAL NOT NULL,
                    metrics TEXT,
                    FOREIGN KEY (optimization_id) REFERENCES optimization_jobs (id)
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_optimization_jobs_symbol 
                ON optimization_jobs(symbol, created_at)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_optimization_history_job 
                ON optimization_history(optimization_id, iteration)
            ''')
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def insert_market_data(self, symbol: str, timestamp: str, open_price: float, 
                          high: float, low: float, close: float, volume: float = 0):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO market_data (symbol, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, timestamp, open_price, high, low, close, volume))
            conn.commit()
    
    def insert_signal(self, symbol: str, signal_type: str, score: int, 
                     entry_price: Optional[float] = None, stop_loss: Optional[float] = None,
                     take_profit: Optional[float] = None, timestamp: Optional[str] = None):
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO signals (symbol, signal_type, score, entry_price, stop_loss, take_profit, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, signal_type, score, entry_price, stop_loss, take_profit, timestamp))
            conn.commit()
    
    def get_latest_market_data(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM market_data 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (symbol, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_active_trades(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM trades 
                WHERE status = 'open' 
                ORDER BY entry_time DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def insert_trade(self, symbol: str, side: str, entry_price: float, quantity: float,
                    stop_loss: Optional[float] = None, take_profit: Optional[float] = None,
                    entry_time: Optional[str] = None, ticket: Optional[int] = None) -> int:
        """新規取引をデータベースに挿入"""
        if entry_time is None:
            entry_time = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades (symbol, side, entry_price, quantity, stop_loss, take_profit, entry_time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
            ''', (symbol, side, entry_price, quantity, stop_loss, take_profit, entry_time))
            trade_id = cursor.lastrowid
            conn.commit()
            return trade_id
    
    def update_trade(self, trade_id: int, **kwargs):
        """取引情報を更新"""
        if not kwargs:
            return
        
        # 更新可能なフィールドのリスト
        allowed_fields = ['exit_price', 'profit_loss', 'status', 'exit_time', 'stop_loss', 'take_profit']
        
        set_clause = []
        values = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                set_clause.append(f"{field} = ?")
                values.append(value)
        
        if not set_clause:
            return
        
        values.append(trade_id)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE trades 
                SET {', '.join(set_clause)}
                WHERE id = ?
            ''', values)
            conn.commit()
    
    def get_trade_by_id(self, trade_id: int) -> Optional[Dict[str, Any]]:
        """IDで取引を取得"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_trades_by_status(self, status: str) -> List[Dict[str, Any]]:
        """ステータスで取引を取得"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM trades 
                WHERE status = ? 
                ORDER BY entry_time DESC
            ''', (status,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_trading_summary(self, days: int = 30) -> Dict[str, Any]:
        """取引サマリーを取得"""
        from datetime import datetime, timedelta
        
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 基本統計
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(profit_loss) as total_profit,
                    AVG(profit_loss) as avg_profit,
                    MAX(profit_loss) as max_profit,
                    MIN(profit_loss) as max_loss
                FROM trades 
                WHERE entry_time >= ? AND status = 'closed'
            ''', (start_date,))
            
            row = cursor.fetchone()
            if row:
                summary = {
                    'total_trades': row[0] or 0,
                    'winning_trades': row[1] or 0,
                    'losing_trades': row[2] or 0,
                    'total_profit': row[3] or 0.0,
                    'avg_profit': row[4] or 0.0,
                    'max_profit': row[5] or 0.0,
                    'max_loss': row[6] or 0.0
                }
            else:
                summary = {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'total_profit': 0.0,
                    'avg_profit': 0.0,
                    'max_profit': 0.0,
                    'max_loss': 0.0
                }
            
            # 勝率計算
            if summary.get('total_trades', 0) > 0:
                summary['win_rate'] = summary['winning_trades'] / summary['total_trades']
            else:
                summary['win_rate'] = 0.0
            
            return summary
    
    def log_system_event(self, level: str, message: str, module: Optional[str] = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_logs (level, message, module)
                VALUES (?, ?, ?)
            ''', (level, message, module))
            conn.commit()

# グローバルインスタンス
db_manager = DatabaseManager()

def get_db_connection():
    """データベース接続を取得する関数"""
    return sqlite3.connect(db_manager.db_path)