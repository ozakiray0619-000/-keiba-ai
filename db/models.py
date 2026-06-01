"""
データベースモデル定義
馬・レース・出走・成績テーブル
"""
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    ForeignKey, Text, Boolean, create_engine
)
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Horse(Base):
    """馬マスタ"""
    __tablename__ = "horses"

    id = Column(Integer, primary_key=True)
    netkeiba_id = Column(String(20), unique=True, nullable=False)  # netkeibaの馬ID
    name = Column(String(100), nullable=False)
    birthday = Column(Date, nullable=True)
    sex = Column(String(5), nullable=True)       # 牡/牝/セン
    color = Column(String(20), nullable=True)    # 毛色
    trainer = Column(String(50), nullable=True)
    owner = Column(String(100), nullable=True)
    breeder = Column(String(100), nullable=True)
    sire = Column(String(100), nullable=True)    # 父
    dam = Column(String(100), nullable=True)     # 母
    dam_sire = Column(String(100), nullable=True)  # 母父
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    results = relationship("RaceResult", back_populates="horse")
    entries = relationship("RaceEntry", back_populates="horse")


class Race(Base):
    """レースマスタ"""
    __tablename__ = "races"

    id = Column(Integer, primary_key=True)
    netkeiba_race_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    race_date = Column(Date, nullable=False)
    venue = Column(String(50), nullable=True)    # 開催場所（東京・阪神等）
    race_number = Column(Integer, nullable=True)
    course_type = Column(String(10), nullable=True)  # 芝/ダート
    distance = Column(Integer, nullable=True)    # 距離（m）
    direction = Column(String(10), nullable=True)  # 右/左
    weather = Column(String(20), nullable=True)
    track_condition = Column(String(20), nullable=True)  # 良/稍重/重/不良
    grade = Column(String(20), nullable=True)    # G1/G2/G3/オープン等
    prize_money = Column(Float, nullable=True)   # 1着賞金（万円）
    num_horses = Column(Integer, nullable=True)  # 出走頭数
    created_at = Column(DateTime, default=datetime.now)

    results = relationship("RaceResult", back_populates="race")
    entries = relationship("RaceEntry", back_populates="race")


class RaceResult(Base):
    """レース結果（確定後）"""
    __tablename__ = "race_results"

    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    horse_id = Column(Integer, ForeignKey("horses.id"), nullable=False)
    finish_position = Column(Integer, nullable=True)   # 着順
    gate_number = Column(Integer, nullable=True)       # 枠番
    horse_number = Column(Integer, nullable=True)      # 馬番
    jockey = Column(String(50), nullable=True)
    weight_carried = Column(Float, nullable=True)      # 斤量
    horse_weight = Column(Integer, nullable=True)      # 馬体重
    horse_weight_diff = Column(Integer, nullable=True) # 馬体重増減
    finish_time = Column(Float, nullable=True)         # タイム（秒）
    margin = Column(String(20), nullable=True)         # 着差
    last_3f = Column(Float, nullable=True)             # 上がり3F
    odds = Column(Float, nullable=True)                # 単勝オッズ
    popularity = Column(Integer, nullable=True)        # 人気
    corner_positions = Column(String(50), nullable=True)  # コーナー通過順
    created_at = Column(DateTime, default=datetime.now)

    race = relationship("Race", back_populates="results")
    horse = relationship("Horse", back_populates="results")


class RaceEntry(Base):
    """出走表（レース前・予測用）"""
    __tablename__ = "race_entries"

    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    horse_id = Column(Integer, ForeignKey("horses.id"), nullable=False)
    gate_number = Column(Integer, nullable=True)
    horse_number = Column(Integer, nullable=True)
    jockey = Column(String(50), nullable=True)
    weight_carried = Column(Float, nullable=True)
    horse_weight = Column(Integer, nullable=True)
    horse_weight_diff = Column(Integer, nullable=True)
    odds = Column(Float, nullable=True)
    popularity = Column(Integer, nullable=True)
    is_scratched = Column(Boolean, default=False)  # 取消フラグ
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    race = relationship("Race", back_populates="entries")
    horse = relationship("Horse", back_populates="entries")


class Prediction(Base):
    """予測結果"""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    horse_id = Column(Integer, ForeignKey("horses.id"), nullable=False)
    horse_number = Column(Integer, nullable=True)
    win_prob = Column(Float, nullable=True)        # 単勝確率
    place_prob = Column(Float, nullable=True)      # 複勝確率
    predicted_rank = Column(Integer, nullable=True)
    model_version = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


def init_db(db_path: str = "keiba.db"):
    """DBを初期化してテーブルを作成"""
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    print(f"DB初期化完了: {db_path}")
    return engine


if __name__ == "__main__":
    init_db()
