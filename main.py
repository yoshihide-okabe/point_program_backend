import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, TIMESTAMP
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, Session
from datetime import datetime
from dotenv import load_dotenv
from typing import List

# ==============================
# 🎯 .env ファイルの読み込み
# ==============================
load_dotenv()

MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = os.getenv("MYSQL_PORT")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")
MYSQL_SSL_CA = os.getenv("MYSQL_SSL_CA")

# 環境変数の読み込み状況（デバッグ用）
print("✅ 環境変数の確認:")
print(f"MYSQL_USER: {MYSQL_USER}")
print(f"MYSQL_HOST: {MYSQL_HOST}")
print(f"MYSQL_DATABASE: {MYSQL_DATABASE}")
print(f"MYSQL_SSL_CA: {MYSQL_SSL_CA}")

# ==============================
# 🎯 MySQL の接続設定
# ==============================
#DATABASE_URL = f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?ssl_ca={MYSQL_SSL_CA}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==============================
# 🎯 データモデル (SQLAlchemy)
# ==============================

class User(Base):
    """ ユーザー情報を管理するテーブル """
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)

#
class UserBalance(Base):
    """ ユーザーのポイント残高を管理するテーブル """
    __tablename__ = "user_balance"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    current_points = Column(Integer, default=0)
    scheduled_points = Column(Integer, default=0)
    expiring_points = Column(Integer, default=0)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

class PointHistory(Base):
    __tablename__ = "point_history"
    """ ユーザーのポイント履歴を管理するテーブル """
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(TIMESTAMP, default=datetime.utcnow)
    description = Column(String(255), nullable=False)
    points = Column(Integer, nullable=False)

class RedeemableItem(Base):
    """ 交換可能なアイテムを管理するテーブル """
    __tablename__ = "redeemable_items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    points_required = Column(Integer, nullable=False)

class RedemptionHistory(Base):
    """ ユーザーのポイント交換履歴を管理するテーブル """
    __tablename__ = "redemption_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("redeemable_items.id"), nullable=False)
    date = Column(TIMESTAMP, default=datetime.utcnow)
    points_spent = Column(Integer, nullable=False)


# ==============================
# 🎯 FastAPI の設定
# ==============================
app = FastAPI()

# CORS設定（フロントエンドとの通信を許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🎯 ルートエンドポイント
@app.get("/")
def read_root():
    return {"message": "Welcome to the Point Management System API!"}

# ==============================
# 🎯 DBセッション取得関数
# ==============================
def get_db():
    """ データベースセッションを取得する関数 """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================
# 🎯 API: ユーザー情報取得
# ==============================
@app.get("/users", response_model=List[dict])
def get_users(db: Session = Depends(get_db)):
    """ ユーザーの一覧を取得する """
    users = db.query(User).all()
    return [{"id": u.id, "name": u.name, "company_name": u.company_name} for u in users]

# ==============================
# 🎯 API: ユーザーのポイント残高取得
# ==============================
@app.get("/users/{user_id}/balance")
def get_user_balance(user_id: int, db: Session = Depends(get_db)):
    """ 指定ユーザーの現在のポイント、付与予定ポイント、失効予定ポイントを取得 """
    balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user_id,
        "current_points": balance.current_points,
        "scheduled_points": balance.scheduled_points,
        "expiring_points": balance.expiring_points,
    }

# ==============================
# 🎯 API: ユーザーのポイント履歴取得
# ==============================
@app.get("/users/{user_id}/points/history", response_model=List[dict])
def get_point_history(user_id: int, db: Session = Depends(get_db)):
    """ 指定ユーザーのポイント履歴を取得する """
    history = db.query(PointHistory).filter(PointHistory.user_id == user_id).all()
    return [
        {"date": h.date, "description": h.description, "points": h.points}
        for h in history
    ]

# ==============================
# 🎯 API: ポイント交換処理
# ==============================
@app.post("/users/{user_id}/redeem/{item_id}")
def redeem_points(user_id: int, item_id: int, db: Session = Depends(get_db)):
    """ ユーザーがポイントを使ってアイテムを交換する処理 """
    
    # 交換可能なアイテムを取得
    item = db.query(RedeemableItem).filter(RedeemableItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # ユーザーの残高を取得
    balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="User not found")

    # 必要なポイントが足りるか確認
    if balance.current_points < item.points_required:
        raise HTTPException(status_code=400, detail="Not enough points")

    # ポイントを減算
    balance.current_points -= item.points_required

    # 交換履歴を追加
    redemption = RedemptionHistory(user_id=user_id, item_id=item_id, points_spent=item.points_required)
    db.add(redemption)

    # ポイント履歴を追加
    history = PointHistory(user_id=user_id, description="ポイント交換", points=-item.points_required)
    db.add(history)

    # 変更をデータベースに保存
    db.commit()

    return {"message": "ポイント交換が完了しました", "new_balance": balance.current_points}


# ==============================
# 🎯 FastAPI の起動コマンド
# ==============================
# uvicorn main:app --reload
