"""
FastAPI バックエンド
フロントエンドに予測結果・レース情報を提供するREST API
"""
import sys
import logging
from pathlib import Path
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import init_db, Race, Horse, RaceEntry, RaceResult, Prediction
from db.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="競馬予測API", version="1.0.0")

# フロントエンド（localhost:5173）からのアクセスを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydanticスキーマ ─────────────────────────────────

class RaceInfo(BaseModel):
    id: int
    netkeiba_race_id: str
    name: str
    race_date: str
    venue: Optional[str]
    race_number: Optional[int]
    course_type: Optional[str]
    distance: Optional[int]
    num_horses: Optional[int]


class EntryInfo(BaseModel):
    horse_number: Optional[int]
    horse_name: str
    jockey: Optional[str]
    horse_weight: Optional[int]
    horse_weight_diff: Optional[int]
    odds: Optional[float]
    popularity: Optional[int]
    win_prob: Optional[float] = None
    place_prob: Optional[float] = None
    predicted_rank: Optional[int] = None


class RaceDetail(BaseModel):
    race: RaceInfo
    entries: List[EntryInfo]


# ─── エンドポイント ───────────────────────────────────

@app.get("/")
def root():
    return {"message": "競馬予測API 稼働中"}


@app.get("/races", response_model=List[RaceInfo])
def get_races(race_date: Optional[str] = None):
    """レース一覧を返す。race_date=YYYY-MM-DD で絞り込み"""
    session = SessionLocal()
    try:
        q = session.query(Race)
        if race_date:
            q = q.filter(Race.race_date == date.fromisoformat(race_date))
        else:
            q = q.filter(Race.race_date == date.today())
        races = q.order_by(Race.race_number).all()

        return [
            RaceInfo(
                id=r.id,
                netkeiba_race_id=r.netkeiba_race_id,
                name=r.name,
                race_date=str(r.race_date),
                venue=r.venue,
                race_number=r.race_number,
                course_type=r.course_type,
                distance=r.distance,
                num_horses=r.num_horses,
            )
            for r in races
        ]
    finally:
        session.close()


@app.get("/races/{race_id}", response_model=RaceDetail)
def get_race_detail(race_id: int):
    """レース詳細＋出走馬＋予測結果"""
    session = SessionLocal()
    try:
        race = session.get(Race, race_id)
        if not race:
            raise HTTPException(status_code=404, detail="Race not found")

        entries = session.query(RaceEntry).filter_by(race_id=race_id).all()
        predictions = {
            p.horse_id: p
            for p in session.query(Prediction).filter_by(race_id=race_id).all()
        }

        entry_list = []
        for e in sorted(entries, key=lambda x: x.horse_number or 99):
            pred = predictions.get(e.horse_id)
            entry_list.append(
                EntryInfo(
                    horse_number=e.horse_number,
                    horse_name=e.horse.name if e.horse else "不明",
                    jockey=e.jockey,
                    horse_weight=e.horse_weight,
                    horse_weight_diff=e.horse_weight_diff,
                    odds=e.odds,
                    popularity=e.popularity,
                    win_prob=pred.win_prob if pred else None,
                    place_prob=pred.place_prob if pred else None,
                    predicted_rank=pred.predicted_rank if pred else None,
                )
            )

        return RaceDetail(
            race=RaceInfo(
                id=race.id,
                netkeiba_race_id=race.netkeiba_race_id,
                name=race.name,
                race_date=str(race.race_date),
                venue=race.venue,
                race_number=race.race_number,
                course_type=race.course_type,
                distance=race.distance,
                num_horses=race.num_horses,
            ),
            entries=entry_list,
        )
    finally:
        session.close()


@app.post("/predict/{race_id}")
def run_prediction(race_id: int):
    """指定レースの予測を実行してDBに保存"""
    try:
        from model.predict import predict_race
        results = predict_race(race_id)
        return {"race_id": race_id, "predictions": results, "count": len(results)}
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
