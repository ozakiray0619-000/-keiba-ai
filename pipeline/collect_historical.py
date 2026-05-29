"""
過去データ一括収集パイプライン
指定した日数分の過去レース結果をnetkeibaからスクレイピングしてDBに保存する

使い方:
    cd keiba_app
    # 直近30日分を収集（デフォルト）
    python -m pipeline.collect_historical

    # 日数を指定
    python -m pipeline.collect_historical --days 90

    # 日付範囲を指定
    python -m pipeline.collect_historical --from 2025-01-01 --to 2025-05-01

Note:
    - 1リクエストあたり 2〜3秒 の待機あり（サーバー負荷軽減）
    - 100日分で 1〜2時間 程度かかる目安
    - 途中でCtrl+Cで中断しても再実行時に取得済みレースはスキップ
"""
import sys
import argparse
import logging
import time
import random
from datetime import date, timedelta, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import init_db, Horse, Race, RaceEntry, RaceResult
from db.session import SessionLocal
from scraper import get_race_list, get_entry, get_result, get_horse_info

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def date_range(start: date, end: date):
    """start から end（含む）の日付を1日ずつ yield"""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def save_race_from_entry(session, race_id_str: str, entry_data: dict, target_date: date) -> Race:
    """出馬表データからRaceレコードを作成・更新"""
    race = session.query(Race).filter_by(netkeiba_race_id=race_id_str).first()
    if race is None:
        race = Race(netkeiba_race_id=race_id_str)
        session.add(race)

    ri = entry_data.get("race_info", {})
    race.name = ri.get("name") or f"レース({race_id_str[-4:]})"
    race.race_date = target_date
    race.venue = ri.get("venue", "")
    race.course_type = ri.get("course_type")
    race.distance = ri.get("distance")
    race.grade = ri.get("grade")

    # race_idの位置からvenue/race_numberを補完
    if len(race_id_str) == 12:
        from scraper.race_list import VENUE_CODES
        venue_code = race_id_str[8:10]
        race.race_number = int(race_id_str[10:12])
        if not race.venue:
            race.venue = VENUE_CODES.get(venue_code, f"会場{venue_code}")

    session.flush()
    return race


def save_or_get_horse(session, horse_id_str: str, horse_name: str) -> Horse:
    """馬をDBに保存（既存なら返すだけ）"""
    if not horse_id_str:
        return None
    horse = session.query(Horse).filter_by(netkeiba_id=horse_id_str).first()
    if horse is None:
        horse = Horse(netkeiba_id=horse_id_str, name=horse_name or "不明")
        session.add(horse)
        session.flush()
        # 馬プロファイル取得（初回のみ・失敗してもスキップ）
        try:
            info = get_horse_info(horse_id_str)
            if info:
                profile = info.get("profile", {})
                horse.name = profile.get("name") or horse_name or "不明"
                horse.trainer = profile.get("trainer")
                horse.owner = profile.get("owner")
                horse.sire = profile.get("sire")
                horse.dam = profile.get("dam")
                horse.dam_sire = profile.get("dam_sire")
        except Exception as e:
            logger.debug(f"馬プロファイル取得失敗 {horse_id_str}: {e}")
    return horse


