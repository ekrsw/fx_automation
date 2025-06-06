from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "FX Trading System"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "ダウ理論・エリオット波動理論ベースの自動売買システム"
    
    API_V1_STR: str = "/api/v1"
    
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/fx_trading.log"
    
    DATABASE_URL: str = "sqlite:///./fx_trading.db"
    
    ALLOWED_HOSTS: List[str] = ["*"]
    
    MAX_POSITIONS: int = 3
    CURRENCY_PAIRS: List[str] = ["USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD"]
    
    RISK_PER_TRADE: float = 0.02
    MAX_DRAWDOWN: float = 0.15
    
    UPDATE_INTERVAL: int = 300  # 5分（秒）
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()