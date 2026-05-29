"""
出馬表スクレイパー
レースIDから出走馬・騎手・オッズ・馬体重を取得
"""
import logging
import re
from typing import List, Dict, Optional
from .base import fetch, safe_text, safe_float, safe_int

logger = logging.getLogger(__name__)


def get_entry(race_id: str) -> Dict:
    """
    出馬表を取得
    Returns: {
        "race_info": {...},
        "entries": [{"horse_number": N, "horse_id": "...", ...}, ...]
    }
    """
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    logger.info(f"出馬表取得: {url}")

    soup = fetch(url)
    if soup is None:
        return {}

    result = {"race_id": race_id, "race_info": {}, "entries": []}

    # ─── レース情報 ───────────────────────────────────
    try:
        race_name_tag = soup.select_one(".RaceName")
        result["race_info"]["name"] = safe_text(race_name_tag)

        data_tag = soup.select_one(".RaceData01")
        if data_tag:
            data_text = safe_text(data_tag)
            # 距離・コース種別を抽出 例: "芝1600m"
            m = re.search(r"(芝|ダート|障害)(\d+)m", data_text)
            if m:
                result["race_info"]["course_type"] = m.group(1)
                result["race_info"]["distance"] = int(m.group(2))

        data2_tag = soup.select_one(".RaceData02")
        if data2_tag:
            spans = data2_tag.select("span")
            texts = [safe_text(s) for s in spans]
            result["race_info"]["venue"] = texts[1] if len(texts) > 1 else ""
            result["race_info"]["grade"] = texts[0] if texts else ""
    except Exception as e:
        logger.error(f"レース情報パースエラー: {e}")

    # ─── 出走馬リスト ────────────────────────────────
    try:
        table = soup.select_one("table.Shutuba_Table")
        if table is None:
            table = soup.select_one("#shutuba_table")

        if table:
            for row in table.select("tr.HorseList"):
                try:
                    entry = {}

                    # 枠番・馬番
                    waku = row.select_one(".Waku")
                    entry["gate_number"] = safe_int(safe_text(waku)) if waku else None

                    umaban = row.select_one(".Umaban")
                    entry["horse_number"] = safe_int(safe_text(umaban)) if umaban else None

                    # 馬情報
                    horse_td = row.select_one(".HorseName")
                    if horse_td:
                        horse_a = horse_td.select_one("a")
                        entry["horse_name"] = safe_text(horse_a)
                        href = horse_a.get("href", "") if horse_a else ""
                        if "/horse/" in href:
                            entry["horse_id"] = href.rstrip("/").split("/")[-1]

                    # 性齢
                    sex_age = row.select_one(".KisoInfo")
                    if sex_age:
                        text = safe_text(sex_age)
                        entry["sex"] = text[0] if text else ""
                        entry["age"] = safe_int(text[1:]) if len(text) > 1 else None

                    # 斤量
                    kinryo = row.select_one(".Kinryo")
                    entry["weight_carried"] = safe_float(safe_text(kinryo)) if kinryo else None

                    # 騎手
                    jockey_td = row.select_one(".Jockey")
                    if jockey_td:
                        jockey_a = jockey_td.select_one("a")
                        entry["jockey"] = safe_text(jockey_a) if jockey_a else safe_text(jockey_td)

                    # 馬体重
                    weight_td = row.select_one(".Weight")
                    if weight_td:
                        wtext = safe_text(weight_td)
                        m = re.match(r"(\d+)\(([+-]?\d+)\)", wtext)
                        if m:
                            entry["horse_weight"] = int(m.group(1))
                            entry["horse_weight_diff"] = int(m.group(2))

                    # オッズ（単勝）
                    odds_td = row.select_one(".Odds")
                    entry["odds"] = safe_float(safe_text(odds_td)) if odds_td else None

                    # 人気
                    pop_td = row.select_one(".Popular")
                    entry["popularity"] = safe_int(safe_text(pop_td)) if pop_td else None

                    if entry.get("horse_number"):
                        result["entries"].append(entry)

                except Exception as e:
                    logger.error(f"行パースエラー: {e}")
                    continue

    except Exception as e:
        logger.error(f"出馬表テーブルパースエラー: {e}")

    logger.info(f"race_id={race_id}: {len(result['entries'])}頭取得")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # テスト用（実際のrace_idに変更してください）
    result = get_entry("202405050511")
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
