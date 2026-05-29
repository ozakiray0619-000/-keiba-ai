"""
当日レースデータ一括収集パイプライン
毎朝レース前に実行して出馬表・馬情報をDBに保存する
"""
import logging
import sys
from datetime import date
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import init_db, Horse, Race, RaceEntry
from db.session import SessionLocal
from scraper import get_race_list, get_entry, get_horse_info

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "collect.log"),
    ],
)
logger = logging.getLogger(__name__)


def save_horse(session, horse_data: dict) -> Horse:
    """馬データをDBに保存（既存なら更新）"""
    horse_id = horse_data.get("horse_id")
    if not horse_id:
        return None

    horse = session.query(Horse).filter_by(netkeiba_id=horse_id).first()
    if horse is None:
        horse = Horse(netkeiba_id=horse_id)
        session.add(horse)

    profile = horse_data.get("profile", {})
    horse.name = profile.get("name") or horse_data.get("horse_name", "")
    horse.trainer = profile.get("trainer")
    horse.owner = profile.get("owner")
    horse.sire = profile.get("sire")
    horse.dam = profile.get("dam")
    horse.dam_sire = profile.get("dam_sire")
    session.flush()
    return horse


def save_race(session, race_data: dict, race_info: dict, target_date: date) -> Race:
    """レースデータをDBに保存"""
    race_id = race_data.get("race_id")
    race = session.query(Race).filter_by(netkeiba_race_id=race_id).first()
    if race is None:
        race = Race(netkeiba_race_id=race_id)
        session.add(race)

    race.name = race_info.get("name") or race_data.get("name", "")
    race.race_date = target_date
    race.venue = race_info.get("venue") or race_data.get("venue", "")
    race.race_number = race_data.get("race_number")
    race.course_type = race_info.get("course_type")
    race.distance = race_info.get("distance")
    session.flush()
    return race


def collect_today(target_date: date = None):
    """当日の全レース・出走馬情報を収集してDBに保存"""
    if target_date is None:
        target_date = date.today()

    logger.info(f"=== 収集開始: {target_date} ===")

    # DB初期化
    init_db()
    session = SessionLocal()

    try:
        # 1. レース一覧取得
        race_list = get_race_list(target_date)
        if not race_list:
            logger.warning("本日のレースが見つかりません")
            return

        logger.info(f"{len(race_list)}レース発見")

        for race_data in race_list:
            race_id = race_data["race_id"]
            logger.info(f"処理中: {race_data['venue']} {race_data['race_number']}R ({race_id})")

            # 2. 出馬表取得
            entry_data = get_entry(race_id)
            if not entry_data:
                logger.warning(f"出馬表取得失敗: {race_id}")
                continue

            # 3. レース保存
            race = save_race(session, race_data, entry_data.get("race_info", {}), target_date)

            # 4. 各馬の情報取得・保存
            for entry in entry_data.get("entries", []):
                horse_id = entry.get("horse_id")
                if not horse_id:
                    continue

                # 馬の過去成績取得（初回のみ、既存なら省略）
                existing = session.query(Horse).filter_by(netkeiba_id=horse_id).first()
                if existing is None:
                    horse_data = get_horse_info(horse_id)
                    horse_data["horse_id"] = horse_id
                    horse_data.setdefault("profile", {})["name"] = entry.get("horse_name", "")
                    horse = save_horse(session, horse_data)
                else:
                    horse = existing

                if horse is None:
                    continue

                # 5. 出走エントリ保存
                existing_entry = (
                    session.query(RaceEntry)
                    .filter_by(race_id=race.id, horse_id=horse.id)
                    .first()
                )
                if existing_entry is None:
                    db_entry = RaceEntry(race_id=race.id, horse_id=horse.id)
                    session.add(db_entry)
                else:
                    db_entry = existing_entry

                db_entry.gate_number = entry.get("gate_number")
                db_entry.horse_number = entry.get("horse_number")
                db_entry.jockey = entry.get("jockey")
                db_entry.weight_carried = entry.get("weight_carried")
                db_entry.horse_weight = entry.get("horse_weight")
                db_entry.horse_weight_diff = entry.get("horse_weight_diff")
                db_entry.odds = entry.get("odds")
                db_entry.popularity = entry.get("popularity")

            session.commit()
            logger.info(f"  → 保存完了: {race.name}")

    except Exception as e:
        session.rollback()
        logger.error(f"収集エラー: {e}", exc_info=True)
    finally:
        session.close()

    logger.info(f"=== 収集完了: {target_date} ===")


if __name__ == "__main__":
    from datetime import datetime
    target = date.today()
    if len(sys.argv) > 1:
        target = datetime.strptime(sys.argv[1], "%Y%m%d").date()
    collect_today(target)
