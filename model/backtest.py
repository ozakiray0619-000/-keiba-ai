"""
バックテストスクリプト
過去データで予測精度・回収率をシミュレーションして検証する

使い方:
    cd keiba_app
    python -m model.backtest

    # テスト期間を指定する場合
    python -m model.backtest --test-start 2024-01-01 --test-end 2024-12-31

    # 訓練済みモデルを使う場合（再学習しない）
    python -m model.backtest --use-saved-model
"""
import sys
import argparse
import logging
import pickle
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from datetime import date, datetime
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.models import init_db, Race, RaceResult, RaceEntry
from db.session import SessionLocal
from model.features import build_features, FEATURE_COLUMNS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "saved_models"


# ─────────────────────────────────────────────
# データ準備
# ─────────────────────────────────────────────

def load_all_races_with_results(session) -> list:
    """結果が揃っているレースをすべて取得（日付昇順）"""
    races = (
        session.query(Race)
        .filter(Race.race_date < date.today())
        .order_by(Race.race_date)
        .all()
    )
    valid = []
    for r in races:
        cnt = session.query(RaceResult).filter_by(race_id=r.id).count()
        if cnt >= 3:
            valid.append(r)
    return valid


def build_dataset(session, races: list) -> pd.DataFrame:
    """レースリストから特徴量+ラベルのDataFrameを構築"""
    dfs = []
    for race in races:
        try:
            df = build_features(session, race.id)
            if df.empty:
                continue
            results = session.query(RaceResult).filter_by(race_id=race.id).all()
            result_map = {r.horse_id: r.finish_position for r in results}
            df["finish_position"] = df["horse_id"].map(result_map)
            df["label_win"] = (df["finish_position"] == 1).astype(int)
            df["label_top3"] = (df["finish_position"] <= 3).astype(int)
            df["race_date"] = race.race_date
            df = df.dropna(subset=["finish_position"])
            dfs.append(df)
        except Exception as e:
            logger.debug(f"race_id={race.id} スキップ: {e}")
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


# ─────────────────────────────────────────────
# モデル学習・予測
# ─────────────────────────────────────────────

def train_lgbm(train_df: pd.DataFrame, target: str):
    """LightGBMをシンプルに学習して返す"""
    X = train_df[FEATURE_COLUMNS]
    y = train_df[target]
    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_child_samples": 20,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbose": -1,
        "n_jobs": -1,
    }
    dataset = lgb.Dataset(X, label=y)
    model = lgb.train(params, dataset, num_boost_round=300)
    return model


def load_saved_model(target: str):
    path = MODEL_DIR / f"lgbm_{target}.pkl"
    if not path.exists():
        raise FileNotFoundError(f"保存済みモデルなし: {path}")
    with open(path, "rb") as f:
        models = pickle.load(f)
    # 複数モデルのアンサンブルの場合は平均を取れるよう list で返す
    return models if isinstance(models, list) else [models]


def predict_proba(models, X: pd.DataFrame) -> np.ndarray:
    if isinstance(models, list):
        return np.mean([m.predict(X) for m in models], axis=0)
    return models.predict(X)


# ─────────────────────────────────────────────
# 評価指標
# ─────────────────────────────────────────────

