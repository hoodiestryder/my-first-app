import streamlit as st
import pandas as pd
import numpy as np
import re

# --- SETUP ---
st.set_page_config(page_title="Fast RBI Final Fix", layout="wide")
st.title("⚾ Fast RBI Athlete Dashboard")

# --- DATA STORAGE (Temporary until Google Sheets is linked) ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame()

# --- THE "LASER" LOADERS ---

def load_full_swing(file):
    """Detects 'Batter' and converts to 'Player'"""
    df = pd.read_csv(file)
    df.columns = [c.strip().replace('"', '') for c in df.columns]
    
    if 'Batter' in df.columns:
        df = df.rename(columns={'Batter': 'Player'})
        # Combine Date and Time
        df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
        return df
    return None

def load_blast(file):
    """Extracts name from the Row 0 'Sentence' and reads data below."""
    # 1. Grab the name from the very first line
    # Format: "Metrics - Leo Echevarria - 2026-03-01..."
    first_line = pd.read_csv(file, nrows=0).columns[0]
    try:
        athlete_name = first_line.split('-')[1].strip()
    except:
        athlete_name = "Unknown Athlete"
    
    # 2. Find the actual data table (scans for the word "Date")
    file.seek(0)
    lines = file.readlines()
    data_start_row = 0
    for i, line in enumerate(lines):
        if b"Date" in line and b"Equipment" in line:
            data_start_row = i
            break
            
    file.seek(0)
    df = pd.read_csv(file, skiprows=data_start_row)
    df.columns = [c.strip().replace('"', '') for c in df.columns]
    
    # 3. Add the name we found at the top to every row
    df['Player'] = athlete_name
    df['Timestamp'] = pd.to_datetime(df['Date'], errors='coerce')
    return df

# --- UPLOAD SECTION ---
st.header("1. Upload Files")
files = st.file_uploader("Upload Blast & Full Swing CSVs", accept_multiple_files=True)

if files:
    processed_dfs = []
    for f in files:
        # Check first line to see if it's Blast or Full Swing
        f.seek(0)
        first_bits = f.read(100).decode('utf-8', errors='ignore')
        f.seek(0)
        
        if "PitchNo" in first_bits or "Batter" in first_bits:
            df = load_full_swing(f)
            if df is not None:
                st.success(f"✅ Full Swing Loaded: {df['Player'].iloc[0]}")
                processed_dfs.append(df)
        elif "Blast Motion" in first_bits or "Metrics" in first_bits:
            df = load_blast(f)
            if df is not None:
                st.success(f"✅ Blast Motion Loaded: {df['Player'].iloc[0]}")
                processed_dfs.append(df)

    if st.button("Link Data & Build Dashboard"):
        # Separate the two types
        fs_only = [d for d in processed_dfs if 'PitchNo' in d.columns]
        blast_only = [d for d in processed_dfs if 'Equipment' in d.columns]
        
        if fs_only and blast_only:
            fs_master = pd.concat(fs_only).sort_values('Timestamp')
            blast_master = pd.concat(blast_only).sort_values('Timestamp')
            
            # THE FUZZY MERGE (10 second window)
            # This matches the 'Batter' from FS to the name extracted from Blast row 0
            linked = pd.merge_asof(
                fs_master, 
                blast_master[['Timestamp', 'Player', 'Bat Speed (mph)', 'Rotational Acceleration (g)', 'Attack Angle (deg)']], 
                on='Timestamp', 
                by='Player', 
                direction='nearest', 
                tolerance=pd.Timedelta('10s')
            )
            
            # --- THE TRENTON WHEAT ANALYTICS ---
            st.header("2. Trenton Wheat Dashboard")
            
            linked['ExitSpeed'] = pd.to_numeric(linked['ExitSpeed'], errors='coerce')
            linked['Angle'] = pd.to_numeric(linked['Angle'], errors='coerce')
            linked['SmashFactor'] = pd.to_numeric(linked['SmashFactor'], errors='coerce')
            
            # Identify hardest 12.5% of hits
            hits = linked[linked['ExitSpeed'] > 0].sort_values('ExitSpeed', ascending=False)
            num_8th = max(1, int(len(hits) * 0.125))
            top_8th = hits.head(num_8th)
            
            # Create Results Row
            row = {
                "Athlete": linked['Player'].iloc[0],
                "BS Avg": linked['Bat Speed (mph)'].mean(),
                "BS Max": linked['Bat Speed (mph)'].max(),
                "BS 1/8th": top_8th['Bat Speed (mph)'].mean(),
                "RA 1/8th": top_8th['Rotational Acceleration (g)'].mean(),
                "EV Max": linked['ExitSpeed'].max(),
                "EV 1/8th": top_8th['ExitSpeed'].mean(),
                "SF 1/8th": top_8th['SmashFactor'].mean(),
                "Burners %": (len(top_8th[(top_8th['Angle'] >= -1) & (top_8th['Angle'] <= 9.9)]) / len(top_8th) * 100),
                "Ropes %": (len(top_8th[(top_8th['Angle'] >= 10) & (top_8th['Angle'] <= 20)]) / len(top_8th) * 100),
                "Bombs %": (len(top_8th[(top_8th['Angle'] >= 21) & (top_8th['Angle'] <= 31)]) / len(top_8th) * 100),
            }
            
            st.table(pd.DataFrame([row]).style.format(precision=1))
            st.session_state.master_df = linked
        else:
            st.error("Need both file types for the same athlete name to link.")
