"""
レース結果スクレイパー
確定後の着順・タイム・配当を取得
"""
import logging
import re
from typing import Dict, List
from .base import fetch, safe_text, safe_float, safe_int

logger = logging.getLogger(__name__)


def get_result(race_id: str) -> Dict:
    """
    レース結果を取得
    Returns: {"race_id": ..., "results": [{finish_position, horse_number, ...}]}
    """
    url = f"https://race.netkeiba.com/race/result.html?race_id={race_id}"
    logger.info(f"レース結果取得: {url}")

    soup = fetch(url)
    if soup is None:
        return {}

    data = {"race_id": race_id, "results": [], "payouts": {}}

    # ─── 着順テーブル ────────────────────────────────
    try:
        table = soup.select_one("table.RaceTable01") or soup.select_one("#race_result")
        if table:
            for row in table.select("tr.HorseList"):
                try:
                    r = {}
                    # 着順
                    pos_td = row.select_one(".Rank")
                    pos_text = safe_text(pos_td)
                    r["finish_position"] = safe_int(pos_text) if pos_text.isdigit() else None

                    # 枠・馬番
                    r["gate_number"] = safe_int(safe_text(row.select_one(".Waku")))
                    r["horse_number"] = safe_int(safe_text(row.select_one(".Umaban")))

                    # 馬名・馬ID
                    horse_a = row.select_one(".Horse_Name a") or row.select_one(".HorseName a")
                    if horse_a:
                        r["horse_name"] = safe_text(horse_a)
                        href = horse_a.get("href", "")
                        if "/horse/" in href:
                            r["horse_id"] = href.rstrip("/").split("/")[-1]

                    # タイム
                    time_td = row.select_one(".Time")
                    if time_td:
                        time_text = safe_text(time_td)
                        m = re.match(r"(\d+):(\d+\.\d+)", time_text)
                        if m:
                            r["finish_time"] = int(m.group(1)) * 60 + float(m.group(2))

                    # 着差
                    r["margin"] = safe_text(row.select_one(".Margin"))

                    # 騎手・斤量
                    r["jockey"] = safe_text(row.select_one(".Jockey a") or row.select_one(".Jockey"))
                    r["weight_carried"] = safe_float(safe_text(row.select_one(".Kinryo")))

                    # 馬体重
                    weight_td = row.select_one(".Weight")
                    if weight_td:
                        wtext = safe_text(weight_td)
                        m2 = re.match(r"(\d+)\(([+-]?\d+)\)", wtext)
                        if m2:
                            r["horse_weight"] = int(m2.group(1))
                            r["horse_weight_diff"] = int(m2.group(2))

                    # 上がり3F
                    r["last_3f"] = safe_float(safe_text(row.select_one(".Last3F")))

                    # オッズ・人気
                    r["odds"] = safe_float(safe_text(row.select_one(".Odds")))
                    r["popularity"] = safe_int(safe_text(row.select_one(".Popular")))

                    if r.get("horse_number") is not None:
                        data["results"].append(r)

                except Exception as e:
                    logger.error(f"結果行パースエラー: {e}")
                    continue
    except Exception as e:
        logger.error(f"結果テーブルエラー: {e}")

    # ─── 配当情報 ────────────────────────────────────
    try:
        pay_table = soup.select_one("table.Payout_Detail_Table")
        if pay_table:
            for row in pay_table.select("tr"):
                bet_type = safe_text(row.select_one("th"))
                numbers = [safe_text(td) for td in row.select("td.Number")]
                payouts = [safe_text(td) for td in row.select("td.Payout")]
                if bet_type and numbers:
                    data["payouts"][bet_type] = list(zip(numbers, payouts))
    except Exception as e:
        logger.error(f"配当パースエラー: {e}")

    logger.info(f"race_id={race_id}: {len(data['results'])}頭の結果取得")
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = get_result("202405050511")
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
