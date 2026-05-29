# 🏇 競馬AI予測アプリ

LightGBMで馬の勝率・複勝率を予測するWebアプリ。  
netkeiba.comから出馬表・過去成績を自動収集し、Reactで結果を表示。

---

## フォルダ構成

```
keiba_app/
├── scraper/          # netkeibaスクレイパー
│   ├── race_list.py  # 当日レース一覧
│   ├── entry.py      # 出馬表
│   ├── result.py     # レース結果
│   └── horse_history.py # 馬の過去成績
├── db/               # SQLiteデータベース
│   ├── models.py     # テーブル定義
│   └── session.py    # セッション管理
├── pipeline/         # 自動収集パイプライン
│   ├── collect_today.py   # 出馬表収集（毎朝実行）
│   ├── collect_results.py # 結果収集（毎夕実行）
│   └── scheduler.py       # 自動スケジューラ
├── model/            # 機械学習モデル
│   ├── features.py   # 特徴量エンジニアリング
│   ├── train.py      # LightGBM学習
│   └── predict.py    # 予測実行
├── api/              # FastAPI バックエンド
│   └── main.py
├── frontend/         # React フロントエンド
│   └── src/
│       ├── pages/    # レース一覧・詳細ページ
│       └── components/
└── requirements.txt
```

---

## セットアップ（初回）

### 1. Python環境構築

```bash
cd keiba_app
python -m venv venv

# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. DBを初期化

```bash
python db/models.py
```

### 3. フロントエンド依存パッケージインストール

```bash
cd frontend
npm install
```

---

## 毎日の使い方

### STEP 1: 当日出馬表を収集（レース前・朝に実行）

```bash
python pipeline/collect_today.py
# または日付指定
python pipeline/collect_today.py 20250601
```

### STEP 2: APIサーバーを起動

```bash
python api/main.py
# → http://localhost:8000 で起動
```

### STEP 3: フロントエンドを起動

```bash
cd frontend
npm run dev
# → http://localhost:5173 をブラウザで開く
```

### STEP 4: ブラウザでレースを選んで「AI予測実行」ボタンを押す

※ 初回は学習データが必要（下記参照）

---

## モデル学習（データが十分溜まってから）

```bash
# レース結果を収集（過去分も含め何日分か実行）
python pipeline/collect_results.py 20250520
python pipeline/collect_results.py 20250525

# モデルを学習
python model/train.py
```

学習完了後、ブラウザの「AI予測実行」ボタンで予測が動くようになります。

---

## 自動実行（毎日自動収集したい場合）

```bash
python pipeline/scheduler.py
```

毎朝8:00に出馬表、毎夕18:00に結果を自動収集します。

---

## Cursorでの開発Tips

- `Cmd+I`（Composer）でファイルをまたいだ修正ができる
- スクレイパーが壊れたら「このHTMLをパースするコードに直して」+HTML貼り付けでOK
- `.cursorrules`ファイルにプロジェクト規約を書くと精度UP

---

## データソース

| サイト | 用途 |
|------|------|
| netkeiba.com | 出馬表・過去成績・オッズ（メイン） |
| JRA公式 | 払い戻し確認 |
| db.netkeiba.com | 馬個別成績 |
