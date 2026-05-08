import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="Fast RBI Athlete Dashboard", layout="wide")
st.title("⚾ Fast RBI Data Assistant")

# --- THE HEADER HUNTER (The Fix for your ParserError) ---
def find_the_real_data(uploaded_file):
    # Read the file as raw text first
    raw_content = uploaded_file.read().decode('utf-8', errors='ignore')
    lines = raw_content.splitlines()
    
    # We are looking for the row that contains "Date" and either "Equipment" or "PitchNo"
    header_row_index = -1
    file_type = "Unknown"
    
    for i, line in enumerate(lines):
        # Clean up the line for checking
        clean_line = line.replace('"', '').strip()
        
        # Check for Blast Motion Headers
        if "Date" in clean_line and "Equipment" in clean_line:
            header_row_index = i
            file_type = "Blast"
            break
        # Check for Full Swing Headers
        if "PitchNo" in clean_line and "Date" in clean_line:
            header_row_index = i
            file_type = "FullSwing"
            break
            
    if header_row_index == -1:
        return None, None

    # Now read the CSV starting from that specific row
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, skiprows=header_row_index)
    
    # Clean up column names
    df.columns = [c.strip().replace('"', '') for c in df.columns]
    
    # Standardize Names
    if file_type == "FullSwing" and "Batter" in df.columns:
        df = df.rename(columns={"Batter": "Athlete"})
    
    return df, file_type

# --- SIDEBAR ---
st.sidebar.header("Athlete Settings")
manual_name = st.sidebar.text_input("Name for Blast Files:", "Leo Echevarria")

# --- UPLOAD ---
st.header("1. Upload CSV Files")
uploaded_files = st.file_uploader("Upload Blast or Full Swing CSVs", accept_multiple_files=True)

all_data = []

if uploaded_files:
    for f in uploaded_files:
        df, f_type = find_the_real_data(f)
        
        if df is not None:
            # If Blast file has no name, use the sidebar name
            if f_type == "Blast" and ("Athlete" not in df.columns or df["Athlete"].isnull().all()):
                df["Athlete"] = manual_name
            
            # Create a uniform Timestamp
            if f_type == "FullSwing":
                df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
            else:
                df['Timestamp'] = pd.to_datetime(df['Date'], errors='coerce')
            
            all_data.append(df)
            st.success(f"✅ Successfully read {f_type} file: {f.name}")
        else:
            st.error(f"❌ Could not find the data table in {f.name}. Make sure 'Date' is in the header row.")

# --- DASHBOARD ---
if all_data:
    st.divider()
    master_df = pd.concat(all_data, ignore_index=True)
    
    # Filter by Athlete
    athlete_list = master_df['Athlete'].unique()
    selected_athlete = st.selectbox("Select Athlete Profile", athlete_list)
    
    athlete_df = master_df[master_df['Athlete'] == selected_athlete].copy()
    
    # --- MATH ENGINE ---
    st.header(f"📊 Dashboard: {selected_athlete}")
    
    # Convert numbers
    athlete_df['ExitSpeed'] = pd.to_numeric(athlete_df['ExitSpeed'], errors='coerce')
    athlete_df['Angle'] = pd.to_numeric(athlete_df['Angle'], errors='coerce')
    
    # Find Top 12.5% (1/8th) of hits by Exit Velocity
    hard_hits = athlete_df[athlete_df['ExitSpeed'] > 0].sort_values('ExitSpeed', ascending=False)
    num_8th = max(1, int(len(hard_hits) * 0.125))
    top_8th = hard_hits.head(num_8th)
    
    if not top_8th.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Top EV Avg", f"{top_8th['ExitSpeed'].mean():.1f} mph")
        col2.metric("Max EV", f"{athlete_df['ExitSpeed'].max():.1f} mph")
        
        # Hit Classification
        burners = len(top_8th[(top_8th['Angle'] >= -1) & (top_8th['Angle'] <= 9.9)])
        st.write(f"**Top 1/8th Breakdown:** {burners} Burners found in hard hits.")
        
        st.dataframe(top_8th[['Timestamp', 'ExitSpeed', 'Angle', 'Direction']])
    else:
        st.info("No hits with Exit Velocity found for this athlete.")
