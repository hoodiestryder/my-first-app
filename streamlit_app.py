import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# --- SETTINGS ---
st.set_page_config(page_title="Fast RBI Athlete Pro Dashboard", layout="wide")

# --- INITIALIZE DATABASE ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame()
if 'checkins' not in st.session_state:
    # This stores every single time a kid puts their weight in
    st.session_state.checkins = pd.DataFrame(columns=['Athlete', 'Date', 'Weight', 'Height'])

# --- HELPER: LINKING & ANALYTICS ---
def link_swings(blast_df, fs_df):
    if blast_df.empty or fs_df.empty: return pd.DataFrame()
    blast_df.columns = [c.strip() for c in blast_df.columns]
    fs_df.columns = [c.strip() for c in fs_df.columns]
    # Standardize Timestamps
    blast_df['Timestamp'] = pd.to_datetime(blast_df['Date'])
    fs_df['Timestamp'] = pd.to_datetime(fs_df['Date'] + ' ' + fs_df['Time'])
    blast_df = blast_df.sort_values('Timestamp')
    fs_df = fs_df.sort_values('Timestamp')
    # Fuzzy Match within 6 seconds
    return pd.merge_asof(fs_df, blast_df[['Timestamp', 'Bat Speed (mph)', 'Rotational Acceleration (g)', 'Attack Angle (deg)', 'Vertical Bat Angle (deg)']], 
                         on='Timestamp', direction='nearest', tolerance=pd.Timedelta('6s'))

def get_1_8th_metrics(df):
    """Anchor = ExitSpeed. Find stats for the top 12.5% hardest hits."""
    df['ExitSpeed'] = pd.to_numeric(df['ExitSpeed'], errors='coerce')
    hits = df[df['ExitSpeed'] > 0].dropna(subset=['ExitSpeed'])
    if hits.empty: return {k: 0 for k in ["BS_18", "RA_18", "EV_18", "SF_18", "HLA_18", "LA_18"]}
    hits = hits.sort_values('ExitSpeed', ascending=False)
    num_top = max(1, int(len(hits) * 0.125))
    top_8th = hits.head(num_top)
    bs_col = 'Bat Speed (mph)' if 'Bat Speed (mph)' in top_8th.columns else 'BatSpeed'
    return {
        "BS_18": top_8th[bs_col].mean(), "RA_18": top_8th['Rotational Acceleration (g)'].mean() if 'Rotational Acceleration (g)' in top_8th.columns else 0,
        "EV_18": top_8th['ExitSpeed'].mean(), "SF_18": top_8th['SmashFactor'].mean() if 'SmashFactor' in top_8th.columns else 0,
        "HLA_18": top_8th['Direction'].mean() if 'Direction' in top_8th.columns else 0, "LA_18": top_8th['Angle'].mean() if 'Angle' in top_8th.columns else 0,
        "Top_Hits": top_8th
    }

# --- UI: SIDEBAR ---
st.sidebar.title("Fast RBI Control")
athlete_name = st.sidebar.text_input("Enter Athlete Name", "Trenton Wheat")

st.sidebar.markdown("---")
st.sidebar.subheader("📍 Session Check-In")
with st.sidebar.form("daily_checkin"):
    check_date = st.date_input("Date of Check-in", datetime.now())
    w_input = st.number_input("Weight (lbs)", value=140.0, step=0.1)
    h_input = st.number_input("Height (in)", value=66.0, step=0.1)
    if st.form_submit_button("Submit Weight & Height"):
        new_row = pd.DataFrame([{'Athlete': athlete_name, 'Date': pd.to_datetime(check_date), 'Weight': w_input, 'Height': h_input}])
        st.session_state.checkins = pd.concat([st.session_state.checkins, new_row]).drop_duplicates()
        st.sidebar.success(f"Logged for {check_date.strftime('%b %d')}!")

# --- UI: TABS ---
tab1, tab2, tab3 = st.tabs(["Dashboard", "Upload Files", "Physical History"])

with tab2:
    st.header("Upload Data")
    col1, col2 = st.columns(2)
    with col1: b_file = st.file_uploader("Blast CSV", type="csv")
    with col2: fs_file = st.file_uploader("Full Swing CSV", type="csv")
    
    if st.button("Link & Save Data"):
        if b_file and fs_file:
            merged = link_swings(pd.read_csv(b_file, skiprows=8), pd.read_csv(fs_file))
            merged['Athlete'] = athlete_name
            st.session_state.master_df = pd.concat([st.session_state.master_df, merged]).drop_duplicates()
            st.success("Data Linked!")

