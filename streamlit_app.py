import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# --- SETTINGS ---
st.set_page_config(page_title="Fast RBI Pro Analytics", layout="wide")

# Initialize memory (until we connect Google Sheets)
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame()
if 'checkins' not in st.session_state:
    st.session_state.checkins = pd.DataFrame(columns=['Athlete', 'Date', 'Weight', 'Height'])

# --- ANALYTICS ENGINE: TOP 1/8th ---
def get_1_8th_metrics(df):
    """Anchor = ExitSpeed. Find stats for the top 12.5% hardest hits."""
    # Ensure EV is numeric
    df['ExitSpeed'] = pd.to_numeric(df['ExitSpeed'], errors='coerce')
    hits = df[df['ExitSpeed'] > 0].dropna(subset=['ExitSpeed'])
    
    if hits.empty:
        return {k: 0 for k in ["BS_18", "RA_18", "EV_18", "SF_18", "HLA_18", "LA_18", "Top_Hits"]}
    
    hits = hits.sort_values('ExitSpeed', ascending=False)
    num_top = max(1, int(len(hits) * 0.125))
    top_8th = hits.head(num_top)
    
    # Identify which Bat Speed column to use
    bs_col = 'Bat Speed (mph)' if 'Bat Speed (mph)' in top_8th.columns else 'BatSpeed'
    
    return {
        "BS_18": top_8th[bs_col].mean() if bs_col in top_8th.columns else 0,
        "RA_18": top_8th['Rotational Acceleration (g)'].mean() if 'Rotational Acceleration (g)' in top_8th.columns else 0,
        "EV_18": top_8th['ExitSpeed'].mean(),
        "SF_18": top_8th['SmashFactor'].mean() if 'SmashFactor' in top_8th.columns else 0,
        "HLA_18": top_8th['Direction'].mean() if 'Direction' in top_8th.columns else 0,
        "LA_18": top_8th['Angle'].mean() if 'Angle' in top_8th.columns else 0,
        "Top_Hits": top_8th
    }

# --- DATA LINKING ENGINE ---
def process_upload(file):
    """Automatically detects file type and cleans it."""
    try:
        # 1. Try reading as Full Swing (No skip)
        df = pd.read_csv(file)
        if "PitchNo" in df.columns or "Batter" in df.columns:
            df.columns = [c.strip() for c in df.columns]
            # Convert 'Batter' to 'Athlete'
            if 'Batter' in df.columns:
                df = df.rename(columns={'Batter': 'Athlete'})
            df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
            df['Source'] = "FullSwing"
            return df
    except:
        pass
    
    try:
        # 2. Try reading as Blast (Skip 8 lines)
        file.seek(0) # Reset file pointer
        df = pd.read_csv(file, skiprows=8)
        df.columns = [c.strip() for c in df.columns]
        if "Bat Speed (mph)" in df.columns:
            df['Timestamp'] = pd.to_datetime(df['Date'])
            df['Source'] = "Blast"
            # Note: Blast individual exports don't always have names, 
            # we will assign it in the app logic
            return df
    except Exception as e:
        st.error(f"Could not read file: {e}")
        return None

# --- SIDEBAR ---
st.sidebar.title("Fast RBI Analytics")
athlete_name = st.sidebar.text_input("Enter Athlete Name", "Andrew Pereira")

with st.sidebar.form("Check-in"):
    st.subheader("📍 Monthly Check-In")
    check_w = st.number_input("Weight (lbs)", value=140.0)
    check_h = st.number_input("Height (in)", value=66.0)
    if st.form_submit_button("Log Physicals"):
        new_row = pd.DataFrame([{'Athlete': athlete_name, 'Date': pd.Timestamp.now(), 'Weight': check_w, 'Height': check_h}])
        st.session_state.checkins = pd.concat([st.session_state.checkins, new_row]).drop_duplicates()
        st.success("Logged!")

# --- TABS ---
tab1, tab2 = st.tabs(["Dashboard", "Upload Files"])

with tab2:
    st.header("Upload Session Data")
    uploaded_files = st.file_uploader("Upload Blast or Full Swing CSVs", accept_multiple_files=True)
    
    if st.button("Process Data"):
        all_new_data = []
        for f in uploaded_files:
            processed = process_upload(f)
            if processed is not None:
                if 'Athlete' not in processed.columns:
                    processed['Athlete'] = athlete_name
                all_new_data.append(processed)
        
        if all_new_data:
            st.session_state.master_df = pd.concat([st.session_state.master_df] + all_new_data).drop_duplicates()
            st.success("Successfully processed all files!")

with tab1:
    if st.session_state.master_df.empty:
        st.warning("No data yet. Upload files in the second tab.")
    else:
        df = st.session_state.master_df[st.session_state.master_df['Athlete'] == athlete_name].copy()
        df['MonthKey'] = pd.to_datetime(df['Timestamp']).dt.strftime('%Y-%m')
        
        # Link Physicals
        phys = st.session_state.checkins[st.session_state.checkins['Athlete'] == athlete_name].copy()
        if not phys.empty:
            phys['MonthKey'] = pd.to_datetime(phys['Date']).dt.strftime('%Y-%m')
            monthly_phys = phys.groupby('MonthKey').agg({'Weight': 'mean', 'Height': 'mean'}).reset_index()
        else:
            monthly_phys = pd.DataFrame(columns=['MonthKey', 'Weight', 'Height'])

        # Create Table
        report_rows = []
        for month in sorted(df['MonthKey'].unique(), reverse=True):
            m_df = df[df['MonthKey'] == month]
            t8 = get_1_8th_metrics(m_df)
            top_hits = t8['Top_Hits']
            
            # Whiff Calc
            bs_col = 'Bat Speed (mph)' if 'Bat Speed (mph)' in m_df.columns else 'BatSpeed'
            swings = m_df[m_df[bs_col] > 0]
            whiffs = swings[(swings['ExitSpeed'].isna()) | (swings['ExitSpeed'] == 0)]
            whiff_pct = (len(whiffs) / len(swings) * 100) if len(swings) > 0 else 0
            
            # Physicals
            p_row = monthly_phys[monthly_phys['MonthKey'] == month]
            curr_w = p_row['Weight'].values[0] if not p_row.empty else 0
            curr_h = p_row['Height'].values[0] if not p_row.empty else 0
            
            report_rows.append({
                "Date Range": datetime.strptime(month, '%Y-%m').strftime('%b %Y'),
                "BS Avg": m_df[bs_col].mean(),
                "BS Max": m_df[bs_col].max(),
                "BS 1/8th": t8['BS_18'],
                "RA Avg": m_df['Rotational Acceleration (g)'].mean() if 'Rotational Acceleration (g)' in m_df.columns else 0,
                "RA 1/8th": t8['RA_18'],
                "EV Max": m_df['ExitSpeed'].max(),
                "EV 1/8th": t8['EV_18'],
                "LA Avg": t8['LA_18'],
                "Whiff %": f"{whiff_pct:.1f}%",
                "Weight": curr_w,
                "mph/lbs": (m_df['ExitSpeed'].max() / curr_w) if curr_w > 0 else 0,
                "Sessions": len(pd.to_datetime(m_df['Timestamp']).dt.date.unique())
            })
            
        st.subheader(f"📊 Dashboard: {athlete_name}")
        st.dataframe(pd.DataFrame(report_rows).style.format(precision=1), use_container_width=True)