def evaluate(test_df: pd.DataFrame, win_probs: np.ndarray, place_probs: np.ndarray) -> dict:
    df = test_df.copy()
    df["win_prob"] = win_probs
    df["place_prob"] = place_probs

    metrics = {}

    # ── AUC ──
    try:
        metrics["win_auc"] = roc_auc_score(df["label_win"], df["win_prob"])
    except Exception:
        metrics["win_auc"] = float("nan")
    try:
        metrics["place_auc"] = roc_auc_score(df["label_top3"], df["place_prob"])
    except Exception:
        metrics["place_auc"] = float("nan")

    # ── レース単位で評価 ──
    race_results = []
    for race_id, grp in df.groupby("race_id"):
        grp = grp.copy()
        grp["pred_rank"] = grp["win_prob"].rank(ascending=False).astype(int)
        grp["pred_rank_place"] = grp["place_prob"].rank(ascending=False).astype(int)

        winner_row = grp[grp["finish_position"] == 1]
        if winner_row.empty:
            continue

        predicted_1st = grp.loc[grp["pred_rank"] == 1]
        if predicted_1st.empty:
            continue

        actual_pos_of_pred1 = predicted_1st.iloc[0]["finish_position"]
        actual_winner_pred_rank = winner_row.iloc[0]["pred_rank"]

        # 単勝オッズ（1着の）
        winner_odds = winner_row.iloc[0].get("odds", np.nan)
        pred1_odds = predicted_1st.iloc[0].get("odds", np.nan)

        race_results.append({
            "race_id": race_id,
            "hit_win": int(actual_pos_of_pred1 == 1),      # 予測1位が実際に1着か
            "hit_place": int(actual_pos_of_pred1 <= 3),    # 予測1位が3着以内か
            "winner_pred_rank": int(actual_winner_pred_rank),
            "winner_odds": winner_odds,
            "pred1_odds": pred1_odds,
        })

    race_df = pd.DataFrame(race_results)
    if race_df.empty:
        return metrics

    n_races = len(race_df)
    metrics["total_races"] = n_races

    # 的中率
    metrics["win_accuracy"] = race_df["hit_win"].mean()      # 単勝的中率
    metrics["place_accuracy"] = race_df["hit_place"].mean()  # 複勝的中率

    # 実際の1着馬の予測順位（低いほど良い）
    metrics["winner_avg_pred_rank"] = race_df["winner_pred_rank"].mean()
    metrics["winner_median_pred_rank"] = race_df["winner_pred_rank"].median()

    # ── 回収率シミュレーション（全レース100円均等買い） ──
    # 単勝：予測1位に100円
    if not race_df["pred1_odds"].isna().all():
        bet_df = race_df.dropna(subset=["pred1_odds"])
        n_bet = len(bet_df)
        total_invest = n_bet * 100
        total_return = (bet_df["hit_win"] * bet_df["pred1_odds"] * 100).sum()
        metrics["tansho_roi"] = total_return / total_invest if total_invest > 0 else float("nan")
        metrics["tansho_hit_rate"] = bet_df["hit_win"].mean()
        metrics["tansho_n"] = n_bet

    return metrics


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

def print_report(metrics: dict, train_races: int, test_races: int,
                 train_start, train_end, test_start, test_end):
    sep = "=" * 55
    print(f"\n{sep}")
    print("  競馬予測モデル バックテストレポート")
    print(sep)
    print(f"  訓練期間: {train_start} ～ {train_end}  ({train_races}レース)")
    print(f"  検証期間: {test_start} ～ {test_end}  ({test_races}レース)")
    print(sep)

    print("\n【予測精度 (AUC)】")
    print(f"  単勝AUC    : {metrics.get('win_auc', float('nan')):.4f}  (0.5=ランダム, 1.0=完璧)")
    print(f"  複勝AUC    : {metrics.get('place_auc', float('nan')):.4f}")

    print("\n【的中率】")
    print(f"  単勝的中率 : {metrics.get('win_accuracy', 0):.1%}  (ランダム想定 ≈ 1/出走頭数)")
    print(f"  複勝的中率 : {metrics.get('place_accuracy', 0):.1%}  (ランダム想定 ≈ 3/出走頭数)")

    print("\n【実際の1着馬の予測順位】")
    print(f"  平均順位   : {metrics.get('winner_avg_pred_rank', float('nan')):.2f}位")
    print(f"  中央値     : {metrics.get('winner_median_pred_rank', float('nan')):.1f}位")

    print("\n【単勝回収率シミュレーション (予測1位に全レース100円均等)】")
    n = metrics.get("tansho_n", 0)
    hit = metrics.get("tansho_hit_rate", float("nan"))
    roi = metrics.get("tansho_roi", float("nan"))
    print(f"  対象レース : {n}レース")
    print(f"  的中率     : {hit:.1%}")
    print(f"  回収率     : {roi:.1%}  (100%=元返し)")
    if not np.isnan(roi):
        if roi >= 1.0:
            print("  → プラス収支 ✓")
        elif roi >= 0.7:
            print("  → 標準的な回収率 (JRA単勝控除率 約20%)")
        else:
            print("  → 要改善")

    print(f"\n{sep}\n")


