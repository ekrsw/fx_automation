"""
アラート・監視システムAPI
リアルタイム通知とシステム監視機能を提供
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import logging
from enum import Enum

from app.core.database import get_db_connection
from app.services.monitoring_service import MonitoringService

router = APIRouter()
logger = logging.getLogger(__name__)

class AlertType(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    TRADE = "trade"
    SYSTEM = "system"

class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

class Alert(BaseModel):
    id: Optional[int] = None
    type: AlertType
    title: str
    message: str
    symbol: Optional[str] = None
    severity: int  # 1-10 (10が最重要)
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class AlertRule(BaseModel):
    id: Optional[int] = None
    name: str
    description: str
    condition: str  # JSON形式の条件
    alert_type: AlertType
    severity: int
    is_active: bool = True
    cooldown_minutes: int = 5  # 同じアラートの再送間隔
    created_at: Optional[datetime] = None

class MonitoringThreshold(BaseModel):
    metric_name: str
    threshold_value: float
    comparison_operator: str  # >, <, >=, <=, ==
    alert_type: AlertType
    severity: int

@router.post("/alerts", response_model=Dict[str, Any])
async def create_alert(alert: Alert, background_tasks: BackgroundTasks):
    """
    新しいアラートを作成
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # アラートをデータベースに保存
        cursor.execute("""
            INSERT INTO alerts (type, title, message, symbol, severity, status, 
                              created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert.type.value,
            alert.title,
            alert.message,
            alert.symbol,
            alert.severity,
            alert.status.value,
            datetime.now(),
            json.dumps(alert.metadata) if alert.metadata else None
        ))
        
        alert_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # バックグラウンドでアラート処理を実行
        background_tasks.add_task(process_alert, alert_id)
        
        logger.info(f"アラート作成: {alert.title} (重要度: {alert.severity})")
        
        return {
            "alert_id": alert_id,
            "status": "created",
            "message": "アラートが正常に作成されました"
        }
        
    except Exception as e:
        logger.error(f"アラート作成エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"アラート作成に失敗しました: {str(e)}")

@router.get("/alerts", response_model=List[Dict[str, Any]])
async def get_alerts(
    status: Optional[AlertStatus] = None,
    alert_type: Optional[AlertType] = None,
    symbol: Optional[str] = None,
    limit: int = 100
):
    """
    アラート一覧を取得
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # クエリ構築
        query = "SELECT * FROM alerts WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status.value)
            
        if alert_type:
            query += " AND type = ?"
            params.append(alert_type.value)
            
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
            
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        alerts = []
        for row in rows:
            alert_data = {
                "id": row[0],
                "type": row[1],
                "title": row[2],
                "message": row[3],
                "symbol": row[4],
                "severity": row[5],
                "status": row[6],
                "created_at": row[7],
                "acknowledged_at": row[8],
                "resolved_at": row[9],
                "metadata": json.loads(row[10]) if row[10] else None
            }
            alerts.append(alert_data)
        
        return alerts
        
    except Exception as e:
        logger.error(f"アラート取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"アラート取得に失敗しました: {str(e)}")

@router.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int):
    """
    アラートを確認済みにする
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE alerts 
            SET status = ?, acknowledged_at = ?
            WHERE id = ?
        """, (AlertStatus.ACKNOWLEDGED.value, datetime.now(), alert_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="アラートが見つかりません")
        
        conn.commit()
        conn.close()
        
        logger.info(f"アラート確認: ID={alert_id}")
        
        return {
            "alert_id": alert_id,
            "status": "acknowledged",
            "message": "アラートが確認済みになりました"
        }
        
    except Exception as e:
        logger.error(f"アラート確認エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"アラート確認に失敗しました: {str(e)}")

@router.put("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int):
    """
    アラートを解決済みにする
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE alerts 
            SET status = ?, resolved_at = ?
            WHERE id = ?
        """, (AlertStatus.RESOLVED.value, datetime.now(), alert_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="アラートが見つかりません")
        
        conn.commit()
        conn.close()
        
        logger.info(f"アラート解決: ID={alert_id}")
        
        return {
            "alert_id": alert_id,
            "status": "resolved",
            "message": "アラートが解決済みになりました"
        }
        
    except Exception as e:
        logger.error(f"アラート解決エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"アラート解決に失敗しました: {str(e)}")

@router.get("/alerts/active/count")
async def get_active_alerts_count():
    """
    アクティブなアラート数を取得
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT type, COUNT(*) as count
            FROM alerts 
            WHERE status = 'active'
            GROUP BY type
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        counts = {row[0]: row[1] for row in rows}
        total = sum(counts.values())
        
        return {
            "total": total,
            "by_type": counts,
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"アクティブアラート数取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"アクティブアラート数取得に失敗しました: {str(e)}")

@router.post("/monitoring/rules", response_model=Dict[str, Any])
async def create_monitoring_rule(rule: AlertRule):
    """
    監視ルールを作成
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO alert_rules (name, description, condition, alert_type, 
                                   severity, is_active, cooldown_minutes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rule.name,
            rule.description,
            rule.condition,
            rule.alert_type.value,
            rule.severity,
            rule.is_active,
            rule.cooldown_minutes,
            datetime.now()
        ))
        
        rule_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"監視ルール作成: {rule.name}")
        
        return {
            "rule_id": rule_id,
            "status": "created",
            "message": "監視ルールが正常に作成されました"
        }
        
    except Exception as e:
        logger.error(f"監視ルール作成エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"監視ルール作成に失敗しました: {str(e)}")

@router.get("/monitoring/rules")
async def get_monitoring_rules():
    """
    監視ルール一覧を取得
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM alert_rules 
            ORDER BY created_at DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        rules = []
        for row in rows:
            rule_data = {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "condition": row[3],
                "alert_type": row[4],
                "severity": row[5],
                "is_active": bool(row[6]),
                "cooldown_minutes": row[7],
                "created_at": row[8]
            }
            rules.append(rule_data)
        
        return rules
        
    except Exception as e:
        logger.error(f"監視ルール取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"監視ルール取得に失敗しました: {str(e)}")

@router.get("/monitoring/system-health")
async def get_system_health():
    """
    システムヘルス状態を取得
    """
    try:
        monitoring_service = MonitoringService()
        health_data = await monitoring_service.get_system_health()
        
        return health_data
        
    except Exception as e:
        logger.error(f"システムヘルス取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"システムヘルス取得に失敗しました: {str(e)}")

@router.post("/monitoring/check")
async def run_monitoring_check(background_tasks: BackgroundTasks):
    """
    手動監視チェックを実行
    """
    try:
        background_tasks.add_task(run_all_monitoring_checks)
        
        return {
            "status": "started",
            "message": "監視チェックをバックグラウンドで開始しました"
        }
        
    except Exception as e:
        logger.error(f"監視チェック開始エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"監視チェック開始に失敗しました: {str(e)}")

# バックグラウンド処理関数
async def process_alert(alert_id: int):
    """
    アラートを処理する（通知送信など）
    """
    try:
        # アラート情報を取得
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
        alert_data = cursor.fetchone()
        conn.close()
        
        if not alert_data:
            return
        
        # 重要度に応じて処理を分岐
        severity = alert_data[5]
        alert_type = alert_data[1]
        
        if severity >= 8:  # 重要度8以上は即座に処理
            logger.critical(f"重要アラート: {alert_data[2]} - {alert_data[3]}")
            # TODO: 緊急通知の実装（メール、Slack等）
            
        elif severity >= 5:  # 重要度5以上は警告ログ
            logger.warning(f"警告アラート: {alert_data[2]} - {alert_data[3]}")
            
        else:  # その他は情報ログ
            logger.info(f"情報アラート: {alert_data[2]} - {alert_data[3]}")
        
        # アラート統計を更新
        monitoring_service = MonitoringService()
        await monitoring_service.update_alert_statistics(alert_id, alert_type, severity)
        
    except Exception as e:
        logger.error(f"アラート処理エラー: {str(e)}")

async def run_all_monitoring_checks():
    """
    すべての監視チェックを実行
    """
    try:
        monitoring_service = MonitoringService()
        await monitoring_service.run_all_checks()
        
    except Exception as e:
        logger.error(f"監視チェック実行エラー: {str(e)}")