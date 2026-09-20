import time
import io

import streamlit as st
import requests
import pandas as pd

# =========================================================
# 基本設定
# =========================================================

start_time = time.time()

st.set_page_config(
    page_title="業績×株価乖離レーダー",
    page_icon="🪃",
    layout="wide",
)

st.title("🪃 業績×株価乖離レーダー Ver.1")
st.subheader("業績が改善しているのに、株価がまだ反応していない企業を探す")

st.info(
    "業績改善・FOP Increase・黒字転換と、"
    "株価20日・60日の動きを比較して乖離を観測します。"
)


# =========================================================
# J-Quants API
# =========================================================

JQUANTS_API_KEY = st.secrets["JQUANTS_API_KEY"]

headers = {
    "x-api-key": JQUANTS_API_KEY
}


# =========================================================
# 銘柄マスター取得
# =========================================================

st.write("🪃 銘柄マスター取得中...")

master_url = "https://api.jquants.com/v2/equities/master"

master_response = requests.get(
    master_url,
    headers=headers,
    timeout=30,
)

if master_response.status_code != 200:
    st.error(
        f"銘柄マスター取得エラー："
        f"{master_response.status_code}"
    )
    st.stop()

master_data = master_response.json().get("data", [])

if not master_data:
    st.error("銘柄マスターが空です。")
    st.stop()

master_df = pd.DataFrame(master_data)

name_map_df = master_df[
    ["Code", "CoName"]
].copy()

name_map_df["Code"] = (
    name_map_df["Code"]
    .astype(str)
    .str.zfill(5)
)

# 東証内国株式
auto_codes = (
    master_df.loc[
        master_df["ProdCat"] == "011",
        "Code"
    ]
    .astype(str)
    .str.zfill(5)
    .tolist()
)

auto_code_set = set(auto_codes)

st.success(
    f"🪃 銘柄マスター取得完了："
    f"{len(auto_codes):,}銘柄"
)


# =========================================================
# 動作確認
# =========================================================

st.subheader("🪃 Boomerang Radar")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "監視対象",
        f"{len(auto_codes):,}銘柄"
    )

with col2:
    st.metric(
        "業績データ",
        "次STEP"
    )

with col3:
    st.metric(
        "株価乖離",
        "次STEP"
    )

elapsed = time.time() - start_time

st.caption(
    f"処理時間：{elapsed:.1f}秒"
)


# =========================================================
# STEP 6：全銘柄株価データ 高速Bulk版
# =========================================================

st.divider()
st.subheader("🪃 STEP 6：全銘柄株価データ高速取得")

st.write("📡 J-Quants Bulk一覧取得中...")


# =========================================================
# 1. Bulk一覧取得
# =========================================================

bulk_list_url = "https://api.jquants.com/v2/bulk/list"

bulk_response = requests.get(
    bulk_list_url,
    headers=headers,
    params={
        "endpoint": "/equities/bars/daily"
    },
    timeout=30,
)

if bulk_response.status_code != 200:
    st.error(
        f"Bulk一覧取得エラー："
        f"{bulk_response.status_code}"
    )
    st.stop()

bulk_data = bulk_response.json()

bulk_files = bulk_data.get("data", [])

if not bulk_files:
    st.error(
        "Bulkファイル一覧が取得できませんでした。"
    )
    st.stop()


# =========================================================
# 2. Historical / Live 分離
# =========================================================

live_bulk_files = [
    item
    for item in bulk_files
    if "/live/" in item.get("Key", "")
]

historical_bulk_files = [
    item
    for item in bulk_files
    if "/historical/" in item.get("Key", "")
]

if not live_bulk_files and not historical_bulk_files:
    st.error(
        "利用可能なBulkファイルがありません。"
    )
    st.stop()


# =========================================================
# 3. 読み込むBulkを決定
#
# 🪃は60営業日前まで必要。
# まず historical 直近3ファイル + live全部で試す。
# =========================================================

recent_historical_files = (
    historical_bulk_files[-3:]
)

bulk_target_files = (
    recent_historical_files
    + live_bulk_files
)

# Key重複除去
unique_files = {}

for item in bulk_target_files:

    key = item.get("Key")

    if key:
        unique_files[key] = item

bulk_target_files = list(
    unique_files.values()
)

st.write(
    f"📦 読み込み対象Bulk："
    f"{len(bulk_target_files)}ファイル"
)


# =========================================================
# 4. Bulkデータ取得
# =========================================================

bulk_get_url = (
    "https://api.jquants.com/v2/bulk/get"
)

bulk_dfs = []

progress_bar = st.progress(0)

status_text = st.empty()

total_files = len(bulk_target_files)


for i, bulk_item in enumerate(
    bulk_target_files
):

    item_key = bulk_item["Key"]

    status_text.write(
        f"📥 データ取得中 "
        f"{i + 1}/{total_files}"
    )

    # ---------------------------------------------
    # Download URL取得
    # ---------------------------------------------

    item_get_response = requests.get(
        bulk_get_url,
        headers=headers,
        params={
            "key": item_key
        },
        timeout=30,
    )

    if item_get_response.status_code != 200:

        st.warning(
            f"取得失敗：{item_key}"
        )

        continue

    item_get_data = (
        item_get_response.json()
    )

    item_download_url = (
        item_get_data.get("url")
    )

    if not item_download_url:

        st.warning(
            f"Download URLなし："
            f"{item_key}"
        )

        continue

    # ---------------------------------------------
    # gzip CSVダウンロード
    # ---------------------------------------------

    item_file_response = requests.get(
        item_download_url,
        timeout=60,
    )

    if item_file_response.status_code != 200:

        st.warning(
            f"ファイルDL失敗："
            f"{item_key}"
        )

        continue

    # ---------------------------------------------
    # CSV読込
    # ---------------------------------------------

    try:

        item_df = pd.read_csv(
            io.BytesIO(
                item_file_response.content
            ),
            compression="gzip",
            usecols=[
                "Date",
                "Code",
                "C",
                "AdjFactor",
            ],
            dtype={
                "Code": str
            },
        )
        
        bulk_dfs.append(
            item_df
        )

    except Exception as e:

        st.warning(
            f"CSV読込失敗："
            f"{item_key} / {e}"
        )

    progress_bar.progress(
        (i + 1) / total_files
    )


