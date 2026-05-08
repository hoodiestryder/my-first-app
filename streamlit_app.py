import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# --- APP SETUP ---
st.set_page_config(page_title="Fast RBI Athlete Pro", layout="wide")

# This is the "Internal Memory" of the app
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame()

st.title("⚾ Fast RBI Athlete Dashboard")

# --- THE CLEANING ENGINE (The Fix for your Error) ---
def clean_and_standardize(file):
    """This function is the 'Fix' for the Header Error."""
    try:
        # Read the file as raw text first to see what's inside
        content = file.read().decode('utf-8', errors='ignore')
        file.seek(0)
        
        # 1. DETECT FULL SWING
        if "PitchNo" in content or "Batter" in content:
            df = pd.read_csv(file)
            df.columns = [c.strip().replace('"', '') for c in df.columns]
            # THE FIX: Rename 'Batter' to 'Athlete' immediately
            if 'Batter' in df.columns:
                df = df.rename(columns={'Batter': 'Athlete'})
            # Create Timestamp
            df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
            return df, "Full Swing"

        # 2. DETECT BLAST MOTION
        # Scan for the row where the data actually starts
        lines = content.splitlines()
        data_start = -1
        athlete_from_header = "Unknown"
        
        for i, line in enumerate(lines):
            # Extract Leo Echevarria from the top header line
            if "Metrics -" in line:
                try:
                    athlete_from_header = line.split('-')[1].strip()
                except: pass
            
            if "Date" in line and "Equipment" in line:
                data_start = i
                break
        
        if data_start != -1:
            file.seek(0)
            df = pd.read_csv(file, skiprows=data_start)
            df.columns = [c.strip().replace('"', '') for c in df.columns]
            # THE FIX: Add the Athlete column using the name from the header
            df['Athlete'] = athlete_from_header
            df['Timestamp'] = pd.to_datetime(df['Date'], errors='coerce')
            return df, "Blast Motion"
            
    except Exception as e:
        st.error(f"Error processing {file.name}: {e}")
    return None, None

# --- UPLOAD SECTION ---
st.header("Step 1: Upload Session Files")
uploaded_files = st.file_uploader("Drag and drop your CSVs here", accept_multiple_files=True)

if uploaded_files:
    new_data = []
    for f in uploaded_files:
        df, file_type = clean_and_standardize(f)
        if df is not None:
            new_data.append(df)
            st.success(f"Successfully cleaned {file_type} for: {df['Athlete'].iloc[0]}")
    
    if st.button("Build Athlete Profiles"):
        # Combine everything into the master database
        if new_data:
            st.session_state.master_df = pd.concat(new_data, ignore_index=True)
            st.success("Profiles Updated! Scroll down to see results.")

# --- DASHBOARD SECTION ---
st.divider()
st.header("Step 2: Athlete Profiles")

if st.session_state.master_df.empty:
    st.info("No athlete data available. Please upload files above.")
else:
    # Filter by Athlete
    all_athletes = st.session_state.master_df['Athlete'].unique()
    selected_athlete = st.selectbox("Select Athlete Profile", all_athletes)
    
    athlete_df = st.session_state.master_df[st.session_state.master_df['Athlete'] == selected_athlete].copy()
    
    # --- TRENTON WHEAT MATH ---
    st.subheader(f"Performance Table: {selected_athlete}")
    
    # Ensure columns are numbers for math
    athlete_df['ExitSpeed'] = pd.to_numeric(athlete_df['ExitSpeed'], errors='coerce')
    athlete_df['Angle'] = pd.to_numeric(athlete_df['Angle'], errors='coerce')
    athlete_df['Month'] = athlete_df['Timestamp'].dt.strftime('%b %Y')
    
    # Determine the Correct Bat Speed Column
    # (Full Swing uses BatSpeed, Blast uses Bat Speed (mph))
    bs_col = 'Bat Speed (mph)' if 'Bat Speed (mph)' in athlete_df.columns else 'BatSpeed'
    
    monthly_rows = []
    for month in athlete_df['Month'].unique():
        m_df = athlete_df[athlete_df['Month'] == month]
        
        # FIND TOP 1/8th (12.5%) based on EXIT VELO
        hard_hits = m_df[m_df['ExitSpeed'] > 0].sort_values('ExitSpeed', ascending=False)
        num_8th = max(1, int(len(hard_hits) * 0.125))
        top_8th = hard_hits.head(num_8th)
        
        # Calculate Whiff %
        swings = m_df[m_df[bs_col] > 0]
        whiffs = swings[(swings['ExitSpeed'].isna()) | (swings['ExitSpeed'] == 0)]
        whiff_pct = (len(whiffs)/len(swings)*100) if len(swings)>0 else 0
        
        monthly_rows.append({
            "Month": month,
            "EV Max": m_df['ExitSpeed'].max(),
            "EV 1/8th": top_8th['ExitSpeed'].mean() if not top_8th.empty else 0,
            "BS 1/8th": top_8th[bs_col].mean() if not top_8th.empty and bs_col in top_8th.columns else 0,
            "Whiff %": f"{whiff_pct:.1f}%",
            "Burners %": (len(top_8th[(top_8th['Angle'] >= -1) & (top_8th['Angle'] <= 9.9)]) / len(top_8th) * 100) if not top_8th.empty else 0,
            "Ropes %": (len(top_8th[(top_8th['Angle'] >= 10) & (top_8th['Angle'] <= 20)]) / len(top_8th) * 100) if not top_8th.empty else 0,
            "Bombs %": (len(top_8th[(top_8th['Angle'] >= 21) & (top_8th['Angle'] <= 31)]) / len(top_8th) * 100) if not top_8th.empty else 0
        })

    st.table(pd.DataFrame(monthly_rows).style.format(precision=1))

    # Raw Data View for debugging
    with st.expander("View Raw Data for this Athlete"):
        st.write(athlete_df)
