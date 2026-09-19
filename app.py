import time

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
    "業績改善・上方修正・黒字転換と、"
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
# STEP 2：財務データ取得テスト（キヤノン 7751）
# =========================================================

st.divider()
st.subheader("🧪 財務データ取得テスト：キヤノン（7751）")

financial_url = "https://api.jquants.com/v2/fins/summary"

test_code = "7751"

fin_response = requests.get(
    financial_url,
    params={"code": test_code},
    headers=headers,
    timeout=30,
)

st.write(
    "APIステータス:",
    fin_response.status_code
)

if fin_response.status_code == 200:

    fin_data = fin_response.json().get("data", [])

    if len(fin_data) == 0:
        st.warning("財務データがありません。")

    else:
        fin_df = pd.DataFrame(fin_data)

        st.success(
            f"✅ キヤノン財務データ取得成功：{len(fin_df)}件"
        )

        fin_df = fin_df.sort_values(
            "DiscDate",
            ascending=False
        )

        st.write("### 📊 取得列")
        st.write(fin_df.columns.tolist())

        # 🪃で重要な列だけ表示
        important_cols = [
            "DiscDate",
            "DocType",
            "CurPerType",
            "CurFYEn",
            "Sales",
            "OP",
            "FOP"
        ]

        existing_cols = [
            col for col in important_cols
            if col in fin_df.columns
        ]

        st.write("### 🪃 キヤノン業績履歴")

        st.dataframe(
            fin_df[existing_cols].head(20),
            use_container_width=True
        )

else:
    st.error(
        f"財務データ取得失敗：{fin_response.status_code}"
    )
    st.write(fin_response.text)
# =========================================================
# STEP 3：最新決算 vs 前年同期
# =========================================================

st.divider()
st.subheader("🪃 最新決算 vs 前年同期")

# 日付型に変換
fin_df["DiscDate"] = pd.to_datetime(
    fin_df["DiscDate"],
    errors="coerce"
)

# 数値型に変換
for col in ["Sales", "OP", "FOP"]:
    if col in fin_df.columns:
        fin_df[col] = pd.to_numeric(
            fin_df[col],
            errors="coerce"
        )

# ---------------------------------------------------------
# 1. 最新の四半期決算を取得
# ---------------------------------------------------------

quarter_df = fin_df[
    fin_df["CurPerType"].isin(
        ["1Q", "2Q", "3Q", "FY"]
    )
].copy()

quarter_df = quarter_df.sort_values(
    "DiscDate",
    ascending=False
)

latest = quarter_df.iloc[0]

latest_period = latest["CurPerType"]
latest_fy_end = pd.to_datetime(
    latest["CurFYEn"],
    errors="coerce"
)

# ---------------------------------------------------------
# 2. 前年同期を探す
# ---------------------------------------------------------

previous_candidates = quarter_df[
    (quarter_df["CurPerType"] == latest_period)
    &
    (
        pd.to_datetime(
            quarter_df["CurFYEn"],
            errors="coerce"
        ).dt.year
        ==
        latest_fy_end.year - 1
    )
].copy()

if previous_candidates.empty:

    st.warning(
        "前年同期データが見つかりませんでした。"
    )

else:

    previous = (
        previous_candidates
        .sort_values(
            "DiscDate",
            ascending=False
        )
        .iloc[0]
    )

    latest_op = latest["OP"]
    previous_op = previous["OP"]

    latest_sales = latest["Sales"]
    previous_sales = previous["Sales"]

    latest_fop = latest["FOP"]

    # -----------------------------------------------------
    # 3. 前年同期比を計算
    # -----------------------------------------------------

    op_change = latest_op - previous_op

    if previous_op > 0:
        op_growth = (
            (latest_op / previous_op) - 1
        ) * 100
    else:
        op_growth = None

    if previous_sales > 0:
        sales_growth = (
            (latest_sales / previous_sales) - 1
        ) * 100
    else:
        sales_growth = None

    # 黒字転換
    turnaround = (
        previous_op <= 0
        and latest_op > 0
    )

    # -----------------------------------------------------
    # 4. 表示
    # -----------------------------------------------------

    st.write(
        f"最新決算：{latest_period} "
        f"（開示日 {latest['DiscDate'].date()}）"
    )

    st.write(
        f"前年同期：{previous['CurPerType']} "
        f"（開示日 {previous['DiscDate'].date()}）"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "最新営業利益",
            f"{latest_op / 1e8:,.1f}億円"
        )

    with col2:
        st.metric(
            "前年同期営業利益",
            f"{previous_op / 1e8:,.1f}億円"
        )

    with col3:

        if op_growth is not None:

            st.metric(
                "営業利益前年比",
                f"{op_growth:+.1f}%"
            )

        elif turnaround:

            st.metric(
                "営業利益前年比",
                "🔥 黒字転換"
            )

        else:

            st.metric(
                "営業利益前年比",
                "比較不能"
            )

    with col4:
        st.metric(
            "会社予想営業利益",
            (
                f"{latest_fop / 1e8:,.1f}億円"
                if pd.notna(latest_fop)
                else "―"
            )
        )

    # -----------------------------------------------------
    # 5. 詳細
    # -----------------------------------------------------

    st.write("### 📊 業績変化")

    result_df = pd.DataFrame(
        {
            "項目": [
                "売上高",
                "営業利益"
            ],
            "前年同期": [
                previous_sales / 1e8,
                previous_op / 1e8
            ],
            "最新": [
                latest_sales / 1e8,
                latest_op / 1e8
            ],
            "前年比(%)": [
                sales_growth,
                op_growth
            ]
        }
    )

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True
    )

    if turnaround:
        st.success(
            "🔥 営業利益が前年同期赤字から黒字へ転換"
        )
