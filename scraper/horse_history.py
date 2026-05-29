"""
馬の過去成績スクレイパー
netkeibaの馬個別ページから過去レース成績を全件取得
"""
import logging
import re
from typing import Dict, List
from .base import fetch, safe_text, safe_float, safe_int

logger = logging.getLogger(__name__)


def get_horse_info(horse_id: str) -> Dict:
    """
    馬の基本情報＋過去成績を取得
    """
    url = f"https://db.netkeiba.com/horse/{horse_id}/"
    logger.info(f"馬情報取得: {url}")

    soup = fetch(url)
    if soup is None:
        return {}

    data = {"horse_id": horse_id, "profile": {}, "history": []}

    # ─── プロフィール ─────────────────────────────────
    try:
        name_tag = soup.select_one(".horse_title h1") or soup.select_one("h1.name")
        data["profile"]["name"] = safe_text(name_tag)

        prof_table = soup.select_one("table.db_prof_table")
        if prof_table:
            for row in prof_table.select("tr"):
                th = safe_text(row.select_one("th"))
                td = safe_text(row.select_one("td"))
                if "生年月日" in th:
                    data["profile"]["birthday"] = td
                elif "調教師" in th:
                    data["profile"]["trainer"] = td
                elif "馬主" in th:
                    data["profile"]["owner"] = td
                elif "生産者" in th:
                    data["profile"]["breeder"] = td
                elif "父" in th and "母父" not in th:
                    data["profile"]["sire"] = td
                elif "母" == th:
                    data["profile"]["dam"] = td
                elif "母父" in th:
                    data["profile"]["dam_sire"] = td
    except Exception as e:
        logger.error(f"プロフィールパースエラー: {e}")

    # ─── 過去成績 ─────────────────────────────────────
    try:
        result_table = soup.select_one("table.db_h_race_results")
        if result_table:
            for row in result_table.select("tr.HorseList"):
                try:
                    cols = row.select("td")
                    if len(cols) < 10:
                        continue

                    h = {}
                    h["race_date"] = safe_text(cols[0])
                    h["venue"] = safe_text(cols[1])
                    h["weather"] = safe_text(cols[2])
                    h["race_number"] = safe_int(safe_text(cols[3]))
                    h["race_name"] = safe_text(cols[4])

                    # レースID
                    race_a = cols[4].select_one("a")
                    if race_a:
                        href = race_a.get("href", "")
                        if "race_id=" in href:
                            h["race_id"] = href.split("race_id=")[1].split("&")[0]
                        elif "/race/" in href:
                            h["race_id"] = href.rstrip("/").split("/")[-1]

                    h["num_horses"] = safe_int(safe_text(cols[5]))
                    h["gate_number"] = safe_int(safe_text(cols[6]))
                    h["horse_number"] = safe_int(safe_text(cols[7]))
                    h["odds"] = safe_float(safe_text(cols[8]))
                    h["popularity"] = safe_int(safe_text(cols[9]))
                    h["finish_position"] = safe_int(safe_text(cols[10])) if len(cols) > 10 else None

                    if len(cols) > 11:
                        h["jockey"] = safe_text(cols[11])
                    if len(cols) > 12:
                        h["weight_carried"] = safe_float(safe_text(cols[12]))
                    if len(cols) > 13:
                        # コース情報 "芝1600" 等
                        course_text = safe_text(cols[13])
                        m = re.search(r"(芝|ダート|障害)(\d+)", course_text)
                        if m:
                            h["course_type"] = m.group(1)
                            h["distance"] = int(m.group(2))
                    if len(cols) > 17:
                        h["finish_time_str"] = safe_text(cols[17])
                    if len(cols) > 18:
                        h["margin"] = safe_text(cols[18])
                    if len(cols) > 22:
                        wtext = safe_text(cols[22])
                        m2 = re.match(r"(\d+)\(([+-]?\d+)\)", wtext)
                        if m2:
                            h["horse_weight"] = int(m2.group(1))
                            h["horse_weight_diff"] = int(m2.group(2))
                    if len(cols) > 23:
                        h["last_3f"] = safe_float(safe_text(cols[23]))

                    data["history"].append(h)

                except Exception as e:
                    logger.error(f"成績行パースエラー: {e}")
                    continue
    except Exception as e:
        logger.error(f"成績テーブルエラー: {e}")

    logger.info(f"horse_id={horse_id}: {len(data['history'])}件の成績取得")
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # イクイノックスのhorse_id
    info = get_horse_info("2019105281")
    import json
    print(json.dumps(info, ensure_ascii=False, indent=2))
