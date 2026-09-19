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

test_code = "77510"

fin_url = "https://api.jquants.com/v2/fins/statements"

fin_response = requests.get(
    fin_url,
    headers=headers,
    params={"code": test_code},
    timeout=30,
)

if fin_response.status_code != 200:
    st.error(
        f"財務データ取得エラー："
        f"{fin_response.status_code}"
    )

    # エラー内容も確認
    st.write(fin_response.text)

else:
    fin_data = fin_response.json().get("data", [])

    if not fin_data:
        st.warning("財務データが取得できませんでした。")

    else:
        fin_df = pd.DataFrame(fin_data)

        st.success(
            f"財務データ取得成功：{len(fin_df)}件"
        )

        # 新しい開示が上に来るようにする
        if "DiscDate" in fin_df.columns:
            fin_df = fin_df.sort_values(
                "DiscDate",
                ascending=False
            )

        st.write("### 📊 取得できた列")

        st.write(
            fin_df.columns.tolist()
        )

        st.write("### 📋 キヤノン財務データ")

        st.dataframe(
            fin_df.head(20),
            use_container_width=True
        )
