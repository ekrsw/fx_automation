"""
CSV履歴データインポートAPI
MT5やその他のソースからエクスポートしたCSVファイルをインポート
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import pandas as pd
import logging
from io import StringIO

from app.core.database import get_db_connection

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/csv/import")
async def import_csv_data(
    file: UploadFile = File(...),
    symbol: str = Form(...),
    date_column: str = Form("Date"),
    time_column: Optional[str] = Form(None),
    open_column: str = Form("Open"),
    high_column: str = Form("High"),
    low_column: str = Form("Low"),
    close_column: str = Form("Close"),
    volume_column: str = Form("Volume"),
    datetime_format: str = Form("%Y.%m.%d %H:%M:%S")
):
    """
    CSVファイルから履歴データをインポート
    
    MT5の標準エクスポート形式に対応:
    Date,Time,Open,High,Low,Close,Volume
    2024.01.01,00:00,143.123,143.456,143.000,143.234,1000
    """
    try:
        # ファイルタイプチェック
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="CSVファイルのみ対応しています")
        
        # ファイル読み込み
        contents = await file.read()
        csv_data = contents.decode('utf-8')
        
        # Pandas DataFrameに変換
        df = pd.read_csv(StringIO(csv_data))
        
        logger.info(f"CSVファイル読み込み完了: {len(df)}行, カラム: {list(df.columns)}")
        
        # 必要なカラムの存在確認
        required_columns = [date_column, open_column, high_column, low_column, close_column]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise HTTPException(
                status_code=400, 
                detail=f"必要なカラムが見つかりません: {missing_columns}"
            )
        
        # データ変換
        processed_data = await process_csv_data(
            df, symbol, date_column, time_column, 
            open_column, high_column, low_column, close_column, volume_column,
            datetime_format
        )
        
        # データベースに保存
        saved_count = await save_csv_data(symbol, processed_data)
        
        return {
            "status": "success",
            "message": f"{symbol} の履歴データをインポートしました",
            "symbol": symbol,
            "total_rows": len(df),
            "saved_rows": saved_count,
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"CSVインポートエラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"CSVインポートに失敗: {str(e)}")

async def process_csv_data(
    df: pd.DataFrame, 
    symbol: str, 
    date_col: str, 
    time_col: Optional[str],
    open_col: str, 
    high_col: str, 
    low_col: str, 
    close_col: str, 
    volume_col: str,
    datetime_format: str
) -> pd.DataFrame:
    """
    CSVデータを処理してデータベース形式に変換
    """
    try:
        # タイムスタンプ列を作成
        if time_col and time_col in df.columns:
            # 日付と時刻が別カラムの場合
            df['datetime'] = df[date_col].astype(str) + ' ' + df[time_col].astype(str)
        else:
            # 日付のみの場合
            df['datetime'] = df[date_col].astype(str)
        
        # 日時形式を統一
        if datetime_format == "%Y.%m.%d %H:%M:%S":
            # MT5形式の場合
            df['timestamp'] = pd.to_datetime(df['datetime'], format=datetime_format, errors='coerce')
        else:
            # その他の形式
            df['timestamp'] = pd.to_datetime(df['datetime'], errors='coerce')
        
        # 無効な日時データを除去
        df = df.dropna(subset=['timestamp'])
        
        # 数値データを変換
        numeric_columns = {
            'open': open_col,
            'high': high_col,
            'low': low_col,
            'close': close_col
        }
        
        for new_col, orig_col in numeric_columns.items():
            df[new_col] = pd.to_numeric(df[orig_col], errors='coerce')
        
        # ボリュームカラムの処理
        if volume_col in df.columns:
            df['volume'] = pd.to_numeric(df[volume_col], errors='coerce').fillna(0)
        else:
            df['volume'] = 0
        
        # 必要なカラムのみ選択
        result_df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
        
        # 重複削除とソート
        result_df = result_df.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
        
        logger.info(f"データ処理完了: {len(result_df)}行 (元データ: {len(df)}行)")
        
        return result_df
        
    except Exception as e:
        logger.error(f"CSVデータ処理エラー: {str(e)}")
        raise

async def save_csv_data(symbol: str, df: pd.DataFrame) -> int:
    """
    処理済みCSVデータをデータベースに保存
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        saved_count = 0
        skipped_count = 0
        
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO market_data 
                    (symbol, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    row['timestamp'].isoformat(),
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume'])
                ))
                
                if cursor.rowcount > 0:
                    saved_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                logger.warning(f"行スキップ: {row['timestamp']} - {str(e)}")
                skipped_count += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"CSV保存完了: {symbol} - 保存: {saved_count}行, スキップ: {skipped_count}行")
        
        return saved_count
        
    except Exception as e:
        logger.error(f"CSVデータ保存エラー: {str(e)}")
        return 0

@router.get("/csv/template")
async def get_csv_template():
    """
    CSVテンプレートの説明を取得
    """
    return {
        "mt5_format": {
            "description": "MetaTrader 5の標準エクスポート形式",
            "columns": ["Date", "Time", "Open", "High", "Low", "Close", "Volume"],
            "example": "2024.01.01,00:00,143.123,143.456,143.000,143.234,1000",
            "datetime_format": "%Y.%m.%d %H:%M:%S"
        },
        "generic_format": {
            "description": "一般的なOHLCデータ形式", 
            "columns": ["DateTime", "Open", "High", "Low", "Close", "Volume"],
            "example": "2024-01-01 00:00:00,143.123,143.456,143.000,143.234,1000",
            "datetime_format": "%Y-%m-%d %H:%M:%S"
        },
        "required_parameters": {
            "symbol": "通貨ペアコード (例: USDJPY)",
            "date_column": "日付カラム名 (デフォルト: Date)",
            "time_column": "時刻カラム名 (オプション)",
            "open_column": "始値カラム名 (デフォルト: Open)",
            "high_column": "高値カラム名 (デフォルト: High)", 
            "low_column": "安値カラム名 (デフォルト: Low)",
            "close_column": "終値カラム名 (デフォルト: Close)",
            "volume_column": "出来高カラム名 (デフォルト: Volume)",
            "datetime_format": "日時フォーマット (デフォルト: %Y.%m.%d %H:%M:%S)"
        }
    }