def collect_one_race(session, race_id_str: str, target_date: date) -> bool:
    """1レースの出走表＋結果を収集してDBに保存"""
    # ── 出馬表取得 ──────────────────────────────────────────
    entry_data = get_entry(race_id_str)
    if not entry_data:
        logger.warning(f"出馬表取得失敗: {race_id_str}")
        return False

    race = save_race_from_entry(session, race_id_str, entry_data, target_date)

    for entry in entry_data.get("entries", []):
        horse_id_str = entry.get("horse_id")
        if not horse_id_str:
            continue

        horse = save_or_get_horse(session, horse_id_str, entry.get("horse_name", ""))
        if horse is None:
            continue

        existing = session.query(RaceEntry).filter_by(race_id=race.id, horse_id=horse.id).first()
        db_entry = existing or RaceEntry(race_id=race.id, horse_id=horse.id)
        if not existing:
            session.add(db_entry)

        db_entry.gate_number     = entry.get("gate_number")
        db_entry.horse_number    = entry.get("horse_number")
        db_entry.jockey          = entry.get("jockey")
        db_entry.weight_carried  = entry.get("weight_carried")
        db_entry.horse_weight    = entry.get("horse_weight")
        db_entry.horse_weight_diff = entry.get("horse_weight_diff")
        db_entry.odds            = entry.get("odds")
        db_entry.popularity      = entry.get("popularity")

    session.flush()

    # ── 結果取得 ────────────────────────────────────────────
    result_data = get_result(race_id_str)
    if not result_data or not result_data.get("results"):
        logger.warning(f"結果なし（レース未開催or取得失敗）: {race_id_str}")
        return False

    saved_count = 0
    for r in result_data.get("results", []):
        horse_id_str = r.get("horse_id")
        if not horse_id_str:
            continue

        horse = save_or_get_horse(session, horse_id_str, r.get("horse_name", ""))
        if horse is None:
            continue

        existing = session.query(RaceResult).filter_by(race_id=race.id, horse_id=horse.id).first()
        db_res = existing or RaceResult(race_id=race.id, horse_id=horse.id)
        if not existing:
            session.add(db_res)

        db_res.finish_position  = r.get("finish_position")
        db_res.gate_number      = r.get("gate_number")
        db_res.horse_number     = r.get("horse_number")
        db_res.jockey           = r.get("jockey")
        db_res.weight_carried   = r.get("weight_carried")
        db_res.horse_weight     = r.get("horse_weight")
        db_res.horse_weight_diff = r.get("horse_weight_diff")
        db_res.finish_time      = r.get("finish_time")
        db_res.margin           = r.get("margin")
        db_res.last_3f          = r.get("last_3f")
        db_res.odds             = r.get("odds")
        db_res.popularity       = r.get("popularity")
        saved_count += 1

    session.commit()
    logger.info(f"  保存: {race.name} ({saved_count}頭の結果)")
    return True


def is_race_already_collected(session, race_id_str: str) -> bool:
    """このレースの結果が既にDBにあるか確認"""
    race = session.query(Race).filter_by(netkeiba_race_id=race_id_str).first()
    if race is None:
        return False
    cnt = session.query(RaceResult).filter_by(race_id=race.id).count()
    return cnt >= 3


def collect_historical(start_date: date, end_date: date):
    """指定期間のレースデータを一括収集"""
    init_db()
    session = SessionLocal()

    total_days = (end_date - start_date).days + 1
    total_races = 0
    skipped = 0
    failed = 0

    logger.info(f"=== 過去データ収集開始: {start_date} ～ {end_date} ({total_days}日間) ===")
    logger.info("Ctrl+C で中断できます（次回再実行時に取得済みレースはスキップ）")

    try:
        for i, d in enumerate(date_range(start_date, end_date)):
            logger.info(f"\n[{i+1}/{total_days}] {d} の処理開始")

            race_list = get_race_list(d)
            if not race_list:
                logger.info(f"  {d}: レースなし（休開催または取得失敗）")
                continue

            logger.info(f"  {len(race_list)}レース発見")

            for race_data in race_list:
                race_id = race_data["race_id"]

                if is_race_already_collected(session, race_id):
                    logger.info(f"  スキップ（取得済み）: {race_data['name']} ({race_id})")
                    skipped += 1
                    continue

                logger.info(f"  収集中: {race_data['name']} ({race_id})")
                try:
                    ok = collect_one_race(session, race_id, d)
                    if ok:
                        total_races += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"  レース収集エラー {race_id}: {e}", exc_info=True)
                    session.rollback()
                    failed += 1

                # レート制限
                time.sleep(random.uniform(1.5, 2.5))

    except KeyboardInterrupt:
        logger.info("\n=== 中断されました ===")

    finally:
        session.close()

    logger.info(f"\n=== 収集完了 ===")
    logger.info(f"  新規収集: {total_races}レース")
    logger.info(f"  スキップ: {skipped}レース（取得済み）")
    logger.info(f"  失敗    : {failed}レース")


def main():
    parser = argparse.ArgumentParser(description="過去レースデータ一括収集")
    parser.add_argument("--days", type=int, default=30,
                        help="直近何日分を収集するか（デフォルト: 30日）")
    parser.add_argument("--from", dest="from_date", type=str, default=None,
                        help="収集開始日 YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", type=str, default=None,
                        help="収集終了日 YYYY-MM-DD（デフォルト: 昨日）")
    args = parser.parse_args()

    today = date.today()
    yesterday = today - timedelta(days=1)

    if args.from_date:
        start = date.fromisoformat(args.from_date)
        end = date.fromisoformat(args.to_date) if args.to_date else yesterday
    else:
        end = date.fromisoformat(args.to_date) if args.to_date else yesterday
        start = end - timedelta(days=args.days - 1)

    if start > yesterday:
        print("⚠️  開始日が未来です。過去データのみ収集できます。")
        return

    end = min(end, yesterday)  # 未来日は収集不可

    collect_historical(start, end)


if __name__ == "__main__":
    main()
