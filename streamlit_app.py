import streamlit as st
import pandas as pd
import numpy as np
from io import StringIO

st.set_page_config(page_title="Fast RBI - Stage 1", layout="wide")
st.title("⚾ Fast RBI Performance Reset")
st.info("Goal: Get the Trenton Wheat table to appear on screen. (Google Sheets is disabled for this test)")

# --- THE BULLETPROOF LOADER ---
def smart_load(file):
    # Read the whole file as text to find the start
    content = file.read().decode('utf-8', errors='ignore')
    lines = content.splitlines()
    
    # 1. Look for Full Swing (has PitchNo)
    if "PitchNo" in content:
        file.seek(0)
        df = pd.read_csv(file)
        df.columns = [c.strip().replace('"', '') for c in df.columns]
        if 'Batter' in df.columns:
            df = df.rename(columns={'Batter': 'Athlete'})
        df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
        return df, "FullSwing"

    # 2. Look for Blast (find the row where "Date" starts)
    data_start = -1
    for i, line in enumerate(lines):
        if "Date" in line and "Equipment" in line:
            data_start = i
            break
    
    if data_start != -1:
        file.seek(0)
        df = pd.read_csv(file, skiprows=data_start)
        df.columns = [c.strip().replace('"', '') for c in df.columns]
        df['Timestamp'] = pd.to_datetime(df['Date'], errors='coerce')
        # Try to find name in the very first line if possible
        if "Metrics" in lines[0]:
            try:
                df['Athlete'] = lines[0].split('-')[1].strip()
            except:
                df['Athlete'] = "Unknown"
        return df, "Blast"

    return None, None

# --- SIDEBAR CONTROL ---
st.sidebar.header("Manual Controls")
manual_name = st.sidebar.text_input("If name is missing, use:", "Trenton Wheat")
weight = st.sidebar.number_input("Weight (lbs)", value=140.0)

# --- UPLOAD ---
files = st.file_uploader("Upload CSVs", accept_multiple_files=True)

if files:
    all_swings = []
    
    for f in files:
        df, f_type = smart_load(f)
        if df is not None:
            if 'Athlete' not in df.columns or df['Athlete'].iloc[0] == "Unknown":
                df['Athlete'] = manual_name
            all_swings.append(df)
            st.success(f"Loaded {f_type}: {f.name}")

    if len(all_swings) >= 1:
        # Combine all data
        master = pd.concat(all_swings, ignore_index=True)
        
        # FUZZY LINKING (If both types are present)
        fs_data = master[master['PitchNo'].notnull()] if 'PitchNo' in master.columns else pd.DataFrame()
        blast_data = master[master['Equipment'].notnull()] if 'Equipment' in master.columns else pd.DataFrame()
        
        if not fs_data.empty and not blast_data.empty:
            st.write("### Linking Blast & Full Swing...")
            fs_data = fs_data.sort_values('Timestamp')
            blast_data = blast_data.sort_values('Timestamp')
            
            final_df = pd.merge_asof(
                fs_data, 
                blast_data[['Timestamp', 'Athlete', 'Bat Speed (mph)', 'Rotational Acceleration (g)', 'Attack Angle (deg)']],
                on='Timestamp', by='Athlete', direction='nearest', tolerance=pd.Timedelta('10s')
            )
        else:
            final_df = master

        # --- THE TRENTON WHEAT MATH ---
        st.header(f"📊 {manual_name} - Monthly Report")
        
        # Ensure numbers are numbers
        final_df['ExitSpeed'] = pd.to_numeric(final_df['ExitSpeed'], errors='coerce')
        final_df['Angle'] = pd.to_numeric(final_df['Angle'], errors='coerce')
        
        final_df['Month'] = final_df['Timestamp'].dt.strftime('%b %Y')
        
        monthly_table = []
        for month in final_df['Month'].unique():
            m_df = final_df[final_df['Month'] == month]
            
            # Top 1/8th EV Logic
            hard_hits = m_df[m_df['ExitSpeed'] > 0].sort_values('ExitSpeed', ascending=False)
            num_8th = max(1, int(len(hard_hits) * 0.125))
            top_8th = hard_hits.head(num_8th)
            
            # Whiff Calc
            # Full Swing uses 'BatSpeed', Blast uses 'Bat Speed (mph)'
            bs_col = 'Bat Speed (mph)' if 'Bat Speed (mph)' in m_df.columns else 'BatSpeed'
            swings = m_df[m_df[bs_col] > 0]
            whiffs = swings[(swings['ExitSpeed'].isna()) | (swings['ExitSpeed'] == 0)]
            whiff_pct = (len(whiffs)/len(swings)*100) if len(swings)>0 else 0

            monthly_table.append({
                "Month": month,
                "EV Max": m_df['ExitSpeed'].max(),
                "EV 1/8th": top_8th['ExitSpeed'].mean() if not top_8th.empty else 0,
                "BS 1/8th": top_8th[bs_col].mean() if not top_8th.empty else 0,
                "Burners %": (len(top_8th[(top_8th['Angle'] >= -1) & (top_8th['Angle'] <= 9.9)]) / len(top_8th) * 100) if not top_8th.empty else 0,
                "Whiff %": f"{whiff_pct:.1f}%",
                "mph/lbs": m_df['ExitSpeed'].max() / weight if weight > 0 else 0
            })
            
        st.table(pd.DataFrame(monthly_table).style.format(precision=1))
        
        # Debugging: Let coach see the raw merged data
        with st.expander("Show Raw Merged Data"):
            st.write(final_df)
