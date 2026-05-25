import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

DB_PATH = "taiwan_election_2024.db"

st.set_page_config(page_title="2024 台灣選舉儀表板", page_icon="🗳️", layout="wide")

# ── 資料載入函數 ──────────────────────────────────────────────────────────────
@st.cache_data
def load_president_national():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT c.name AS candidate, pa.name AS party, SUM(p.votes) AS votes
        FROM presidents p
        JOIN candidates c ON p.candidate_id = c.id
        JOIN parties pa ON c.party_id = pa.id
        GROUP BY c.name, pa.name
        ORDER BY votes DESC
    """, conn)
    conn.close()
    df["vote_share"] = df["votes"] / df["votes"].sum()
    return df

@st.cache_data
def load_president_by_county():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT d.county, c.name AS candidate, pa.name AS party, SUM(p.votes) AS votes
        FROM presidents p
        JOIN districts d ON p.district_id = d.id
        JOIN candidates c ON p.candidate_id = c.id
        JOIN parties pa ON c.party_id = pa.id
        GROUP BY d.county, c.name, pa.name
        ORDER BY d.county, votes DESC
    """, conn)
    conn.close()
    return df

@st.cache_data
def load_turnout():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT d.county,
               SUM(pp.effective_votes + pp.wasted_votes) AS total_voted,
               SUM(pp.issued_votes + pp.remained_votes) AS total_eligible
        FROM polling_places pp
        JOIN districts d ON pp.district_id = d.id
        WHERE pp.election_type_id = 1
        GROUP BY d.county
    """, conn)
    conn.close()
    df["turnout"] = df["total_voted"] / df["total_eligible"]
    return df.sort_values("turnout", ascending=False)

@st.cache_data
def load_party_legislators():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT pa.name AS party, SUM(pl.votes) AS votes
        FROM party_legislators pl
        JOIN parties pa ON pl.party_id = pa.id
        GROUP BY pa.name
        ORDER BY votes DESC
    """, conn)
    conn.close()
    df["vote_share"] = df["votes"] / df["votes"].sum()
    return df

@st.cache_data
def load_legislator_seats():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT rl.legislator_region, c.name AS candidate, pa.name AS party, SUM(rl.votes) AS votes
        FROM regional_legislators rl
        JOIN candidates c ON rl.candidate_id = c.id
        JOIN parties pa ON c.party_id = pa.id
        GROUP BY rl.legislator_region, c.name, pa.name
    """, conn)
    conn.close()
    winner_idx = df.groupby("legislator_region")["votes"].idxmax()
    winners = df.loc[winner_idx]
    seats = winners.groupby("party").size().reset_index(name="seats")
    return seats.sort_values("seats", ascending=False)

# ── 黨色對應 ──────────────────────────────────────────────────────────────────
PARTY_COLORS = {
    "中國國民黨": "#000095",
    "民主進步黨": "#1B9431",
    "台灣民眾黨": "#28C8C8",
}

def get_color_sequence(parties):
    return [PARTY_COLORS.get(p, "#AAAAAA") for p in parties]

# ── 頁面標題 ──────────────────────────────────────────────────────────────────
st.title("🗳️ 2024 台灣總統暨立委選舉儀表板")
st.caption("資料來源：中央選舉委員會 | 2024年1月13日")

tab1, tab2, tab3, tab4 = st.tabs(["🏛️ 總統大選", "📋 立委選舉", "📊 投票率", "🔄 資料總覽"])

# ── Tab 1：總統大選 ───────────────────────────────────────────────────────────
with tab1:
    df_nat = load_president_national()
    df_county = load_president_by_county()

    st.subheader("全台得票結果")
    col1, col2, col3 = st.columns(3)
    for i, row in df_nat.iterrows():
        col = [col1, col2, col3][i]
        col.metric(
            label=f"{row['candidate']}　{row['party']}",
            value=f"{row['vote_share']:.1%}",
            delta=f"{row['votes']:,} 票"
        )

    fig_pie = px.pie(
        df_nat, values="votes", names="candidate",
        color="candidate",
        color_discrete_map={r["candidate"]: PARTY_COLORS.get(r["party"], "#AAAAAA") for _, r in df_nat.iterrows()},
        title="全台總統得票比例"
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    st.subheader("各縣市得票分佈")
    county_options = sorted(df_county["county"].unique())
    selected_counties = st.multiselect("選擇縣市（預設全選）", county_options, default=county_options)
    df_filtered = df_county[df_county["county"].isin(selected_counties)]

    fig_bar = px.bar(
        df_filtered, x="county", y="votes", color="candidate",
        color_discrete_map={r["candidate"]: PARTY_COLORS.get(r["party"], "#AAAAAA") for _, r in df_nat.iterrows()},
        title="各縣市候選人得票數",
        barmode="group"
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ── Tab 2：立委選舉 ───────────────────────────────────────────────────────────
with tab2:
    df_seats = load_legislator_seats()
    df_party_leg = load_party_legislators()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("區域立委席次")
        fig_seats = px.bar(
            df_seats.head(10), x="seats", y="party", orientation="h",
            color="party",
            color_discrete_map=PARTY_COLORS,
            title="各黨區域立委當選席次"
        )
        st.plotly_chart(fig_seats, use_container_width=True)

    with col2:
        st.subheader("政黨票得票比例")
        df_top = df_party_leg[df_party_leg["vote_share"] >= 0.01]
        fig_party = px.pie(
            df_top, values="votes", names="party",
            color="party",
            color_discrete_map=PARTY_COLORS,
            title="政黨票得票比例（1%以上）"
        )
        st.plotly_chart(fig_party, use_container_width=True)

# ── Tab 3：投票率 ─────────────────────────────────────────────────────────────
with tab3:
    df_turnout = load_turnout()

    st.subheader("各縣市投票率排行")
    fig_turnout = px.bar(
        df_turnout, x="turnout", y="county", orientation="h",
        color="turnout", color_continuous_scale="Teal",
        title="各縣市投票率",
        labels={"turnout": "投票率", "county": "縣市"}
    )
    fig_turnout.update_xaxes(tickformat=".1%")
    st.plotly_chart(fig_turnout, use_container_width=True)

    avg = df_turnout["turnout"].mean()
    st.info(f"全台平均投票率：{avg:.2%}")

# ── Tab 4：資料總覽 ───────────────────────────────────────────────────────────
with tab4:
    st.subheader("資料重新整理")
    if st.button("🔄 重新從資料庫載入"):
        st.cache_data.clear()
        st.success("快取已清除，資料已重新載入！")
        st.rerun()

    st.subheader("總統得票原始資料")
    st.dataframe(load_president_national(), use_container_width=True)

    st.subheader("各縣市投票率")
    st.dataframe(load_turnout(), use_container_width=True)

    st.subheader("政黨票")
    st.dataframe(load_party_legislators(), use_container_width=True)