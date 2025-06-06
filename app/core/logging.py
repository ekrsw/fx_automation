import logging
import logging.handlers
import os
from datetime import datetime
from .config import settings

def setup_logging():
    log_dir = os.path.dirname(settings.LOG_FILE)
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.handlers.RotatingFileHandler(
                settings.LOG_FILE,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            ),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger("fx_trading")
    logger.info(f"Logging initialized - Level: {settings.LOG_LEVEL}")
    return logger

def get_logger(name: str = "fx_trading") -> logging.Logger:
    return logging.getLogger(name)