# =========================================================
# STEP 4：会社予想営業利益（FOP）の修正検知
# =========================================================

st.divider()
st.subheader("🪃 会社予想営業利益の修正")

# FOPが存在するデータだけ使用
fop_df = fin_df[
    fin_df["FOP"].notna()
].copy()

fop_df = fop_df.sort_values(
    "DiscDate",
    ascending=False
)

if fop_df.empty:

    st.warning(
        "会社予想営業利益（FOP）がありません。"
    )

else:

    # -----------------------------------------------------
    # 1. 現在の最新FOP
    # -----------------------------------------------------

    latest_fop_row = fop_df.iloc[0]

    current_fop = pd.to_numeric(
        latest_fop_row["FOP"],
        errors="coerce"
    )

    current_fop_date = latest_fop_row["DiscDate"]

    # -----------------------------------------------------
    # 2. 過去の「異なるFOP」を探す
    # -----------------------------------------------------

    previous_fop_row = None

    for _, row in fop_df.iloc[1:].iterrows():

        candidate_fop = pd.to_numeric(
            row["FOP"],
            errors="coerce"
        )

        if (
            pd.notna(candidate_fop)
            and
            pd.notna(current_fop)
            and
            candidate_fop != current_fop
        ):
            previous_fop_row = row
            break

    # -----------------------------------------------------
    # 3. 修正率を計算
    # -----------------------------------------------------

    if previous_fop_row is None:

        st.info(
            "比較できる過去の異なる会社予想がありません。"
        )

    else:

        previous_fop = pd.to_numeric(
            previous_fop_row["FOP"],
            errors="coerce"
        )

        previous_fop_date = previous_fop_row["DiscDate"]

        fop_change = (
            current_fop - previous_fop
        )

        if previous_fop != 0:

            fop_change_pct = (
                (current_fop / previous_fop) - 1
            ) * 100

        else:

            fop_change_pct = None

        # -------------------------------------------------
        # 4. 判定
        # -------------------------------------------------

        if current_fop > previous_fop:

            revision_label = "🟢 上方修正"

        elif current_fop < previous_fop:

            revision_label = "🔴 下方修正"

        else:

            revision_label = "⚪ 変更なし"

        # -------------------------------------------------
        # 5. 表示
        # -------------------------------------------------

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.metric(
                "現在会社予想",
                f"{current_fop / 1e8:,.1f}億円"
            )

        with col2:

            st.metric(
                "前回会社予想",
                f"{previous_fop / 1e8:,.1f}億円"
            )

        with col3:

            if fop_change_pct is not None:

                st.metric(
                    "予想修正率",
                    f"{fop_change_pct:+.2f}%"
                )

            else:

                st.metric(
                    "予想修正率",
                    "比較不能"
                )

        with col4:

            st.metric(
                "修正判定",
                revision_label
            )

        st.caption(
            f"前回予想：{previous_fop_date.date()} → "
            f"現在予想：{current_fop_date.date()}"
        )

        # -------------------------------------------------
        # 6. 修正額
        # -------------------------------------------------

        st.write("### 📈 会社予想の変化")

        revision_df = pd.DataFrame(
            {
                "項目": [
                    "会社予想営業利益"
                ],
                "前回予想（億円）": [
                    previous_fop / 1e8
                ],
                "現在予想（億円）": [
                    current_fop / 1e8
                ],
                "修正額（億円）": [
                    fop_change / 1e8
                ],
                "修正率（%）": [
                    fop_change_pct
                ]
            }
        )

        st.dataframe(
            revision_df,
            use_container_width=True,
            hide_index=True
        )
