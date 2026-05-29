"""
LightGBMモデルの学習スクリプト
DBに蓄積された過去成績でモデルを学習・保存する
"""
import sys
import logging
import pickle
from pathlib import Path
from datetime import date

import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import log_loss, roc_auc_score

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.models import init_db, Race, RaceResult, RaceEntry
from db.session import SessionLocal
from model.features import build_features, FEATURE_COLUMNS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "saved_models"
MODEL_DIR.mkdir(exist_ok=True)


def load_training_data(session) -> pd.DataFrame:
    """過去の全レース結果から学習データを構築"""
    logger.info("学習データ構築中...")

    races = session.query(Race).filter(Race.race_date < date.today()).all()
    all_dfs = []

    for race in races:
        # 結果が存在するレースのみ使用
        results = session.query(RaceResult).filter_by(race_id=race.id).all()
        if len(results) < 3:
            continue

        try:
            df = build_features(session, race.id)
            if df.empty:
                continue

            # 目的変数：1位なら1、それ以外は0（単勝予測）
            result_map = {r.horse_id: r.finish_position for r in results}
            df["finish_position"] = df["horse_id"].map(result_map)
            df["label_win"] = (df["finish_position"] == 1).astype(int)
            df["label_top3"] = (df["finish_position"] <= 3).astype(int)
            df = df.dropna(subset=["finish_position"])

            all_dfs.append(df)

        except Exception as e:
            logger.error(f"レース{race.id}の特徴量構築失敗: {e}")
            continue

    if not all_dfs:
        logger.warning("学習データが空です。先にデータを収集してください。")
        return pd.DataFrame()

    full_df = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"学習データ: {len(full_df)}行 / {full_df['race_id'].nunique()}レース")
    return full_df


def train_model(df: pd.DataFrame, target: str = "label_win"):
    """LightGBMモデルを学習"""
    X = df[FEATURE_COLUMNS]
    y = df[target]

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

    # 時系列クロスバリデーション
    tscv = TimeSeriesSplit(n_splits=5)
    oof_preds = np.zeros(len(y))
    models = []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        dtrain = lgb.Dataset(X_train, label=y_train)
        dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)

        model = lgb.train(
            params,
            dtrain,
            num_boost_round=500,
            valid_sets=[dval],
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)],
        )

        oof_preds[val_idx] = model.predict(X_val)
        models.append(model)
        logger.info(f"Fold {fold+1} AUC: {roc_auc_score(y_val, oof_preds[val_idx]):.4f}")

    # OOF全体評価
    valid_mask = oof_preds > 0
    if valid_mask.sum() > 0:
        auc = roc_auc_score(y[valid_mask], oof_preds[valid_mask])
        logger.info(f"OOF AUC: {auc:.4f}")

    return models


def save_models(models, target: str = "win"):
    """モデルを保存"""
    model_path = MODEL_DIR / f"lgbm_{target}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(models, f)
    logger.info(f"モデル保存: {model_path}")
    return model_path


def main():
    init_db()
    session = SessionLocal()

    try:
        df = load_training_data(session)
        if df.empty:
            return

        # 単勝モデル
        logger.info("=== 単勝モデル学習 ===")
        win_models = train_model(df, target="label_win")
        save_models(win_models, target="win")

        # 複勝モデル
        logger.info("=== 複勝モデル学習 ===")
        top3_models = train_model(df, target="label_top3")
        save_models(top3_models, target="top3")

    finally:
        session.close()

    logger.info("✅ 学習完了")


if __name__ == "__main__":
    main()
