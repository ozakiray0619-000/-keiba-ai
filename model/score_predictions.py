"""
手動予測ログ(data/manual_predictions.json)を実際の着順と照合し、
各券種の的中可否と通算精度を計算する。

使い方:
  1. data/manual_predictions.json の actual_result.finish_order に着順を記入
     例: "finish_order": [17, 11, 1, 6, 14, ...]  (1着→最下位の馬番)
  2. python model/score_predictions.py
"""
import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "manual_predictions.json"


def eval_record(rec: dict) -> dict:
    order = rec.get("actual_result", {}).get("finish_order")
    if not order:
        return {k: None for k in ("trifecta_hit", "exacta_hit", "place_hit", "trio_hit")}
    top3 = order[:3]
    top3_set = set(top3)
    p = rec["predictions"]

    # 3連単: 1着2着3着の順序まで一致
    tri = any(combo == top3 for b in p.get("trifecta", []) for combo in b["combos"])

    # 馬単: 1着2着の順序一致
    exa = any(combo == order[:2] for b in p.get("exacta", []) for combo in b["combos"])

    # 複勝: 指定馬が3着以内
    place = any(h["number"] in top3_set for b in p.get("place", []) for h in b["horses"])

    # 3連複フォーメーション: top3が各列を満たす組合せに含まれるか
    trio = False
    for b in p.get("trio_formation", []):
        f, s, t = set(b["first"]), set(b["second"]), set(b["third"])
        # top3の3頭が {1着列, 2着列, 3着列} を1頭ずつ満たす割当が存在するか
        from itertools import permutations
        for perm in permutations(top3):
            if perm[0] in f and perm[1] in s and perm[2] in t:
                trio = True
                break
        if trio:
            break

    return {"trifecta_hit": tri, "exacta_hit": exa, "place_hit": place, "trio_hit": trio}


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    recs = data["records"]
    totals = {k: [0, 0] for k in ("trifecta", "exacta", "place", "trio")}  # [hit, scored]
    for rec in recs:
        ev = eval_record(rec)
        rec["evaluation"] = ev
        for key, ekey in (("trifecta", "trifecta_hit"), ("exacta", "exacta_hit"),
                          ("place", "place_hit"), ("trio", "trio_hit")):
            if ev[ekey] is not None:
                totals[key][1] += 1
                totals[key][0] += int(ev[ekey])

    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== 通算精度 ===")
    for key, (hit, scored) in totals.items():
        rate = f"{hit/scored*100:.1f}%" if scored else "未集計(着順待ち)"
        print(f"{key:9s}: {hit}/{scored}  {rate}")


if __name__ == "__main__":
    main()
