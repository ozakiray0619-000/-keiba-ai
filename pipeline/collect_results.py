"""
レース結果収集パイプライン
レース終了後に実行して着順・タイムをDBに保存
モデルの再学習データとして蓄積する
"""
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import init_db, Race, Horse, RaceResult
from db.session import SessionLocal
from scraper import get_result

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def collect_results(target_date: date = None):
    """指定日のレース結果を収集"""
    if target_date is None:
        target_date = date.today()

    logger.info(f"=== 結果収集開始: {target_date} ===")
    init_db()
    session = SessionLocal()

    try:
        races = session.query(Race).filter(Race.race_date == target_date).all()
        logger.info(f"{len(races)}レースの結果を収集します")

        for race in races:
            logger.info(f"結果取得: {race.name} ({race.netkeiba_race_id})")
            result_data = get_result(race.netkeiba_race_id)

            if not result_data or not result_data.get("results"):
                logger.warning(f"結果なし: {race.netkeiba_race_id}")
                continue

            for r in result_data["results"]:
                horse_id_str = r.get("horse_id")
                if not horse_id_str:
                    continue

                horse = session.query(Horse).filter_by(netkeiba_id=horse_id_str).first()
                if horse is None:
                    logger.warning(f"馬が見つからない: {horse_id_str}")
                    continue

                # 既存チェック
                existing = (
                    session.query(RaceResult)
                    .filter_by(race_id=race.id, horse_id=horse.id)
                    .first()
                )
                if existing:
                    db_result = existing
                else:
                    db_result = RaceResult(race_id=race.id, horse_id=horse.id)
                    session.add(db_result)

                db_result.finish_position = r.get("finish_position")
                db_result.gate_number = r.get("gate_number")
                db_result.horse_number = r.get("horse_number")
                db_result.jockey = r.get("jockey")
                db_result.weight_carried = r.get("weight_carried")
                db_result.horse_weight = r.get("horse_weight")
                db_result.horse_weight_diff = r.get("horse_weight_diff")
                db_result.finish_time = r.get("finish_time")
                db_result.margin = r.get("margin")
                db_result.last_3f = r.get("last_3f")
                db_result.odds = r.get("odds")
                db_result.popularity = r.get("popularity")

            session.commit()
            logger.info(f"  → 保存: {len(result_data['results'])}頭")

    except Exception as e:
        session.rollback()
        logger.error(f"結果収集エラー: {e}", exc_info=True)
    finally:
        session.close()

    logger.info(f"=== 結果収集完了 ===")


if __name__ == "__main__":
    target = date.today()
    if len(sys.argv) > 1:
        target = datetime.strptime(sys.argv[1], "%Y%m%d").date()
    collect_results(target)
