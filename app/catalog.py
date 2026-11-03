"""Products shown on the dashboard and how source broker identifiers map to one broker."""
import re

# Order here is the order of the product buttons on the page.
PRODUCTS = [
    {
        "id": "eln",
        "label": "ELN",
        "metrics": ["inventory", "volume"],
        "source": {"name": "櫃買中心・結構型商品統計資料",
                   "url": "https://www.tpex.org.tw/zh-tw/derivative/tpex-derivative/statistics/td/structure.html"},
        "note": "庫存＝流通在外餘額「股權連結型商品」；交易量＝契約本金「非保本型」扣除「信用連結型」。",
    },
    {
        "id": "pgn",
        "label": "PGN",
        "metrics": ["inventory", "volume"],
        "source": {"name": "櫃買中心・結構型商品統計資料",
                   "url": "https://www.tpex.org.tw/zh-tw/derivative/tpex-derivative/statistics/td/structure.html"},
        "note": "庫存＝流通在外餘額「保本型商品」；交易量＝契約本金「保本型商品」。",
    },
    {
        "id": "sub_brokerage",
        "label": "複委託",
        "metrics": ["volume"],
        "source": {"name": "證券商公會・外國有價證券統計資料",
                   "url": "https://www.twsa.org.tw/E01/E011.html"},
        "note": "證券商受託買賣外國有價證券月成交金額。",
    },
    {
        "id": "split_account",
        "label": "分戶帳",
        "metrics": ["inventory"],
        "source": {"name": "政府資料開放平台・各券商每月月計表",
                   "url": "https://data.gov.tw/dataset/20764"},
        "note": "會計科目 119095「專戶分戶帳留存客戶款項」借方餘額。開放資料只有最新一個月，舊月份為系統逐月保存。",
    },
    {
        "id": "rp",
        "label": "RP",
        "metrics": ["inventory"],
        "source": {"name": "政府資料開放平台・各券商每月月計表",
                   "url": "https://data.gov.tw/dataset/20764"},
        "note": "會計科目 214010「附買回債券負債」借方餘額。開放資料只有最新一個月，自 2026/09 起由系統逐月保存。",
    },
]
PRODUCT_IDS = [p["id"] for p in PRODUCTS]
METRIC_LABELS = {"inventory": "庫存", "volume": "交易量"}

# Old broker codes folded into their successor, so a merged firm keeps one continuous
# (pro-forma) series. 元富 switched to 9B00 on 2026-02-02 and 台新 merged into it on
# 2026-04-06 (證券商公會 115年複委託 表註1、註2). Delete a line to show the firms separately.
CODE_ALIASES = {
    "5920": "9B00",  # 元富
    "8150": "9B00",  # 台新
}

# TPEx's outstanding-balance report uses 3-char codes plus "T" ("526T" for 5260). Leverage
# dealers don't follow that rule, so their codes are listed explicitly.
TPEX_INVENTORY_CODES = {
    "221T": "F020",  # 群益期貨
}

# Display names keyed by canonical code. Codes not listed fall back to the source's name.
NAMES = {
    "0200": "遠智", "0250": "基富通", "0290": "巴克萊", "1020": "合庫", "1040": "臺銀",
    "1160": "日盛", "1260": "宏遠", "1360": "麥格理", "1440": "美林", "1470": "摩根士丹利",
    "1650": "新加坡瑞銀", "2180": "亞東", "5050": "大展", "5260": "美好", "5380": "第一金", "5850": "統一",
    "5920": "元富", "6010": "犇亞", "6110": "台中銀", "6160": "中國信託", "6210": "新百王",
    "6380": "光和", "6460": "大昌", "6480": "福邦", "6620": "口袋", "6910": "德信", "7000": "兆豐",
    "7030": "致和", "7790": "國票", "8150": "台新", "8450": "康和", "8560": "新光",
    "8840": "玉山", "8880": "國泰", "8960": "匯豐", "9100": "群益金鼎", "9200": "凱基",
    "9300": "華南永昌", "9600": "富邦", "9800": "元大", "9A00": "永豐金", "9B00": "台新",
    "F020": "群益期貨",
}


def canonical_code(code: str) -> str:
    code = code.strip().upper()
    return CODE_ALIASES.get(code, code)


def clean_name(name: str) -> str:
    """'群益金鼎證券公司' -> '群益金鼎', '元富(註1)' -> '元富', '宏    遠' -> '宏遠'."""
    name = re.sub(r"\s+", "", name or "")
    name = re.sub(r"[（(]註\d*[)）]", "", name)
    name = re.sub(r"(股份有限公司|公司)$", "", name)
    name = re.sub(r"證券$", "", name)
    return name


def display_name(code: str, fallback: str = "") -> str:
    return NAMES.get(code) or clean_name(fallback) or code
