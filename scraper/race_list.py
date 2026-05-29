"""
当日・指定日のレース一覧をnetkeibaから取得
"""
import logging
from datetime import date, datetime
from typing import List, Dict
from .base import fetch, safe_text

logger = logging.getLogger(__name__)

# 開催場コード (netkeiba)
VENUE_CODES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
    "09": "阪神", "10": "小倉",
}


def get_race_list(target_date: date = None) -> List[Dict]:
    """
    指定日のJRAレース一覧を取得
    netkeibaの開催カレンダーページからkaisai_idを取得し、
    各会場のレースIDを構築する
    """
    if target_date is None:
        target_date = date.today()

    date_str = target_date.strftime("%Y%m%d")
    races = []

    # 開催情報ページからその日の開催場を取得
    url = f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={date_str}"
    logger.info(f"開催情報取得: {url}")
    soup = fetch(url, wait=2.0)

    if soup:
        import re
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = re.search(r"race_id=(\d{12})", href)
            if not m:
                m = re.search(r"/(\d{12})/?$", href)
            if m:
                race_id = m.group(1)
                if race_id not in seen:
                    seen.add(race_id)
                    venue_code = race_id[8:10]
                    race_num = int(race_id[10:12])
                    venue = VENUE_CODES.get(venue_code, f"会場{venue_code}")
                    races.append({
                        "race_id": race_id,
                        "name": f"{venue}{race_num}R",
                        "venue": venue,
                        "race_number": race_num,
                        "race_date": target_date,
                    })

    # 上記で取れない場合、主要会場×12Rを総当たりで存在確認
    if not races:
        logger.info("総当たりでレースID探索中...")
        for venue_code in ["05", "06", "08", "09"]:  # 東京・中山・京都・阪神
            for race_num in range(1, 13):
                race_id = f"{date_str}{venue_code}{race_num:02d}"
                url2 = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
                s = fetch(url2, wait=1.0)
                if s and s.select_one(".RaceName"):
                    venue = VENUE_CODES.get(venue_code, "")
                    race_name = safe_text(s.select_one(".RaceName")) or f"{venue}{race_num}R"
                    races.append({
                        "race_id": race_id,
                        "name": race_name,
                        "venue": venue,
                        "race_number": race_num,
                        "race_date": target_date,
                    })
                    logger.info(f"  発見: {race_id} {race_name}")

    logger.info(f"{target_date}: {len(races)}レース取得")
    return races


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    races = get_race_list(date.today())
    for r in races:
        print(r)
