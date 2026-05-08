import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- SETUP ---
st.set_page_config(page_title="Fast RBI Diagnostic App", layout="wide")
st.title("⚾ Fast RBI Data Diagnostic")

# --- RESILIENT LOADER ---
def load_csv(file):
    """Try to find the data regardless of header rows."""
    try:
        # Try reading it normally first (Full Swing style)
        file.seek(0)
        df = pd.read_csv(file)
        if 'Date' in df.columns and ('PitchNo' in df.columns or 'Batter' in df.columns):
            st.success(f"✅ Full Swing file detected: {file.name}")
            return df, "FullSwing"
        
        # If that fails, scan for the line where "Date" starts (Blast style)
        file.seek(0)
        lines = file.readlines()
        for i, line in enumerate(lines):
            decoded_line = line.decode('utf-8')
            if "Date" in decoded_line and "Equipment" in decoded_line:
                file.seek(0)
                df = pd.read_csv(file, skiprows=i)
                st.success(f"✅ Blast Motion file detected: {file.name}")
                return df, "Blast"
    except Exception as e:
        st.error(f"❌ Error reading {file.name}: {e}")
    return None, None

# --- SIDEBAR ---
st.sidebar.header("1. Identify Athlete")
# MUST MATCH THE CSV NAME EXACTLY
target_name = st.sidebar.text_input("Athlete Name in CSV", "Andrew Pereira")

# --- UPLOAD ---
st.header("2. Upload Your Files")
st.info("Upload one Full Swing file and one Blast file for the same athlete.")
files = st.file_uploader("Upload CSVs", accept_multiple_files=True)

all_data = []

if files:
    for f in files:
        df, f_type = load_csv(f)
        if df is not None:
            # Clean column names
            df.columns = [c.strip().replace('"', '') for c in df.columns]
            
            # Standardize Name
            if f_type == "FullSwing":
                df = df.rename(columns={'Batter': 'Player'})
            else:
                df['Player'] = target_name # Blast individual exports need manual name
            
            # Standardize Time
            if f_type == "FullSwing":
                df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
            else:
                df['Timestamp'] = pd.to_datetime(df['Date'], errors='coerce')
            
            df = df.dropna(subset=['Timestamp'])
            all_data.append(df)

# --- PROCESSING ---
if len(all_data) >= 2:
    st.header("3. Linking Data")
    
    # Separate the lists
    fs_dfs = [d for d in all_data if 'PitchNo' in d.columns]
    blast_dfs = [d for d in all_data if 'Equipment' in d.columns]
    
    if fs_dfs and blast_dfs:
        fs_master = pd.concat(fs_dfs).sort_values('Timestamp')
        blast_master = pd.concat(blast_dfs).sort_values('Timestamp')
        
        # FUZZY MERGE
        linked = pd.merge_asof(
            fs_master, 
            blast_master[['Timestamp', 'Player', 'Bat Speed (mph)', 'Rotational Acceleration (g)', 'Attack Angle (deg)']], 
            on='Timestamp', 
            by='Player', 
            direction='nearest', 
            tolerance=pd.Timedelta('10s') # 10 second window
        )
        
        st.success(f"Successfully matched {len(linked)} swings!")
        
        # --- THE TRENTON WHEAT TABLE ---
        st.header("4. Trenton Wheat Performance Table")
        
        # Ensure numeric
        linked['ExitSpeed'] = pd.to_numeric(linked['ExitSpeed'], errors='coerce')
        linked['Angle'] = pd.to_numeric(linked['Angle'], errors='coerce')
        linked['SmashFactor'] = pd.to_numeric(linked['SmashFactor'], errors='coerce')
        
        # Find Top 1/8th EV
        hard_hits = linked[linked['ExitSpeed'] > 0].sort_values('ExitSpeed', ascending=False)
        num_8th = max(1, int(len(hard_hits) * 0.125))
        top_8th = hard_hits.head(num_8th)
        
        # Create the Row
        row = {
            "Date Range": "Current Session",
            "BS Avg": linked['Bat Speed (mph)'].mean(),
            "BS Max": linked['Bat Speed (mph)'].max(),
            "BS 1/8th": top_8th['Bat Speed (mph)'].mean(),
            "RA 1/8th": top_8th['Rotational Acceleration (g)'].mean(),
            "EV Max": linked['ExitSpeed'].max(),
            "EV 1/8th": top_8th['ExitSpeed'].mean(),
            "LA Avg": top_8th['Angle'].mean(),
            "SF 1/8th": top_8th['SmashFactor'].mean(),
            "Burners %": (len(top_8th[(top_8th['Angle'] >= -1) & (top_8th['Angle'] <= 9.9)]) / len(top_8th) * 100),
            "Ropes %": (len(top_8th[(top_8th['Angle'] >= 10) & (top_8th['Angle'] <= 20)]) / len(top_8th) * 100),
            "Bombs %": (len(top_8th[(top_8th['Angle'] >= 21) & (top_8th['Angle'] <= 31)]) / len(top_8th) * 100),
        }
        
        st.table(pd.DataFrame([row]).style.format(precision=1))
        
        st.subheader("Raw Linked Data (Check for matched rows)")
        st.dataframe(linked)
    else:
        st.error("I need at least one Full Swing file AND one Blast file to create the table.")
