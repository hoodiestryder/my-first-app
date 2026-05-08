import streamlit as st
import pandas as pd
import numpy as np

# 1. Setup the Page
st.set_page_config(page_title="Fast RBI Athlete Assistant", layout="wide")
st.title("⚾ Fast RBI Performance Dashboard")

# Initialize memory
if 'master_data' not in st.session_state:
    st.session_state.master_data = pd.DataFrame()

# --- THE SMART LOADER (Fixes the ParserError) ---
def smart_load(file):
    try:
        # Check first few lines to see if it's Blast or Full Swing
        header_check = file.read(500).decode('utf-8', errors='ignore')
        file.seek(0)
        
        if "PitchNo" in header_check or "Batter" in header_check:
            # FULL SWING LOGIC
            df = pd.read_csv(file)
            df.columns = [c.strip().replace('"', '') for c in df.columns]
            if 'Batter' in df.columns:
                df = df.rename(columns={'Batter': 'Athlete'})
            # Link Date and Time
            df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
            return df, "Full Swing"
            
        else:
            # BLAST MOTION LOGIC (The "Skip" Fix)
            # We skip 8 lines to get past the Copyright/Email stuff
            df = pd.read_csv(file, skiprows=8)
            df.columns = [c.strip().replace('"', '') for c in df.columns]
            
            # Extract name from filename or top header if possible
            # For now, let's look for Date to confirm it's a Blast file
            if "Date" in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Date'], errors='coerce')
                return df, "Blast Motion"
                
    except Exception as e:
        st.error(f"Error reading file: {e}")
    return None, None

# --- SIDEBAR ---
st.sidebar.header("Athlete Settings")
manual_name = st.sidebar.text_input("Assign Name to Blast Data:", "Leo Echevarria")

# --- UPLOAD SECTION ---
st.header("1. Upload CSV Files")
uploaded_files = st.file_uploader("Upload Blast or Full Swing CSVs", accept_multiple_files=True)

if uploaded_files:
    temp_dfs = []
    for f in uploaded_files:
        df, file_type = smart_load(f)
        if df is not None:
            # If Blast file, it often lacks a name column, so we add the sidebar name
            if file_type == "Blast Motion" and 'Athlete' not in df.columns:
                df['Athlete'] = manual_name
            
            temp_dfs.append(df)
            st.success(f"Successfully Loaded {file_type}: {f.name}")
    
    if st.button("Generate Dashboard Table"):
        if temp_dfs:
            st.session_state.master_data = pd.concat(temp_dfs, ignore_index=True)

# --- DASHBOARD SECTION ---
if not st.session_state.master_data.empty:
    st.header("2. Performance Table")
    master = st.session_state.master_data
    
    # Filter by Athlete
    athletes = master['Athlete'].unique()
    selected = st.selectbox("Select Athlete Profile", athletes)
    
    a_df = master[master['Athlete'] == selected].copy()
    a_df['ExitSpeed'] = pd.to_numeric(a_df['ExitSpeed'], errors='coerce')
    a_df['Angle'] = pd.to_numeric(a_df['Angle'], errors='coerce')
    
    # Identify the Top 12.5% of Exit Velo
    hard_hits = a_df[a_df['ExitSpeed'] > 0].sort_values('ExitSpeed', ascending=False)
    num_top = max(1, int(len(hard_hits) * 0.125))
    top_8th = hard_hits.head(num_top)
    
    # Simple Trenton Wheat Style Summary
    if not top_8th.empty:
        summary = {
            "Athlete": selected,
            "EV Max": a_df['ExitSpeed'].max(),
            "EV 1/8th Avg": top_8th['ExitSpeed'].mean(),
            "LA 1/8th Avg": top_8th['Angle'].mean(),
            "Burners %": (len(top_8th[(top_8th['Angle'] >= -1) & (top_8th['Angle'] <= 9.9)]) / len(top_8th) * 100),
            "Ropes %": (len(top_8th[(top_8th['Angle'] >= 10) & (top_8th['Angle'] <= 20)]) / len(top_8th) * 100),
            "Bombs %": (len(top_8th[(top_8th['Angle'] >= 21) & (top_8th['Angle'] <= 31)]) / len(top_8th) * 100)
        }
        st.table(pd.DataFrame([summary]).style.format(precision=1))
    
    with st.expander("Show Raw Merged Data"):
        st.dataframe(a_df)
