"""
予測スクリプト
指定レースの勝率・複勝率を予測してDBに保存する
"""
import sys
import pickle
import logging
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import init_db, Race, Prediction
from db.session import SessionLocal
from model.features import build_features, FEATURE_COLUMNS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "saved_models"
MODEL_VERSION = "lgbm_v1"


def load_models(target: str):
    path = MODEL_DIR / f"lgbm_{target}.pkl"
    if not path.exists():
        raise FileNotFoundError(f"モデルが見つかりません: {path}\n先に train.py を実行してください")
    with open(path, "rb") as f:
        return pickle.load(f)


def predict_race(race_id: int, save_to_db: bool = True) -> list:
    """
    指定レースの予測を実行
    Returns: [{"horse_number": N, "win_prob": 0.xx, "place_prob": 0.xx, "predicted_rank": N}, ...]
    """
    init_db()
    session = SessionLocal()

    try:
        df = build_features(session, race_id)
        if df.empty:
            logger.warning(f"特徴量なし: race_id={race_id}")
            return []

        X = df[FEATURE_COLUMNS]

        # 単勝確率
        win_models = load_models("win")
        win_probs = np.mean([m.predict(X) for m in win_models], axis=0)

        # 複勝確率
        top3_models = load_models("top3")
        place_probs = np.mean([m.predict(X) for m in top3_models], axis=0)

        # 確率を正規化（合計が1になるよう）
        win_probs = win_probs / win_probs.sum()

        df = df.copy()
        df["win_prob"] = win_probs
        df["place_prob"] = place_probs
        df["predicted_rank"] = df["win_prob"].rank(ascending=False).astype(int)
        df = df.sort_values("win_prob", ascending=False)

        results = df[["horse_number", "horse_id", "win_prob", "place_prob", "predicted_rank"]].to_dict("records")

        if save_to_db:
            for r in results:
                existing = (
                    session.query(Prediction)
                    .filter_by(race_id=race_id, horse_id=r["horse_id"])
                    .first()
                )
                if existing:
                    pred = existing
                else:
                    pred = Prediction(race_id=race_id, horse_id=r["horse_id"])
                    session.add(pred)

                pred.horse_number = r["horse_number"]
                pred.win_prob = float(r["win_prob"])
                pred.place_prob = float(r["place_prob"])
                pred.predicted_rank = r["predicted_rank"]
                pred.model_version = MODEL_VERSION

            session.commit()
            logger.info(f"予測保存完了: race_id={race_id}")

        return results

    finally:
        session.close()


def predict_today():
    """当日全レースを予測"""
    from datetime import date
    init_db()
    session = SessionLocal()

    try:
        from datetime import date
        races = session.query(Race).filter(Race.race_date == date.today()).all()
        logger.info(f"本日{len(races)}レースを予測します")

        for race in races:
            logger.info(f"予測: {race.name}")
            results = predict_race(race.id)
            if results:
                logger.info(f"  1位予測: {results[0]['horse_number']}番 (win_prob={results[0]['win_prob']:.1%})")
    finally:
        session.close()


if __name__ == "__main__":
    predict_today()
