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
    
    def log_system_event(self, level: str, message: str, module: Optional[str] = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_logs (level, message, module)
                VALUES (?, ?, ?)
            ''', (level, message, module))
            conn.commit()

db_manager = DatabaseManager()