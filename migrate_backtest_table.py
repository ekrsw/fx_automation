#!/usr/bin/env python3
"""
バックテストテーブルに新しいカラムを追加するマイグレーションスクリプト
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_backtest_table():
    """
    バックテストテーブルに初期資金、最終資金、レバレッジカラムを追加
    """
    try:
        conn = sqlite3.connect('fx_trading.db')
        cursor = conn.cursor()
        
        # 既存のカラムを確認
        cursor.execute("PRAGMA table_info(backtest_results)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        # 新しいカラムを追加（存在しない場合のみ）
        if 'initial_balance' not in column_names:
            cursor.execute("""
                ALTER TABLE backtest_results 
                ADD COLUMN initial_balance REAL DEFAULT 100000
            """)
            logger.info("initial_balance カラムを追加しました")
        
        if 'final_balance' not in column_names:
            cursor.execute("""
                ALTER TABLE backtest_results 
                ADD COLUMN final_balance REAL
            """)
            logger.info("final_balance カラムを追加しました")
        
        if 'leverage' not in column_names:
            cursor.execute("""
                ALTER TABLE backtest_results 
                ADD COLUMN leverage REAL DEFAULT 1.0
            """)
            logger.info("leverage カラムを追加しました")
        
        # 既存のレコードの final_balance を計算して更新
        cursor.execute("""
            UPDATE backtest_results 
            SET final_balance = initial_balance + total_profit
            WHERE final_balance IS NULL
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("マイグレーション完了")
        
    except Exception as e:
        logger.error(f"マイグレーションエラー: {str(e)}")
        raise

if __name__ == "__main__":
    migrate_backtest_table()