progress_bar.empty()
status_text.empty()


if not bulk_dfs:

    st.error(
        "日足データを取得できませんでした。"
    )

    st.stop()


# =========================================================
# 5. 全Bulk結合
# =========================================================

st.write(
    "🪃 日足データ結合中..."
)

bulk_all_df = pd.concat(
    bulk_dfs,
    ignore_index=True,
)


# =========================================================
# 6. データ整形
# =========================================================

bulk_all_df["Code"] = (
    bulk_all_df["Code"]
    .astype(str)
    .str.zfill(5)
)

# 東証内国株式のみ
bulk_all_df = bulk_all_df[
    bulk_all_df["Code"].isin(
        auto_code_set
    )
].copy()


bulk_all_df["Date"] = pd.to_datetime(
    bulk_all_df["Date"],
    errors="coerce",
)


bulk_all_df["C"] = pd.to_numeric(
    bulk_all_df["C"],
    errors="coerce",
)

bulk_all_df["AdjFactor"] = pd.to_numeric(
    bulk_all_df["AdjFactor"],
    errors="coerce",
)

bulk_all_df["AdjFactor"] = (
    bulk_all_df["AdjFactor"]
    .fillna(1.0)
)

bulk_all_df = bulk_all_df.dropna(
    subset=[
        "Code",
        "Date",
        "C",
    ]
)


# Historical / Liveの重複除去
bulk_all_df = (
    bulk_all_df
    .drop_duplicates(
        subset=[
            "Code",
            "Date",
        ],
        keep="last",
    )
)


# Code → Date順
bulk_all_df = (
    bulk_all_df
    .sort_values(
        [
            "Code",
            "Date",
        ]
    )
    .reset_index(drop=True)
)


st.success(
    f"株価データ結合完了："
    f"{len(bulk_all_df):,}行"
)


# =========================================================
# 7. 株式分割調整済み終値を作成
# =========================================================

# Code → Date順になっていることを確認
bulk_all_df = (
    bulk_all_df
    .sort_values(
        ["Code", "Date"]
    )
    .reset_index(drop=True)
)

# AdjFactorが欠損している日は1.0
bulk_all_df["AdjFactor"] = (
    pd.to_numeric(
        bulk_all_df["AdjFactor"],
        errors="coerce"
    )
    .fillna(1.0)
)

# ---------------------------------------------------------
# 将来のAdjFactorを累積
#
# 過去の株価を現在基準へ調整する
# ---------------------------------------------------------

bulk_all_df["CumAdjFactor"] = (
    bulk_all_df
    .groupby("Code")["AdjFactor"]
    .transform(
        lambda s:
        s.iloc[::-1]
        .cumprod()
        .iloc[::-1]
    )
)

# 当日自身のAdjFactorは翌日以降に効かせる
bulk_all_df["CumAdjFactor"] = (
    bulk_all_df["CumAdjFactor"]
    /
    bulk_all_df["AdjFactor"]
)

# 分割調整済み終値
bulk_all_df["AdjClose"] = (
    bulk_all_df["C"]
    *
    bulk_all_df["CumAdjFactor"]
)


# =========================================================
# 8. 20営業日前・60営業日前
# =========================================================

bulk_all_df["Close20"] = (
    bulk_all_df
    .groupby("Code")["AdjClose"]
    .shift(20)
)

bulk_all_df["Close60"] = (
    bulk_all_df
    .groupby("Code")["AdjClose"]
    .shift(60)
)


# =========================================================
# 9. 各銘柄の最新行だけ取得
# =========================================================

latest_price_df = (
    bulk_all_df
    .groupby(
        "Code",
        as_index=False
    )
    .tail(1)
    .copy()
)


# =========================================================
# 10. 騰落率計算
# =========================================================

latest_price_df["Return20"] = (
    (
        latest_price_df["AdjClose"]
        /
        latest_price_df["Close20"]
    )
    - 1
) * 100


latest_price_df["Return60"] = (
    (
        latest_price_df["AdjClose"]
        /
        latest_price_df["Close60"]
    )
    - 1
) * 100

# 60営業日取れていない銘柄は除外
valid_price_df = (
    latest_price_df
    .dropna(
        subset=[
            "Return20",
            "Return60",
        ]
    )
    .copy()
)


# =========================================================
# 10. 銘柄名追加
# =========================================================

valid_price_df = (
    valid_price_df
    .merge(
        name_map_df,
        on="Code",
        how="left",
    )
)


# =========================================================
# 11. 表示用
# =========================================================

price_summary_df = (
    valid_price_df[
        [
            "Code",
            "CoName",
            "Date",
            "C",
            "Return20",
            "Return60",
        ]
    ]
    .copy()
)


price_summary_df = (
    price_summary_df
    .rename(
        columns={
            "C": "LatestClose"
        }
    )
)


st.success(
    f"⚡ 20日・60日計算成功："
    f"{len(price_summary_df):,}銘柄"
)

st.write(
    "🔍 株価計算後の列名",
    bulk_all_df.columns.tolist()
)

st.write(
    "### 📊 全銘柄 株価20日・60日"
)


