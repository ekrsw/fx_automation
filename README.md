# FX自動売買システム - フェーズ2完了

## 📋 プロジェクト概要
ダウ理論とエリオット波動理論に基づくFX自動売買システムのPython FastAPI基盤とMQL5 EA実装

## 🗂️ プロジェクト構造
```
FX_automation/
├── app/
│   ├── core/
│   │   ├── config.py          # 設定管理
│   │   ├── logging.py         # ログ機能
│   │   └── database.py        # SQLiteデータベース
│   ├── api/
│   │   ├── market_data.py     # 市場データAPI
│   │   └── analysis.py        # テクニカル分析API
│   ├── models/
│   │   └── market_data.py     # データモデル
│   └── services/
│       └── technical_analysis.py  # テクニカル分析サービス
├── mql5/
│   ├── FX_Trading_EA.mq5      # MetaTrader 5 Expert Advisor
│   └── README.md              # EA セットアップガイド
├── docs/                      # 要件定義書
├── logs/                      # ログファイル
├── main.py                    # FastAPIアプリケーション
├── test_communication.py     # 通信テストスクリプト
└── requirements.txt           # Python依存関係
```

## 🚀 セットアップ手順

### 1. Python環境セットアップ
```bash
# 依存関係インストール
pip install -r requirements.txt

# FastAPIサーバー起動
python main.py
```

### 2. MQL5 EA セットアップ
1. MetaTrader 5でWebRequestを有効化
2. `mql5/FX_Trading_EA.mq5`をコンパイル
3. USDJPY チャートにEAを適用

詳細は `mql5/README.md` を参照

### 3. 通信テスト実行
```bash
python test_communication.py
```

## 🔧 API エンドポイント

### 基本API
- `GET /status` - システム状態確認
- `GET /api/v1/system-status` - 詳細システム状態

### 市場データAPI  
- `POST /api/v1/market-data` - MT5からのデータ受信
- `GET /api/v1/market-data/{symbol}` - 過去データ取得

### テクニカル分析API
- `GET /api/v1/analysis/{symbol}` - 包括的テクニカル分析
- `GET /api/v1/swing-points/{symbol}` - スイングポイント取得
- `GET /api/v1/zigzag/{symbol}` - ZigZagインジケータ
- `GET /api/v1/trend/{symbol}` - トレンド分析

## 📊 実装済み機能

### フェーズ1: 基本インフラ ✅
- FastAPI基盤とヘルスチェックAPI
- ログ機能とSQLiteデータベース
- 基本的なAPIエンドポイント

### フェーズ2: シングルペア分析 ✅  
- MQL5 EA（HTTP通信機能）
- MetaTraderとの基本接続
- USD/JPY価格データ取得
- Python-MQL5間通信テスト
- ダウ理論スイングポイント検出
- 高値・安値切り上げ/切り下げ判定
- ZigZagインジケータ実装

### フェーズ3: 実取引機能 ✅
- 注文機能（成行注文実行）
- ストップロス・テイクプロフィット設定
- ポジション管理
- リスク管理（2%リスク計算、15%ドローダウン監視）
- ポジションサイズ計算機能
- 取引履歴記録とトラッキング

## 🔍 テクニカル分析機能

### ダウ理論分析
- スイングポイント自動検出
- 高値・安値の切り上げ/切り下げ判定
- トレンド方向判定（上昇/下降/横ばい）
- トレンド強度スコア（0-30点）

### ZigZagインジケータ
- 設定可能な偏差パラメータ
- ピーク・トラフポイント検出
- ノイズフィルタリング

## 💼 取引管理機能

### リスク管理システム
- ポジションサイズ自動計算（2%リスクベース）
- ドローダウン監視（15%制限）
- 最大ポジション数制限（3ペア）
- リスクリワード比率計算

### 取引実行機能
- 成行注文・指値注文・逆指値注文
- ストップロス・テイクプロフィット自動設定
- ポジション修正・部分決済
- 取引シグナル検証システム

### レポート機能
- 取引履歴とサマリー
- パフォーマンス指標（勝率、プロフィットファクター）
- 日次損益レポート
- リスクエクスポージャー監視

## 📈 次のステップ（フェーズ4: マルチペア対応）

### 実装予定機能
1. 6ペア同時監視（全通貨ペア対応）
2. 相関調整機能
3. 3ペア選択ロジック（100点満点スコアリング）
4. 動的ポジション入替システム

## 🧪 テスト方法

### 基本通信テスト
```bash
# サーバー起動後
curl http://localhost:8000/status

# 市場データ確認
curl http://localhost:8000/api/v1/market-data/USDJPY
```

### テクニカル分析テスト
```bash
# スイングポイント取得
curl http://localhost:8000/api/v1/swing-points/USDJPY

# トレンド分析
curl http://localhost:8000/api/v1/trend/USDJPY
```

## 📝 設定

### 環境変数（.env）
```env
HOST=127.0.0.1
PORT=8000
LOG_LEVEL=INFO
MAX_POSITIONS=3
RISK_PER_TRADE=0.02
MAX_DRAWDOWN=0.15
UPDATE_INTERVAL=300
```

## 🎯 現在の達成状況
- ✅ Python-MQL5間でUSD/JPYの価格データが正常に送受信
- ✅ ダウ理論に基づくトレンド判定機能
- ✅ ZigZagインジケータによる転換点検出
- ✅ RESTful API による分析結果提供

フェーズ2の目標「USD/JPY単一ペアでのダウ理論・エリオット波動基本実装」が完了しました。