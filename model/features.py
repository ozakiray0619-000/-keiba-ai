"""
特徴量エンジニアリング
DBから馬・レース情報を読み取り、モデル用の特徴量を生成する
"""
import pandas as pd
import numpy as np
import logging
from sqlalchemy.orm import Session
from typing import List

logger = logging.getLogger(__name__)


def build_features(session: Session, race_id: int) -> pd.DataFrame:
    """
    指定レースの特徴量DataFrameを生成
    Returns: pd.DataFrame (1行=1頭)
    """
    from db.models import Race, RaceEntry, RaceResult, Horse

    race = session.get(Race, race_id)
    if race is None:
        raise ValueError(f"Race not found: {race_id}")

    entries = session.query(RaceEntry).filter_by(race_id=race_id).all()
    rows = []

    for entry in entries:
        horse = entry.horse
        row = {
            # 識別
            "race_id": race_id,
            "horse_id": horse.id,
            "horse_number": entry.horse_number,
            # レース条件
            "distance": race.distance or 0,
            "course_type": 1 if race.course_type == "芝" else 0,
            "venue_code": _venue_to_code(race.venue),
            # 出走時情報
            "gate_number": entry.gate_number or 0,
            "weight_carried": entry.weight_carried or 55.0,
            "horse_weight": entry.horse_weight or 470,
            "horse_weight_diff": entry.horse_weight_diff or 0,
            "odds": entry.odds or 99.0,
            "popularity": entry.popularity or 18,
        }

        # 過去成績から特徴量を計算
        past = _get_past_results(session, horse.id, race.race_date, limit=10)
        row.update(_calc_horse_features(past, race))

        # 騎手特徴量
        row.update(_calc_jockey_features(session, entry.jockey, race.race_date))

        rows.append(row)

    df = pd.DataFrame(rows)
    df = df.fillna(0)
    return df


def _venue_to_code(venue: str) -> int:
    mapping = {
        "札幌": 1, "函館": 2, "福島": 3, "新潟": 4,
        "東京": 5, "中山": 6, "中京": 7, "京都": 8,
        "阪神": 9, "小倉": 10,
    }
    return mapping.get(venue or "", 0)


def _get_past_results(session: Session, horse_id: int, before_date, limit: int = 10):
    """過去N走の成績を取得"""
    from db.models import RaceResult, Race
    results = (
        session.query(RaceResult, Race)
        .join(Race, RaceResult.race_id == Race.id)
        .filter(RaceResult.horse_id == horse_id, Race.race_date < before_date)
        .order_by(Race.race_date.desc())
        .limit(limit)
        .all()
    )
    return results


def _calc_horse_features(past_results, current_race) -> dict:
    """過去成績から特徴量を計算"""
    if not past_results:
        return {
            "past_races_count": 0,
            "win_rate": 0.0,
            "top3_rate": 0.0,
            "avg_finish_pos": 10.0,
            "avg_last_3f": 37.0,
            "days_since_last_race": 999,
            "same_distance_win_rate": 0.0,
            "same_course_win_rate": 0.0,
            "avg_odds": 50.0,
            "best_finish": 18,
        }

    positions = []
    last_3fs = []
    same_dist_results = []
    same_course_results = []
    import datetime

    for result, race in past_results:
        pos = result.finish_position
        if pos:
            positions.append(pos)
        if result.last_3f:
            last_3fs.append(result.last_3f)

        if race.distance and current_race.distance:
            if abs(race.distance - current_race.distance) <= 200:
                same_dist_results.append(pos or 99)
        if race.course_type == current_race.course_type:
            same_course_results.append(pos or 99)

    n = len(positions)
    wins = sum(1 for p in positions if p == 1)
    top3 = sum(1 for p in positions if p and p <= 3)

    # 最後のレースからの日数
    last_race_date = past_results[0][1].race_date if past_results else None
    days_since = 999
    if last_race_date and current_race.race_date:
        days_since = (current_race.race_date - last_race_date).days

    return {
        "past_races_count": n,
        "win_rate": wins / n if n > 0 else 0.0,
        "top3_rate": top3 / n if n > 0 else 0.0,
        "avg_finish_pos": np.mean(positions) if positions else 10.0,
        "avg_last_3f": np.mean(last_3fs) if last_3fs else 37.0,
        "days_since_last_race": days_since,
        "same_distance_win_rate": sum(1 for p in same_dist_results if p == 1) / len(same_dist_results) if same_dist_results else 0.0,
        "same_course_win_rate": sum(1 for p in same_course_results if p == 1) / len(same_course_results) if same_course_results else 0.0,
        "avg_odds": np.mean([r[0].odds for r in past_results if r[0].odds]) or 50.0,
        "best_finish": min(positions) if positions else 18,
    }


def _calc_jockey_features(session: Session, jockey_name: str, before_date) -> dict:
    """騎手の過去成績から特徴量を計算"""
    from db.models import RaceResult, Race

    if not jockey_name:
        return {"jockey_win_rate": 0.1, "jockey_top3_rate": 0.3}

    results = (
        session.query(RaceResult)
        .join(Race, RaceResult.race_id == Race.id)
        .filter(RaceResult.jockey == jockey_name, Race.race_date < before_date)
        .limit(100)
        .all()
    )

    if not results:
        return {"jockey_win_rate": 0.1, "jockey_top3_rate": 0.3}

    positions = [r.finish_position for r in results if r.finish_position]
    n = len(positions)
    wins = sum(1 for p in positions if p == 1)
    top3 = sum(1 for p in positions if p <= 3)

    return {
        "jockey_win_rate": wins / n if n > 0 else 0.1,
        "jockey_top3_rate": top3 / n if n > 0 else 0.3,
    }


# 予測に使う特徴量カラム名（モデルの入力と一致させること）
FEATURE_COLUMNS = [
    "distance", "course_type", "venue_code",
    "gate_number", "weight_carried", "horse_weight", "horse_weight_diff",
    "odds", "popularity",
    "past_races_count", "win_rate", "top3_rate", "avg_finish_pos",
    "avg_last_3f", "days_since_last_race",
    "same_distance_win_rate", "same_course_win_rate",
    "avg_odds", "best_finish",
    "jockey_win_rate", "jockey_top3_rate",
]
