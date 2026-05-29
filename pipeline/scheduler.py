"""
自動実行スケジューラ
毎朝8:00 → 出馬表収集
毎夕18:00 → レース結果収集
"""
import schedule
import time
import logging
from datetime import date

from collect_today import collect_today
from collect_results import collect_results

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def morning_job():
    logger.info("🌅 朝の収集ジョブ開始")
    collect_today(date.today())


def evening_job():
    logger.info("🌆 夕方の結果収集ジョブ開始")
    collect_results(date.today())


# スケジュール設定
schedule.every().day.at("08:00").do(morning_job)
schedule.every().day.at("18:00").do(evening_job)

if __name__ == "__main__":
    logger.info("スケジューラ起動 (Ctrl+C で停止)")
    logger.info("  毎朝 08:00 → 出馬表収集")
    logger.info("  毎夕 18:00 → レース結果収集")
    while True:
        schedule.run_pending()
        time.sleep(60)