with tab3:
    st.header("Physical Log History")
    a_checkins = st.session_state.checkins[st.session_state.checkins['Athlete'] == athlete_name]
    st.table(a_checkins.sort_values('Date', ascending=False))
    # Option to download so you don't lose data
    st.download_button("Download History as CSV", a_checkins.to_csv(index=False), f"{athlete_name}_physicals.csv")

with tab1:
    if st.session_state.master_df.empty:
        st.warning("Upload data to see the Trenton Wheat Table.")
    else:
        df = st.session_state.master_df[st.session_state.master_df['Athlete'] == athlete_name].copy()
        df['MonthGroup'] = pd.to_datetime(df['Timestamp']).dt.strftime('%Y-%m') # Using YYYY-MM to keep months sorted
        
        # Get Physicals for the athlete
        phys = st.session_state.checkins[st.session_state.checkins['Athlete'] == athlete_name].copy()
        phys['MonthGroup'] = pd.to_datetime(phys['Date']).dt.strftime('%Y-%m')
        # Average weight per month
        monthly_phys = phys.groupby('MonthGroup').agg({'Weight': 'mean', 'Height': 'mean'}).reset_index()

        monthly_report = []
        for month in sorted(df['MonthGroup'].unique(), reverse=True):
            m_df = df[df['MonthGroup'] == month]
            t8 = get_1_8th_metrics(m_df)
            top_hits = t8['Top_Hits']
            
            # Physicals for THIS month ONLY
            p_match = monthly_phys[monthly_phys['MonthGroup'] == month]
            m_weight = p_match['Weight'].values[0] if not p_match.empty else 0
            m_height = p_match['Height'].values[0] if not p_match.empty else 0
            
            # Whiff Calc
            bs_col = 'Bat Speed (mph)' if 'Bat Speed (mph)' in m_df.columns else 'BatSpeed'
            swings = m_df[m_df[bs_col] > 0]
            whiffs = swings[(swings['ExitSpeed'].isna()) | (swings['ExitSpeed'] == 0)]
            whiff_pct = (len(whiffs) / len(swings) * 100) if len(swings) > 0 else 0

            monthly_report.append({
                "Date Range": datetime.strptime(month, '%Y-%m').strftime('%b %Y'),
                "BS Avg": m_df[bs_col].mean(), "BS Max": m_df[bs_col].max(), "BS 1/8th": t8['BS_18'],
                "RA Avg": m_df['Rotational Acceleration (g)'].mean() if 'Rotational Acceleration (g)' in m_df.columns else 0,
                "RA 1/8th": t8['RA_18'], "AA Avg": m_df['Attack Angle (deg)'].mean() if 'Attack Angle (deg)' in m_df.columns else 0,
                "EV Avg": m_df['ExitSpeed'].mean(), "EV Max": m_df['ExitSpeed'].max(), "EV 1/8th": t8['EV_18'],
                "HLA Avg": t8['HLA_18'], "LA Avg": t8['LA_18'],
                "Burn %": (len(top_hits[(top_hits['Angle'] >= -1) & (top_hits['Angle'] <= 9.9)]) / len(top_hits) * 100) if len(top_hits) > 0 else 0,
                "Ropes %": (len(top_hits[(top_hits['Angle'] >= 10) & (top_hits['Angle'] <= 20)]) / len(top_hits) * 100) if len(top_hits) > 0 else 0,
                "Bombs %": (len(top_hits[(top_hits['Angle'] >= 21) & (top_hits['Angle'] <= 31)]) / len(top_hits) * 100) if len(top_hits) > 0 else 0,
                "SF": m_df['SmashFactor'].mean() if 'SmashFactor' in m_df.columns else 0,
                "1/8th SF": t8['SF_18'], "Weight": m_weight, "Whiff %": f"{whiff_pct:.1f}%",
                "mph/lbs": (m_df['ExitSpeed'].max() / m_weight) if m_weight > 0 else 0,
                "lbs/in": (m_weight / m_height) if m_height > 0 else 0
            })

        st.dataframe(pd.DataFrame(monthly_report).style.format(precision=1), use_container_width=True)
