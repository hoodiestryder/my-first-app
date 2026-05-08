import streamlit as st
import pandas as pd
import numpy as np

# --- SETUP ---
st.set_page_config(page_title="Fast RBI Pro Dashboard", layout="wide")
st.title("⚾ Fast RBI Performance Dashboard")

# --- THE DATA HUNTER ---
def load_and_clean(file):
    # Read the file as text to find the header row
    content = file.read().decode('utf-8', errors='ignore')
    lines = content.splitlines()
    file.seek(0)
    
    # 1. Try to find the header row by looking for "Date"
    header_row = -1
    for i, line in enumerate(lines):
        if "Date" in line:
            header_row = i
            break
            
    if header_row == -1:
        st.error(f"Could not find a 'Date' column in {file.name}")
        return None
    
    # 2. Read the CSV from that row
    df = pd.read_csv(file, skiprows=header_row, on_bad_lines='skip')
    df.columns = [c.strip().replace('"', '') for c in df.columns]
    
    # 3. Clean up the Timestamps
    if 'Time' in df.columns:
        df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
    else:
        df['Timestamp'] = pd.to_datetime(df['Date'], errors='coerce')
    
    return df.dropna(subset=['Timestamp'])

# --- SIDEBAR ---
st.sidebar.header("Athlete Profile")
# We will use this name for EVERY file uploaded to ensure they link
force_name = st.sidebar.text_input("Athlete Name:", "Trenton Wheat")
weight = st.sidebar.number_input("Weight (lbs):", value=140.0)

# --- UPLOAD ---
st.header("1. Upload Files")
uploaded_files = st.file_uploader("Upload Blast and Full Swing CSVs", accept_multiple_files=True)

if uploaded_files:
    all_swings = []
    
    for f in uploaded_files:
        df = load_and_clean(f)
        if df is not None:
            # FORCE the name to match the sidebar
            df['Athlete'] = force_name
            all_swings.append(df)
            st.success(f"✅ Loaded {f.name} for {force_name}")

    if len(all_swings) >= 1:
        # Combine everything
        master = pd.concat(all_swings, ignore_index=True)
        
        # Split into Blast and Full Swing
        # Full Swing has 'ExitSpeed' or 'PitchNo'
        fs_df = master[master['ExitSpeed'].notnull()] if 'ExitSpeed' in master.columns else pd.DataFrame()
        # Blast has 'Rotational Acceleration (g)'
        blast_df = master[master['Rotational Acceleration (g)'].notnull()] if 'Rotational Acceleration (g)' in master.columns else pd.DataFrame()
        
        # --- LINKING ---
        if not fs_df.empty and not blast_df.empty:
            st.info("Linking Swing Mechanics to Ball Flight...")
            fs_df = fs_df.sort_values('Timestamp')
            blast_df = blast_df.sort_values('Timestamp')
            
            final_df = pd.merge_asof(
                fs_df, 
                blast_df[['Timestamp', 'Athlete', 'Bat Speed (mph)', 'Rotational Acceleration (g)', 'Attack Angle (deg)']],
                on='Timestamp', by='Athlete', direction='nearest', tolerance=pd.Timedelta('10s')
            )
        else:
            final_df = master

        # --- THE TRENTON WHEAT TABLE ---
        st.header(f"2. {force_name}'s Performance Table")
        
        # Ensure numbers are numbers
        final_df['ExitSpeed'] = pd.to_numeric(final_df['ExitSpeed'], errors='coerce')
        final_df['Angle'] = pd.to_numeric(final_df['Angle'], errors='coerce')
        final_df['SmashFactor'] = pd.to_numeric(final_df['SmashFactor'], errors='coerce')
        
        # Group by Month
        final_df['Month'] = final_df['Timestamp'].dt.strftime('%b %Y')
        
        report_data = []
        for month in final_df['Month'].unique():
            m_df = final_df[final_df['Month'] == month]
            
            # Top 1/8th EV Logic
            hard_hits = m_df[m_df['ExitSpeed'] > 0].sort_values('ExitSpeed', ascending=False)
            num_8th = max(1, int(len(hard_hits) * 0.125))
            top_8th = hard_hits.head(num_8th)
            
            # Metrics
            bs_col = 'Bat Speed (mph)' if 'Bat Speed (mph)' in m_df.columns else 'BatSpeed'
            
            report_data.append({
                "Month": month,
                "EV Max": m_df['ExitSpeed'].max(),
                "EV 1/8th": top_8th['ExitSpeed'].mean() if not top_8th.empty else 0,
                "BS 1/8th": top_8th[bs_col].mean() if not top_8th.empty and bs_col in top_8th.columns else 0,
                "RA 1/8th": top_8th['Rotational Acceleration (g)'].mean() if not top_8th.empty and 'Rotational Acceleration (g)' in top_8th.columns else 0,
                "SF 1/8th": top_8th['SmashFactor'].mean() if not top_8th.empty else 0,
                "Burners %": (len(top_8th[(top_8th['Angle'] >= -1) & (top_8th['Angle'] <= 9.9)]) / len(top_8th) * 100) if not top_8th.empty else 0,
                "mph/lbs": m_df['ExitSpeed'].max() / weight if weight > 0 else 0
            })
            
        st.table(pd.DataFrame(report_data).style.format(precision=1))
        
        # DEBUG: Let coach see everything
        with st.expander("View Linked Swings"):
            st.dataframe(final_df)