def main():
    parser = argparse.ArgumentParser(description="競馬予測バックテスト")
    parser.add_argument("--test-start", type=str, default=None,
                        help="検証開始日 YYYY-MM-DD (省略時=全データの後半20%%)")
    parser.add_argument("--test-end", type=str, default=None,
                        help="検証終了日 YYYY-MM-DD (省略時=最終レース)")
    parser.add_argument("--use-saved-model", action="store_true",
                        help="再学習せず保存済みモデルを使う")
    args = parser.parse_args()

    init_db()
    session = SessionLocal()

    try:
        logger.info("レースデータ読み込み中...")
        all_races = load_all_races_with_results(session)
        if not all_races:
            print("\n⚠️  DBにレース結果データがありません。")
            print("先に scraper でデータを収集してください。\n")
            return

        logger.info(f"有効レース数: {len(all_races)}")

        # 訓練/検証の分割
        if args.test_start:
            test_start_date = date.fromisoformat(args.test_start)
            train_races = [r for r in all_races if r.race_date < test_start_date]
            test_races  = [r for r in all_races if r.race_date >= test_start_date]
            if args.test_end:
                test_end_date = date.fromisoformat(args.test_end)
                test_races = [r for r in test_races if r.race_date <= test_end_date]
        else:
            # デフォルト: 先頭80%で訓練、後半20%で検証
            split = int(len(all_races) * 0.8)
            train_races = all_races[:split]
            test_races  = all_races[split:]

        if not test_races:
            print("\n⚠️  検証期間にレースがありません。期間を確認してください。\n")
            return

        train_start = train_races[0].race_date if train_races else "N/A"
        train_end   = train_races[-1].race_date if train_races else "N/A"
        test_start  = test_races[0].race_date
        test_end    = test_races[-1].race_date

        logger.info(f"訓練: {len(train_races)}レース, 検証: {len(test_races)}レース")

        # テストデータ構築
        logger.info("検証データ特徴量構築中...")
        test_df = build_dataset(session, test_races)
        if test_df.empty:
            print("\n⚠️  検証データの特徴量が構築できませんでした。\n")
            return

        # モデル用意
        if args.use_saved_model:
            logger.info("保存済みモデルを読み込みます")
            try:
                win_models   = load_saved_model("win")
                place_models = load_saved_model("top3")
            except FileNotFoundError as e:
                print(f"\n⚠️  {e}\n先に train.py を実行してください。\n")
                return
        else:
            if not train_races:
                print("\n⚠️  訓練データがありません。--use-saved-model を試してください。\n")
                return
            logger.info("訓練データ特徴量構築中...")
            train_df = build_dataset(session, train_races)
            if train_df.empty:
                print("\n⚠️  訓練データの特徴量が構築できませんでした。\n")
                return
            logger.info("単勝モデル学習中...")
            win_models   = [train_lgbm(train_df, "label_win")]
            logger.info("複勝モデル学習中...")
            place_models = [train_lgbm(train_df, "label_top3")]

        # 予測
        logger.info("予測実行中...")
        X_test = test_df[FEATURE_COLUMNS]
        win_probs   = predict_proba(win_models,   X_test)
        place_probs = predict_proba(place_models, X_test)

        # 評価
        metrics = evaluate(test_df, win_probs, place_probs)

        # レポート出力
        print_report(
            metrics,
            train_races=len(train_races),
            test_races=len(test_races),
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
        )

        # 特徴量重要度（再学習した場合）
        if not args.use_saved_model:
            print("【特徴量重要度 TOP10 (単勝モデル)】")
            importance = win_models[0].feature_importance(importance_type="gain")
            feat_imp = sorted(
                zip(FEATURE_COLUMNS, importance), key=lambda x: x[1], reverse=True
            )
            for name, imp in feat_imp[:10]:
                bar = "█" * int(imp / max(i for _, i in feat_imp) * 20)
                print(f"  {name:<30} {bar} {imp:.1f}")
            print()

    finally:
        session.close()


if __name__ == "__main__":
    main()
