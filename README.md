# 券商月度資料看板

ELN／PGN／複委託／分戶帳，各券商庫存與交易量的趨勢、排名、市佔一覽。

伺服器每天自動從官方來源下載檔案、解析後存進 SQLite，網頁從 `/api/data` 讀取資料。不需要再手動整理 Google 試算表。

```
官方來源 ──(每天 08:30 下載)──▶ app/sources/*.py 解析 ──▶ data/market.db ──▶ /api/data ──▶ static/index.html
```

## 資料來源

| 商品 | 指標 | 來源 | 取值規則 | 原始單位 |
|---|---|---|---|---|
| ELN | 庫存 | 櫃買中心 `CBmcs006` 流通在外餘額月報表 | 股權連結型商品(ELN) | 千元 |
| ELN | 交易量 | 櫃買中心 `CBmss102` 交易月報表 | 非保本型契約本金 − 信用連結型契約本金 | 千元 |
| PGN | 庫存 | 櫃買中心 `CBmcs006` | 保本型商品(PGN) | 千元 |
| PGN | 交易量 | 櫃買中心 `CBmss102` | 保本型契約本金 | 千元 |
| 複委託 | 交易量 | 證券商公會 `{民國年}年外國買賣彙總統計表.xlsx` | 各券商月成交金額（不含期貨商 IB、基富通） | 元 |
| 分戶帳 | 庫存 | 證交所開放資料 `t187ap20.csv`（data.gov.tw 20764） | 科目 119095「專戶分戶帳留存客戶款項」借方餘額 | 元 |

- 櫃買中心：<https://www.tpex.org.tw/zh-tw/derivative/tpex-derivative/statistics/td/structure.html>，每月 1 日左右公布上月檔案，歷史月份都能下載。
- 證券商公會：<https://www.twsa.org.tw/E01/E011.html>，一年一個檔，每月更新。
- 證交所月計表：<https://data.gov.tw/dataset/20764>，**只有最新一個月**。每月 11 日起，系統把當天的檔案視為上月資料存檔。舊月份只存在這個系統的資料庫裡，2024/07–2026/08 的歷史則來自 `seed/split_account.csv`（由原 Google 試算表轉出）。

### 券商代號與合併

- 券商一律以 4 碼代號識別，名稱對照在 `app/catalog.py` 的 `NAMES`（同一個代號可能改名，例如 526 以前叫大慶、現在叫美好）。
- 元富（5920）與台新（8150）在 2026 年合併成 9B00（公會 115 年表的註 1、註 2）。從官方來源抓到的資料會把舊代號併入 9B00，成為一條連續的「台新」走勢，這也是原本複委託試算表的做法。如果想分開顯示，刪掉 `CODE_ALIASES` 裡對應的那一行即可。
- `seed/` 和 `import-csv` 匯入的資料保留原本的代號，所以分戶帳的元富、台新維持原試算表的分法。

## 本機執行

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
# 打開 http://localhost:8000
```

資料庫是空的時候，第一次啟動會在背景自動回補：匯入 seed，再下載 `START_MONTH` 之後的歷史資料，大約 1 分鐘。網頁會顯示「資料更新中」，完成後自動重新整理。

## 部署（Docker）

```bash
ADMIN_TOKEN=請換成一組長亂數 docker compose up -d --build
```

- 服務跑在 8000 port。正式上線時建議在前面加一層 Nginx／Caddy 處理 HTTPS；如果只給內部看，可以在那一層加上 Basic Auth 或 IP 白名單。
- 資料放在 Docker volume `market-data`（`/app/data`），包含 `market.db` 和 `raw/` 底下每一份下載過的原始檔。**分戶帳的歷史只存在這裡，請定期備份**：
  ```bash
  docker compose cp app:/app/data ./backup-$(date +%Y%m%d)
  ```
- 排程在 web process 裡面執行，所以 uvicorn 只能開 1 個 worker（Dockerfile 已經這樣設定）。

### 環境變數

| 變數 | 預設 | 說明 |
|---|---|---|
| `UPDATE_TIME` | `08:30` | 每天更新的時間（`TZ` 時區） |
| `TZ` | `Asia/Taipei` | |
| `START_MONTH` | `2025-01` | 第一次啟動時回補的起始月份 |
| `ADMIN_TOKEN` | 空 | 設定後才開放 `POST /api/refresh` |
| `MOPS_MIN_DAY` | `11` | 每月幾號以後，才把月計表當成上月資料 |
| `SCHEDULER_ENABLED` | `1` | 設成 `0` 會關掉內建排程（例如改用外部 cron 執行 `python -m app.cli update`） |
| `AUTO_BOOTSTRAP` | `1` | 空資料庫啟動時是否自動回補 |
| `DATA_DIR` | `./data` | 資料庫與原始檔的存放位置 |

## 日常操作

```bash
# 在容器裡執行，例如：docker compose exec app python -m app.cli status
python -m app.cli status                 # 各來源最後一次更新的結果、各商品的最新月份
python -m app.cli update                 # 立即執行一次每日更新
python -m app.cli backfill --from 2020-01  # 補更早的歷史（櫃買可回溯到 2007、公會到 2016）
python -m app.cli import-csv 檔案.csv     # 手動補資料（欄位：product,metric,month,broker_code,name,value，金額單位為元）
```

不進主機也能觸發更新：

```bash
curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" https://你的網址/api/refresh
```

`GET /api/status` 會顯示每個來源最後一次的執行狀態與訊息。來源網站改版或下載失敗時，狀態會是 `error`，而且已經存在的資料不會被覆蓋。

## 測試

```bash
pip install pytest httpx
python -m pytest
```

`tests/fixtures/` 是 2026-10-21 下載的原始檔，測試中的期望值已經和原本 Google 試算表的數字對過。