st.dataframe(
    price_summary_df.head(100),
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# 12. 処理時間
# =========================================================

bulk_elapsed = (
    time.time() - start_time
)

st.caption(
    f"🪃 現在までの処理時間："
    f"{bulk_elapsed:.1f}秒"
)

# =========================================================
# STEP 7：財務Bulkファイル確認
# =========================================================

st.divider()
st.subheader("🪃 STEP 7：全銘柄財務データ高速取得")

st.write("📡 財務Bulkファイルを確認中...")


# =========================================================
# 財務Bulk一覧取得
# =========================================================

fin_bulk_response = requests.get(
    "https://api.jquants.com/v2/bulk/list",
    headers=headers,
    params={
        "endpoint": "/fins/summary"
    },
    timeout=30,
)


st.write(
    "財務Bulk APIステータス:",
    fin_bulk_response.status_code
)


if fin_bulk_response.status_code != 200:

    st.error(
        "財務Bulk一覧を取得できませんでした。"
    )

    st.write(
        fin_bulk_response.text
    )

else:

    fin_bulk_data = (
        fin_bulk_response.json()
    )

    fin_bulk_files = (
        fin_bulk_data.get(
            "data",
            []
        )
    )

    if not fin_bulk_files:

        st.warning(
            "fins/summary のBulkファイルがありません。"
        )

    else:

        st.success(
            f"🪃 財務Bulk発見："
            f"{len(fin_bulk_files)}ファイル"
        )

        # ---------------------------------------------
        # Keyだけ確認
        # ---------------------------------------------

        fin_bulk_keys = [
            item.get("Key")
            for item in fin_bulk_files
            if item.get("Key")
        ]

        st.write(
            "### 📦 財務Bulkファイル"
        )

        st.dataframe(
            pd.DataFrame(
                {
                    "Key": fin_bulk_keys
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
# =========================================================
# STEP 7-2：最新財務Bulk 1ファイルの列確認
# =========================================================

st.write("### 🧪 最新財務Bulkの中身を確認")

# Keyがあるファイルだけ
valid_fin_files = [
    item
    for item in fin_bulk_files
    if item.get("Key")
]

# Key順に並べて最新を取得
valid_fin_files = sorted(
    valid_fin_files,
    key=lambda x: x["Key"]
)

latest_fin_item = valid_fin_files[-1]

latest_fin_key = latest_fin_item["Key"]

st.write(
    "確認ファイル：",
    latest_fin_key
)


# =========================================================
# Download URL取得
# =========================================================

fin_get_response = requests.get(
    "https://api.jquants.com/v2/bulk/get",
    headers=headers,
    params={
        "key": latest_fin_key
    },
    timeout=30,
)

if fin_get_response.status_code != 200:

    st.error(
        f"財務Bulk取得エラー："
        f"{fin_get_response.status_code}"
    )

    st.write(fin_get_response.text)

else:

    fin_download_url = (
        fin_get_response
        .json()
        .get("url")
    )

    if not fin_download_url:

        st.error(
            "Download URLがありません。"
        )

    else:

        fin_file_response = requests.get(
            fin_download_url,
            timeout=60,
        )

        if fin_file_response.status_code != 200:

            st.error(
                "財務CSVのダウンロードに失敗しました。"
            )

        else:

            try:

                test_fin_bulk_df = pd.read_csv(
                    io.BytesIO(
                        fin_file_response.content
                    ),
                    compression="gzip",
                    dtype={
                        "Code": str
                    },
                )

                st.success(
                    f"財務Bulk読込成功："
                    f"{len(test_fin_bulk_df):,}行"
                )

                st.write("### 📊 実際の列名")

                st.write(
                    test_fin_bulk_df.columns.tolist()
                )

                st.write("### 📋 先頭10行")

                st.dataframe(
                    test_fin_bulk_df.head(10),
                    use_container_width=True,
                )

            except Exception as e:

                st.error(
                    f"財務CSV読込エラー：{e}"
                )
# =========================================================
# STEP 7-3：重要そうな財務列だけ確認
# =========================================================

st.write("### 🔍 業績・予想関連の列名")

important_keywords = [
    "Sales",
    "OP",
    "OdP",
    "NP",
    "Forecast",
    "FOP",
]

important_columns = [
    col
    for col in test_fin_bulk_df.columns
    if any(
        keyword.lower() in col.lower()
        for keyword in important_keywords
    )
]

st.write(important_columns)

# =========================================================
# STEP 7-4：直近18か月 財務Bulk一括取得
# =========================================================

st.divider()
st.subheader("🪃 STEP 7-4：直近18か月 財務データ高速取得")

# ---------------------------------------------------------
# 18か月前の日付
# ---------------------------------------------------------

today_fin = pd.Timestamp.today().normalize()

fin_start_date = (
    today_fin - pd.DateOffset(months=18)
)

st.write(
    f"対象期間："
    f"{fin_start_date.date()} ～ {today_fin.date()}"
)


# =========================================================
# Historical / Live 分離
# =========================================================

fin_historical_files = [
    item
    for item in fin_bulk_files
    if "/historical/" in item.get("Key", "")
]

fin_live_files = [
    item
    for item in fin_bulk_files
    if "/live/" in item.get("Key", "")
]


# =========================================================
# Historicalから直近18か月分を選択
# =========================================================

target_historical_files = []

for item in fin_historical_files:

    key = item.get("Key", "")

    try:

        # 例：
        # fins_summary_202608.csv.gz

        filename = key.split("/")[-1]

        yyyymm = (
            filename
            .replace("fins_summary_", "")
            .replace(".csv.gz", "")
        )

        file_month = pd.to_datetime(
            yyyymm,
            format="%Y%m"
        )

        if file_month >= fin_start_date.replace(day=1):

            target_historical_files.append(
                item
            )

    except Exception:

        continue


# =========================================================
# Liveは全部使用
# =========================================================

fin_target_files = (
    target_historical_files
    + fin_live_files
)


# ---------------------------------------------------------
# Key重複除去
# ---------------------------------------------------------

unique_fin_files = {}

for item in fin_target_files:

    key = item.get("Key")

    if key:
        unique_fin_files[key] = item


fin_target_files = list(
    unique_fin_files.values()
)


st.write(
    f"📦 読み込み対象財務Bulk："
    f"{len(fin_target_files)}ファイル"
)


# =========================================================
# 財務Bulk取得
# =========================================================

fin_bulk_dfs = []

fin_progress = st.progress(0)

fin_status = st.empty()

total_fin_files = len(
    fin_target_files
)


for i, fin_item in enumerate(
    fin_target_files
):

    fin_key = fin_item["Key"]

    fin_status.write(
        f"📥 財務データ取得中 "
        f"{i + 1}/{total_fin_files}"
    )

    # ---------------------------------------------
    # Download URL取得
    # ---------------------------------------------

    get_response = requests.get(
        "https://api.jquants.com/v2/bulk/get",
        headers=headers,
        params={
            "key": fin_key
        },
        timeout=30,
    )

    if get_response.status_code != 200:

        st.warning(
            f"取得失敗：{fin_key}"
        )

        continue


    download_url = (
        get_response
        .json()
        .get("url")
    )

    if not download_url:

        st.warning(
            f"Download URLなし：{fin_key}"
        )

        continue


    # ---------------------------------------------
    # CSVダウンロード
    # ---------------------------------------------

    file_response = requests.get(
        download_url,
        timeout=60,
    )

    if file_response.status_code != 200:

        st.warning(
            f"CSV取得失敗：{fin_key}"
        )

        continue


    # ---------------------------------------------
    # CSV読込
    # ---------------------------------------------

    try:

        fin_part_df = pd.read_csv(
            io.BytesIO(
                file_response.content
            ),
            compression="gzip",
            dtype={
                "Code": str
            },
        )

        fin_bulk_dfs.append(
            fin_part_df
        )

    except Exception as e:

        st.warning(
            f"CSV読込失敗："
            f"{fin_key} / {e}"
        )


    fin_progress.progress(
        (i + 1)
        / total_fin_files
    )


fin_progress.empty()
fin_status.empty()


# =========================================================
# 財務Bulk結合
# =========================================================

if not fin_bulk_dfs:

    st.error(
        "財務データを取得できませんでした。"
    )

    st.stop()


st.write(
    "📡 財務データ結合中..."
)


all_fin_df = pd.concat(
    fin_bulk_dfs,
    ignore_index=True,
)


# =========================================================
# 基本整形
# =========================================================

all_fin_df["Code"] = (
    all_fin_df["Code"]
    .astype(str)
    .str.zfill(5)
)


all_fin_df["DiscDate"] = pd.to_datetime(
    all_fin_df["DiscDate"],
    errors="coerce",
)


# ---------------------------------------------------------
# 東証内国株式のみ
# ---------------------------------------------------------

all_fin_df = all_fin_df[
    all_fin_df["Code"].isin(
        auto_code_set
    )
].copy()


# ---------------------------------------------------------
# 実際の開示日でも18か月に限定
# ---------------------------------------------------------

all_fin_df = all_fin_df[
    all_fin_df["DiscDate"]
    >= fin_start_date
].copy()


# ---------------------------------------------------------
# 重複除去
#
# DiscNoが開示書類の識別子なので、
# 同じ開示がHistorical / Live双方にあっても1件にする
# ---------------------------------------------------------

if "DiscNo" in all_fin_df.columns:

    all_fin_df = (
        all_fin_df
        .drop_duplicates(
            subset=["DiscNo"],
            keep="last",
        )
    )


# ---------------------------------------------------------
# 開示日順
# ---------------------------------------------------------

all_fin_df = (
    all_fin_df
    .sort_values(
        [
            "Code",
            "DiscDate",
        ]
    )
    .reset_index(drop=True)
)


# =========================================================
# 数値列変換
# =========================================================

numeric_columns = [
    "Sales",
    "OP",
    "OdP",
    "NP",
    "FSales",
    "FOP",
    "FOdP",
    "FNP",
    "FSales2Q",
    "FOP2Q",
    "FOdP2Q",
    "FNP2Q",
]


for col in numeric_columns:

    if col in all_fin_df.columns:

        all_fin_df[col] = pd.to_numeric(
            all_fin_df[col],
            errors="coerce",
        )


# =========================================================
# 結果
# =========================================================

st.success(
    f"🪃 財務データ取得完了："
    f"{len(all_fin_df):,}行"
)


st.success(
    f"🪃 財務データ対象："
    f"{all_fin_df['Code'].nunique():,}銘柄"
)


# =========================================================
# 確認用表示
# =========================================================

display_fin_columns = [
    "DiscDate",
    "Code",
    "DocType",
    "CurPerType",
    "CurFYEn",
    "Sales",
    "OP",
    "FSales",
    "FOP",
]


display_fin_columns = [
    col
    for col in display_fin_columns
    if col in all_fin_df.columns
]


st.write(
    "### 📊 直近18か月 財務データ"
)


st.dataframe(
    all_fin_df[
        display_fin_columns
    ].tail(100),
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# DocType確認
# =========================================================

st.write(
    "### 🔍 DocType別件数"
)


doctype_count_df = (
    all_fin_df["DocType"]
    .value_counts()
    .reset_index()
)

doctype_count_df.columns = [
    "DocType",
    "件数",
]


st.dataframe(
    doctype_count_df,
    use_container_width=True,
    hide_index=True,
)

# =========================================================
# STEP 8：全銘柄 OP前年比 ＋ 黒字転換判定
# =========================================================

st.divider()
st.subheader("🪃 STEP 8：全銘柄 OP前年比・黒字転換判定")

st.write(
    "📡 最新決算と前年同期を比較しています..."
)


# =========================================================
# 1. 決算データだけ抽出
# =========================================================

financial_df = all_fin_df[
    all_fin_df["DocType"]
    .astype(str)
    .str.contains(
        "FinancialStatements",
        na=False,
    )
].copy()


# ---------------------------------------------------------
# 必要項目がない行を除外
# ---------------------------------------------------------

financial_df = financial_df.dropna(
    subset=[
        "Code",
        "DiscDate",
        "CurPerType",
        "CurFYEn",
        "OP",
    ]
).copy()


# =========================================================
# 2. 比較対象の決算期を限定
#
# 1Q → 前年1Q
# 2Q → 前年2Q
# 3Q → 前年3Q
# FY → 前年FY
# =========================================================

valid_periods = [
    "1Q",
    "2Q",
    "3Q",
    "FY",
]

financial_df = financial_df[
    financial_df["CurPerType"].isin(
        valid_periods
    )
].copy()


# =========================================================
# 3. 同じ決算が複数回開示されている場合の整理
#
# Code + CurFYEn + CurPerType ごとに
# 最も新しい開示を採用
# =========================================================

financial_df = (
    financial_df
    .sort_values(
        [
            "Code",
            "CurFYEn",
            "CurPerType",
            "DiscDate",
        ]
    )
    .drop_duplicates(
        subset=[
            "Code",
            "CurFYEn",
            "CurPerType",
        ],
        keep="last",
    )
    .reset_index(drop=True)
)


# =========================================================
# 4. 年度終了日を日付化
# =========================================================

financial_df["CurFYEn"] = pd.to_datetime(
    financial_df["CurFYEn"],
    errors="coerce",
)

financial_df = financial_df.dropna(
    subset=["CurFYEn"]
).copy()


# =========================================================
# 5. 前年同期を自己結合するためのデータ作成
# =========================================================

previous_df = financial_df[
    [
        "Code",
        "CurPerType",
        "CurFYEn",
        "OP",
        "Sales",
    ]
].copy()


previous_df = previous_df.rename(
    columns={
        "CurFYEn": "PrevFYEn",
        "OP": "PrevOP",
        "Sales": "PrevSales",
    }
)


# =========================================================
# 6. 前年の年度終了日を作成
#
# 例：
# 2027-03-31 → 2026-03-31
# =========================================================

financial_df["PrevFYEn"] = (
    financial_df["CurFYEn"]
    - pd.DateOffset(years=1)
)


# =========================================================
# 7. Code + 決算期 + 前年度終了日で前年同期を結合
# =========================================================

comparison_df = financial_df.merge(
    previous_df,
    on=[
        "Code",
        "CurPerType",
        "PrevFYEn",
    ],
    how="left",
)


# =========================================================
# 8. OP前年比を計算
# =========================================================

comparison_df["OP_YoY"] = pd.NA


# ---------------------------------------------------------
# 通常の前年比
#
# 前年OPがプラスの場合のみ
# %計算する
# ---------------------------------------------------------

positive_prev_mask = (
    comparison_df["PrevOP"] > 0
)

comparison_df.loc[
    positive_prev_mask,
    "OP_YoY"
] = (
    (
        comparison_df.loc[
            positive_prev_mask,
            "OP"
        ]
        /
        comparison_df.loc[
            positive_prev_mask,
            "PrevOP"
        ]
        - 1
    )
    * 100
)


comparison_df["OP_YoY"] = pd.to_numeric(
    comparison_df["OP_YoY"],
    errors="coerce",
)


# =========================================================
# 9. 黒字転換・赤字転落を判定
# =========================================================

comparison_df["Turnaround"] = (
    (comparison_df["PrevOP"] < 0)
    &
    (comparison_df["OP"] > 0)
)


comparison_df["LossTurn"] = (
    (comparison_df["PrevOP"] > 0)
    &
    (comparison_df["OP"] < 0)
)


# =========================================================
# 10. 増益判定
#
# 前年・今年とも黒字で、
# OPが前年を上回る場合
# =========================================================

comparison_df["ProfitGrowth"] = (
    (comparison_df["PrevOP"] > 0)
    &
    (comparison_df["OP"] > comparison_df["PrevOP"])
)


# =========================================================
# 11. 各銘柄の「最新決算」だけ取得
# =========================================================

latest_financial_df = (
    comparison_df
    .sort_values(
        [
            "Code",
            "DiscDate",
        ]
    )
    .groupby(
        "Code",
        as_index=False
    )
    .tail(1)
    .copy()
)


# =========================================================
# 12. 前年同期データが存在する銘柄だけ
# =========================================================

latest_financial_df = (
    latest_financial_df
    .dropna(
        subset=["PrevOP"]
    )
    .copy()
)


# =========================================================
# 13. 銘柄名を追加
# =========================================================

latest_financial_df = (
    latest_financial_df
    .merge(
        name_map_df,
        on="Code",
        how="left",
    )
)


# =========================================================
# 14. 億円表示用
# =========================================================

latest_financial_df["OP_Oku"] = (
    latest_financial_df["OP"]
    / 100_000_000
)


latest_financial_df["PrevOP_Oku"] = (
    latest_financial_df["PrevOP"]
    / 100_000_000
)


# =========================================================
# 15. 判定ラベル
# =========================================================

def make_op_label(row):

    if row["Turnaround"]:
        return "🔥 黒字転換"

    if row["LossTurn"]:
        return "🔻 赤字転落"

    if row["ProfitGrowth"]:
        return "🟢 増益"

    if (
        row["OP"] > 0
        and row["PrevOP"] > 0
    ):
        return "🟡 減益"

    if (
        row["OP"] < 0
        and row["PrevOP"] < 0
    ):

        if row["OP"] > row["PrevOP"]:
            return "🟠 赤字縮小"

        return "🔴 赤字拡大"

    return "－"


latest_financial_df["OP判定"] = (
    latest_financial_df.apply(
        make_op_label,
        axis=1,
    )
)


# =========================================================
# 16. 表示用データ
# =========================================================

op_result_df = latest_financial_df[
    [
        "Code",
        "CoName",
        "DiscDate",
        "CurPerType",
        "CurFYEn",
        "PrevOP_Oku",
        "OP_Oku",
        "OP_YoY",
        "OP判定",
        "Turnaround",
    ]
].copy()


op_result_df = op_result_df.rename(
    columns={
        "DiscDate": "開示日",
        "CurPerType": "決算期",
        "CurFYEn": "年度末",
        "PrevOP_Oku": "前年OP(億円)",
        "OP_Oku": "最新OP(億円)",
        "OP_YoY": "OP前年比(%)",
        "Turnaround": "黒字転換",
    }
)


# =========================================================
# 17. 結果
# =========================================================

st.success(
    f"🪃 前年同期比較成功："
    f"{len(op_result_df):,}銘柄"
)


turnaround_count = int(
    op_result_df["黒字転換"].sum()
)


growth_count = int(
    (
        op_result_df["OP判定"]
        == "🟢 増益"
    ).sum()
)


col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "前年同期比較",
        f"{len(op_result_df):,}銘柄",
    )


with col2:

    st.metric(
        "🟢 増益",
        f"{growth_count:,}銘柄",
    )


with col3:

    st.metric(
        "🔥 黒字転換",
        f"{turnaround_count:,}銘柄",
    )


# =========================================================
# 18. 黒字転換ランキング
# =========================================================

st.write(
    "### 🔥 前年赤字 → 黒字転換"
)


turnaround_df = (
    op_result_df[
        op_result_df["黒字転換"]
    ]
    .copy()
)


# 黒字転換後の営業利益が大きい順
turnaround_df = turnaround_df.sort_values(
    "最新OP(億円)",
    ascending=False,
)


st.dataframe(
    turnaround_df,
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# 19. 増益ランキング
# =========================================================

st.write(
    "### 🟢 営業利益 増益ランキング"
)


growth_df = (
    op_result_df[
        op_result_df["OP判定"]
        == "🟢 増益"
    ]
    .copy()
)


growth_df = growth_df.sort_values(
    "OP前年比(%)",
    ascending=False,
)


st.dataframe(
    growth_df.head(100),
    use_container_width=True,
    hide_index=True,
)

# =========================================================
# STEP 9：会社予想営業利益 FOP FOP Increase判定
# =========================================================

st.divider()
st.subheader("🪃 STEP 9：会社予想営業利益 FOP Increase判定")


# ---------------------------------------------------------
# STEP8で作成した財務データを使用
# fin_all_df を想定
# ---------------------------------------------------------

forecast_df = all_fin_df.copy()


# ---------------------------------------------------------
# 必要列チェック
# ---------------------------------------------------------

required_cols = [
    "Code",
    "DiscDate",
    "CurFYEn",
    "FOP",
]

missing_cols = [
    col
    for col in required_cols
    if col not in forecast_df.columns
]

if missing_cols:

    st.error(
        f"必要な列がありません：{missing_cols}"
    )

else:

    # -----------------------------------------------------
    # 型を整える
    # -----------------------------------------------------

    forecast_df["Code"] = (
        forecast_df["Code"]
        .astype(str)
        .str.zfill(5)
    )

    forecast_df["DiscDate"] = pd.to_datetime(
        forecast_df["DiscDate"],
        errors="coerce"
    )

    forecast_df["CurFYEn"] = pd.to_datetime(
        forecast_df["CurFYEn"],
        errors="coerce"
    )

    forecast_df["FOP"] = pd.to_numeric(
        forecast_df["FOP"],
        errors="coerce"
    )


    # -----------------------------------------------------
    # 会社予想営業利益が存在する行だけ
    # -----------------------------------------------------

    forecast_df = forecast_df.dropna(
        subset=[
            "Code",
            "DiscDate",
            "CurFYEn",
            "FOP",
        ]
    ).copy()


    # -----------------------------------------------------
    # 東証内国株式のみ
    # -----------------------------------------------------

    forecast_df = forecast_df[
        forecast_df["Code"].isin(
            auto_code_set
        )
    ].copy()


    # -----------------------------------------------------
    # 同一銘柄・同一年度内で開示日順
    # -----------------------------------------------------

    forecast_df = forecast_df.sort_values(
        [
            "Code",
            "CurFYEn",
            "DiscDate",
        ]
    )


    # -----------------------------------------------------
    # 前回会社予想を作る
    #
    # 同じFOPが決算ごとに繰り返し掲載されることがあるため
    # 単純shiftだけではなく、
    # 「予想値が変化した履歴」を見る
    # -----------------------------------------------------

    revision_rows = []

    for (code, fy_end), group in forecast_df.groupby(
        [
            "Code",
            "CurFYEn",
        ]
    ):

        group = group.sort_values(
            "DiscDate"
        ).copy()

        # 同じ予想値の連続重複を除く
        group["PrevRawFOP"] = (
            group["FOP"]
            .shift(1)
        )

        changed_group = group[
            (
                group["PrevRawFOP"].isna()
            )
            |
            (
                group["FOP"]
                != group["PrevRawFOP"]
            )
        ].copy()

        # 最低2回の異なる会社予想が必要
        if len(changed_group) < 2:
            continue

        latest = changed_group.iloc[-1]
        previous = changed_group.iloc[-2]

        prev_fop = previous["FOP"]
        latest_fop = latest["FOP"]

        # -------------------------------------------------
        # 修正額
        # -------------------------------------------------

        revision_amount = (
            latest_fop
            - prev_fop
        )

        # -------------------------------------------------
        # 修正率
        #
        # 前回予想が0以下の場合、
        # %表示は意味が崩れるのでNone
        # -------------------------------------------------

        if prev_fop > 0:

            revision_rate = (
                (
                    latest_fop
                    / prev_fop
                )
                - 1
            ) * 100

        else:

            revision_rate = None


        # -------------------------------------------------
        # 判定
        # -------------------------------------------------

        if (
            prev_fop < 0
            and latest_fop > 0
        ):

            revision_type = "🔥 予想黒字転換"

        elif latest_fop > prev_fop:

            revision_type = "🟢 FOP Increase"

        elif latest_fop < prev_fop:

            revision_type = "🔴 下方修正"

        else:

            revision_type = "⚪ 据え置き"


        revision_rows.append({
            "Code": code,
            "CurFYEn": fy_end,

            "PrevDiscDate":
                previous["DiscDate"],

            "LatestDiscDate":
                latest["DiscDate"],

            "PrevFOP":
                prev_fop,

            "LatestFOP":
                latest_fop,

            "RevisionAmount":
                revision_amount,

            "RevisionRate":
                revision_rate,

            "RevisionType":
                revision_type,
        })


    # -----------------------------------------------------
    # DataFrame化
    # -----------------------------------------------------

    revision_df = pd.DataFrame(
        revision_rows
    )


    if revision_df.empty:

        st.warning(
            "会社予想の変更履歴を取得できませんでした。"
        )

    else:

        # -------------------------------------------------
        # 銘柄名追加
        # -------------------------------------------------

        revision_df = revision_df.merge(
            name_map_df,
            on="Code",
            how="left"
        )


        # -------------------------------------------------
        # 億円表示
        # -------------------------------------------------

        revision_df[
            "PrevFOP億円"
        ] = (
            revision_df["PrevFOP"]
            / 100_000_000
        )

        revision_df[
            "LatestFOP億円"
        ] = (
            revision_df["LatestFOP"]
            / 100_000_000
        )

        revision_df[
            "RevisionAmount億円"
        ] = (
            revision_df["RevisionAmount"]
            / 100_000_000
        )


        # -------------------------------------------------
        # FOP Increaseのみ
        # -------------------------------------------------

        upward_df = revision_df[
            revision_df[
                "LatestFOP"
            ]
            >
            revision_df[
                "PrevFOP"
            ]
        ].copy()


        # -------------------------------------------------
        # 集計表示
        # -------------------------------------------------

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "予想変更を確認",
                f"{len(revision_df):,}銘柄"
            )

        with col2:

            st.metric(
                "FOP Increase",
                f"{len(upward_df):,}銘柄"
            )

        with col3:

            forecast_turnaround_count = (
                revision_df[
                    "RevisionType"
                ]
                .eq(
                    "🔥 予想黒字転換"
                )
                .sum()
            )

            st.metric(
                "予想黒字転換",
                f"{forecast_turnaround_count:,}銘柄"
            )


        # -------------------------------------------------
        # FOP Increase一覧
        # -------------------------------------------------

        st.write(
            "### 🟢 会社予想営業利益 FOP Increase"
        )

        upward_display_df = (
            upward_df[
                [
                    "Code",
                    "CoName",
                    "CurFYEn",
                    "PrevDiscDate",
                    "LatestDiscDate",
                    "PrevFOP億円",
                    "LatestFOP億円",
                    "RevisionAmount億円",
                    "RevisionRate",
                    "RevisionType",
                ]
            ]
            .sort_values(
                "LatestDiscDate",
                ascending=False
            )
        )

        st.dataframe(
            upward_display_df,
            use_container_width=True,
            hide_index=True,
        )


        # -------------------------------------------------
        # 予想黒字転換
        # -------------------------------------------------

        forecast_turnaround_df = (
            revision_df[
                revision_df[
                    "RevisionType"
                ]
                ==
                "🔥 予想黒字転換"
            ]
            .copy()
        )

        st.write(
            "### 🔥 会社予想 赤字 → 黒字転換"
        )

        st.dataframe(
            forecast_turnaround_df[
                [
                    "Code",
                    "CoName",
                    "CurFYEn",
                    "PrevDiscDate",
                    "LatestDiscDate",
                    "PrevFOP億円",
                    "LatestFOP億円",
                    "RevisionAmount億円",
                    "RevisionType",
                ]
            ]
            .sort_values(
                "LatestDiscDate",
                ascending=False
            ),
            use_container_width=True,
            hide_index=True,
        )

# =========================================================
# STEP 10：業績 × 株価 統合観測テーブル
# =========================================================

st.divider()
st.subheader("🪃 STEP 10：業績 × 株価 統合観測テーブル")

st.info(
    "実績営業利益・会社予想の変化と、"
    "株価20日・60日の反応を同じテーブルで観測します。"
)


# =========================================================
# ① STEP8の業績データを準備
# =========================================================

# STEP8の全銘柄業績データをSTEP10へ引き継ぐ
performance_merge_df = growth_df.copy()

st.write(
    "STEP10 接続元 growth_df：",
    len(performance_merge_df),
    performance_merge_df.columns.tolist()
)

performance_merge_df = performance_merge_df.rename(
    columns={
        "PrevOP": "PrevOP実績",
        "LatestOP": "LatestOP実績",
        "OPYoY": "OP前年比",
        "Turnaround": "黒字転換",
    }
)


# =========================================================
# ② STEP9の会社予想データを準備
# =========================================================

forecast_merge_df = revision_df[
    [
        "Code",
        "PrevFOP",
        "LatestFOP",
        "RevisionAmount",
        "RevisionRate",
        "RevisionType",
        "LatestDiscDate",
    ]
].copy()

forecast_merge_df = forecast_merge_df.rename(
    columns={
        "RevisionAmount": "FOP修正額",
        "RevisionRate": "FOP修正率",
        "RevisionType": "FOP修正判定",
        "LatestDiscDate": "予想修正開示日",
    }
)


# =========================================================
# ③ STEP6の株価データを準備
# =========================================================

price_merge_df = price_summary_df[
    [
        "Code",
        "CoName",
        "LatestClose",
        "Return20",
        "Return60",
    ]
].copy()


# =========================================================
# ④ Codeを統一
# =========================================================

for df in [
    performance_merge_df,
    forecast_merge_df,
    price_merge_df,
]:

    df["Code"] = (
        df["Code"]
        .astype(str)
        .str.zfill(5)
    )


# =========================================================
# ⑤ 3データを結合
# =========================================================

boomerang_df = (
    performance_merge_df
    .merge(
        price_merge_df,
        on="Code",
        how="left",
    )
    .merge(
        forecast_merge_df,
        on="Code",
        how="left",
    )
)


# =========================================================
# ⑥ 金額を億円へ
# =========================================================

money_cols = [
    "PrevOP実績",
    "LatestOP実績",
    "PrevFOP",
    "LatestFOP",
    "FOP修正額",
]

for col in money_cols:

    if col in boomerang_df.columns:

        boomerang_df[col] = (
            pd.to_numeric(
                boomerang_df[col],
                errors="coerce",
            )
            / 100_000_000
        )


# =========================================================
# ⑦ 数値列を整える
# =========================================================

numeric_cols = [
    "OP前年比",
    "FOP修正率",
    "LatestClose",
    "Return20",
    "Return60",
]

for col in numeric_cols:

    if col in boomerang_df.columns:

        boomerang_df[col] = pd.to_numeric(
            boomerang_df[col],
            errors="coerce",
        )

# =========================================================
# ⑧ 銘柄名整理
# =========================================================

if "CoName_x" in boomerang_df.columns:
    boomerang_df = boomerang_df.rename(
        columns={
            "CoName_x": "CoName"
        }
    )

if "CoName_y" in boomerang_df.columns:
    boomerang_df = boomerang_df.drop(
        columns=["CoName_y"]
    )


# =========================================================
# ⑦-2 重複銘柄を整理
# 1銘柄 = 1行
# 最新の開示データを残す
# =========================================================

boomerang_df["開示日"] = pd.to_datetime(
    boomerang_df["開示日"],
    errors="coerce"
)

boomerang_df = (
    boomerang_df
    .sort_values(
        ["Code", "開示日"],
        ascending=[True, False]
    )
    .drop_duplicates(
        subset=["Code"],
        keep="first"
    )
    .reset_index(drop=True)
)

# =========================================================
# ⑨ 観測用フラグ
# =========================================================

boomerang_df["実績改善"] = (
    boomerang_df["最新OP(億円)"]
    >
    boomerang_df["前年OP(億円)"]
)

boomerang_df["会社予想FOP Increase"] = (
    boomerang_df["LatestFOP"]
    >
    boomerang_df["PrevFOP"]
)

boomerang_df["20日株価未反応"] = (
    boomerang_df["Return20"] <= 0
)

boomerang_df["60日株価未反応"] = (FOP Increase
    boomerang_df["Return60"] <= 0
)

# =========================================================
# ⑨ 🪃候補タイプ
# =========================================================

def classify_boomerang(row):

    signals = []

    if row.get("黒字転換", False):
        signals.append("🔥実績黒転")

    if (
        row.get("FOP修正判定")
        == "🔥 予想黒字転換"
    ):
        signals.append("🔥予想黒転")

    elif row.get("会社予想FOP Increase", False):
        signals.append("🟢FOP Increase")

    if row.get("20日株価未反応", False):
        signals.append("📉20日未反応")

    if row.get("60日株価未反応", False):
        signals.append("📉60日未反応")

    if not signals:
        return ""

    return " / ".join(signals)


boomerang_df["観測シグナル"] = (
    boomerang_df.apply(
        classify_boomerang,
        axis=1,
    )
)


# =========================================================
# ⑩ まずは簡単な観測ポイント
#
# まだ最終BoomerangScoreにはしません。
# シグナル数だけ数えて上位を観察します。
# =========================================================

boomerang_df["SignalCount"] = (
    boomerang_df[
        [
            "実績改善",
            "黒字転換",
            "FOPI",
            "20日株価未反応",
            "60日株価未反応",
        ]
    ]
    .fillna(False)
    .astype(int)
    .sum(axis=1)
)


# =========================================================
# ⑪ 集計
# =========================================================

valid_boomerang_df = boomerang_df.dropna(
    subset=[
        "Return20",
        "Return60",
    ]
).copy()


strong_candidate_df = valid_boomerang_df[
    (
        valid_boomerang_df["実績改善"]
        |
        valid_boomerang_df["FOPI"]
        |
        valid_boomerang_df["黒字転換"]
    )
    &
    (
        valid_boomerang_df["20日株価未反応"]
        |
        valid_boomerang_df["60日株価未反応"]
    )
].copy()


col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "統合観測銘柄",
        f"{len(valid_boomerang_df):,}銘柄",
    )

with col2:

    st.metric(
        "業績改善＋株価未反応",
        f"{len(strong_candidate_df):,}銘柄",
    )

with col3:

    double_negative_count = (
        (
            strong_candidate_df["Return20"] < 0
        )
        &
        (
            strong_candidate_df["Return60"] < 0
        )
    ).sum()

    st.metric(
        "20日・60日ともマイナス",
        f"{double_negative_count:,}銘柄",
    )


# =========================================================
# ⑫ 🪃 業績改善 × 株価未反応
# =========================================================

st.write(
    "### 🪃 業績改善 × 株価未反応"
)

strong_candidate_df = (
    strong_candidate_df
    .sort_values(
        [
            "SignalCount",
            "Return20",
        ],
        ascending=[
            False,
            True,
        ],
    )
)


display_cols = [
    "Code",
    "CoName",
    "LatestClose",
    "Return20",
    "Return60",
    "PrevOP実績",
    "LatestOP実績",
    "OP前年比",
    "黒字転換",
    "PrevFOP",
    "LatestFOP",
    "FOP修正率",
    "FOP修正判定",
    "SignalCount",
    "観測シグナル",
]

display_cols = [
    col
    for col in display_cols
    if col in strong_candidate_df.columns
]


st.dataframe(
    strong_candidate_df[
        display_cols
    ].head(200),
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# ⑬ 特に面白いゾーン
#     業績改善なのに20日・60日とも株価マイナス
# =========================================================

deep_boomerang_df = strong_candidate_df[
    (
        strong_candidate_df["Return20"] < 0
    )
    &
    (
        strong_candidate_df["Return60"] < 0
    )
].copy()


st.write(
    "### 🔥🪃 20日・60日とも株価マイナス"
)

st.caption(
    "業績改善シグナルがある一方、"
    "20日・60日の株価騰落率がともにマイナスの銘柄です。"
)

st.dataframe(
    deep_boomerang_df[
        display_cols
    ].head(100),
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# 処理時間
# =========================================================

elapsed = time.time() - start_time

st.caption(
    f"🪃 現在までの処理時間：{elapsed:.1f}秒"
)
