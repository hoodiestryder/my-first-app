import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import numpy as np
from datetime import datetime

# --- PAGE SETUP ---
st.set_page_config(page_title="Fast RBI Pro Analytics", layout="wide")

# --- CONNECT TO GOOGLE SHEETS ---
# This requires your "Secrets" to be set up in the Streamlit Dashboard!
conn = st.connection("gsheets", type=GSheetsConnection)

def get_google_data():
    try:
        master = conn.read(worksheet="Master")
        checks = conn.read(worksheet="Checkins")
        return pd.DataFrame(master), pd.DataFrame(checks)
    except:
        return pd.DataFrame(), pd.DataFrame()

# --- ROBUST DATA CLEANING ---
def clean_full_swing(file):
    df = pd.read_csv(file)
    df.columns = [c.strip().replace('"', '') for c in df.columns]
    # Standardize Name
    if 'Batter' in df.columns:
        df = df.rename(columns={'Batter': 'Athlete'})
    # Standardize Time - Full Swing is usually MM/DD/YY
    df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
    return df.dropna(subset=['Timestamp'])

def clean_blast(file, manual_name):
    # Blast files vary. We look for the row that starts the data table.
    # We skip the copyright/email/academy rows automatically.
    df = pd.read_csv(file, skiprows=8) 
    df.columns = [c.strip().replace('"', '') for c in df.columns]
    
    # If the file doesn't have an Athlete column, use the name from the sidebar
    if 'Athlete' not in df.columns:
        df['Athlete'] = manual_name
    
    df['Timestamp'] = pd.to_datetime(df['Date'], errors='coerce')
    return df.dropna(subset=['Timestamp'])

# --- TRENTON WHEAT MATH ENGINE ---
def calculate_trenton_metrics(df):
    """Anchor = ExitSpeed. Top 12.5% logic."""
    df['ExitSpeed'] = pd.to_numeric(df['ExitSpeed'], errors='coerce')
    hits = df[df['ExitSpeed'] > 0].copy()
    
    if hits.empty:
        return None
    
    # Sort by EV to find the hardest 12.5% of hits
    hits = hits.sort_values('ExitSpeed', ascending=False)
    num_top = max(1, int(len(hits) * 0.125))
    top_8th = hits.head(num_top)

    # Determine which Bat Speed column exists
    bs_col = 'Bat Speed (mph)' if 'Bat Speed (mph)' in top_8th.columns else 'BatSpeed'
    
    return {
        "BS Avg": df[bs_col].mean() if bs_col in df.columns else 0,
        "BS Max": df[bs_col].max() if bs_col in df.columns else 0,
        "BS 1/8th": top_8th[bs_col].mean() if bs_col in top_8th.columns else 0,
        "RA 1/8th": top_8th['Rotational Acceleration (g)'].mean() if 'Rotational Acceleration (g)' in top_8th.columns else 0,
        "EV Max": df['ExitSpeed'].max(),
        "EV 1/8th": top_8th['ExitSpeed'].mean(),
        "LA Avg": top_8th['Angle'].mean() if 'Angle' in top_8th.columns else 0,
        "HLA Avg": top_8th['Direction'].mean() if 'Direction' in top_8th.columns else 0,
        "SF 1/8th": top_8th['SmashFactor'].mean() if 'SmashFactor' in top_8th.columns else 0,
        "Burn %": (len(top_8th[(top_8th['Angle'] >= -1) & (top_8th['Angle'] <= 9.9)]) / len(top_8th) * 100),
        "Ropes %": (len(top_8th[(top_8th['Angle'] >= 10) & (top_8th['Angle'] <= 20)]) / len(top_8th) * 100),
        "Bombs %": (len(top_8th[(top_8th['Angle'] >= 21) & (top_8th['Angle'] <= 31)]) / len(top_8th) * 100),
        "Top_Hits_Count": len(top_8th)
    }

# --- APP UI ---
st.title("⚾ Fast RBI Performance Dashboard")
master_df, checkins_df = get_google_data()

# Sidebar Setup
st.sidebar.header("Athlete Control")
athlete_name = st.sidebar.text_input("Current Athlete Name", "Andrew Pereira")

# --- TAB 1: UPLOAD & SYNC ---
st.header("1. Upload & Sync Data")
col1, col2 = st.columns(2)

with col1:
    st.subheader("Check-In")
    with st.form("checkin"):
        w = st.number_input("Weight (lbs)", value=140.0)
        h = st.number_input("Height (in)", value=66.0)
        if st.form_submit_button("Save Physicals"):
            new_c = pd.DataFrame([{"Athlete": athlete_name, "Date": str(pd.Timestamp.now().date()), "Weight": w, "Height": h}])
            updated_c = pd.concat([checkins_df, new_c])
            conn.update(worksheet="Checkins", data=updated_c)
            st.success("Physicals saved to Google Sheets!")

with col2:
    st.subheader("Upload Session")
    b_file = st.file_uploader("Blast Motion CSV")
    fs_file = st.file_uploader("Full Swing CSV")
    
    if st.button("Link and Save to Master"):
        if b_file and fs_file:
            b_df = clean_blast(b_file, athlete_name)
            fs_df = clean_full_swing(fs_file)
            
            # Fuzzy Merge (7 second window)
            b_df = b_df.sort_values('Timestamp')
            fs_df = fs_df.sort_values('Timestamp')
            merged = pd.merge_asof(fs_df, b_df[['Timestamp', 'Bat Speed (mph)', 'Rotational Acceleration (g)', 'Attack Angle (deg)']], 
                                 on='Timestamp', direction='nearest', tolerance=pd.Timedelta('7s'))
            
            # Save to Google
            updated_master = pd.concat([master_df, merged], ignore_index=True)
            conn.update(worksheet="Master", data=updated_master)
            st.success("Session successfully merged and saved to Google Sheets!")

# --- TAB 2: DASHBOARD ---
st.divider()
st.header(f"2. {athlete_name}'s Profile")

if not master_df.empty and athlete_name in master_df['Athlete'].values:
    # Filter for selected athlete
    a_df = master_df[master_df['Athlete'] == athlete_name].copy()
    a_df['Timestamp'] = pd.to_datetime(a_df['Timestamp'])
    a_df['MonthYear'] = a_df['Timestamp'].dt.strftime('%b %Y')
    
    # Process Monthly Table
    rows = []
    for month in a_df['MonthYear'].unique():
        m_df = a_df[a_df['MonthYear'] == month]
        metrics = calculate_trenton_metrics(m_df)
        
        if metrics:
            metrics['Date Range'] = month
            rows.append(metrics)
            
    if rows:
        display_df = pd.DataFrame(rows)
        # Organize columns to match your Trenton Wheat request
        cols = ["Date Range", "BS Avg", "BS Max", "BS 1/8th", "RA 1/8th", "EV Max", "EV 1/8th", "LA Avg", "HLA Avg", "Burn %", "Ropes %", "Bombs %", "SF 1/8th"]
        st.dataframe(display_df[cols].style.format(precision=1), use_container_width=True)
    else:
        st.error("Data exists but top 1/8th calculations failed. Check if ExitSpeed exists.")
else:
    st.info("No data found for this athlete in the Master Sheet. Please upload files above.")
