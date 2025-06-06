from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api.market_data import router as market_data_router
from app.api.analysis import router as analysis_router
from app.api.trading import router as trading_router
from app.api.reports import router as reports_router

setup_logging()
logger = get_logger()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market_data_router)
app.include_router(analysis_router)
app.include_router(trading_router)
app.include_router(reports_router)

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Shutting down {settings.PROJECT_NAME}")

@app.get("/")
async def root():
    return {"message": f"{settings.PROJECT_NAME} API"}

@app.get("/status")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "config": {
            "max_positions": settings.MAX_POSITIONS,
            "currency_pairs": settings.CURRENCY_PAIRS,
            "update_interval": settings.UPDATE_INTERVAL
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )