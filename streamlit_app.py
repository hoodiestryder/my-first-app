import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import numpy as np

# --- PAGE SETUP ---
st.set_page_config(page_title="Fast RBI Athlete Pro Dashboard", layout="wide")

# --- CONNECT TO GOOGLE SHEETS ---
# This requires you to have Phase 2 & 3 (Secrets) set up in Streamlit Cloud!
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        master = conn.read(worksheet="Master")
        checks = conn.read(worksheet="Checkins")
        return master, checks
    except:
        return pd.DataFrame(), pd.DataFrame()

# --- DATA CLEANING ENGINES ---
def clean_full_swing(file):
    df = pd.read_csv(file)
    df.columns = [c.strip().replace('"', '') for c in df.columns]
    # Rename Batter to Athlete
    if 'Batter' in df.columns:
        df = df.rename(columns={'Batter': 'Athlete'})
    # Combine Date and Time
    df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
    return df

def clean_blast(file):
    # Get Name from Row 0 (The "Metrics - Leo Echevarria" line)
    raw_header = pd.read_csv(file, nrows=0).columns[0]
    # Extract name between the first two dashes
    try:
        athlete_name = raw_header.split('-')[1].strip()
    except:
        athlete_name = "Unknown Athlete"
        
    # Now read the actual data starting at row 9
    file.seek(0)
    df = pd.read_csv(file, skiprows=8)
    df.columns = [c.strip().replace('"', '') for c in df.columns]
    df['Athlete'] = athlete_name
    df['Timestamp'] = pd.to_datetime(df['Date'])
    return df

# --- THE TRENTON WHEAT ANALYTICS ---
def get_1_8th_metrics(df):
    df['ExitSpeed'] = pd.to_numeric(df['ExitSpeed'], errors='coerce')
    hits = df[df['ExitSpeed'] > 0].dropna(subset=['ExitSpeed'])
    if hits.empty: return None
    
    hits = hits.sort_values('ExitSpeed', ascending=False)
    num_top = max(1, int(len(hits) * 0.125))
    top_8th = hits.head(num_top)
    
    # Logic: Average mechanics based on the hardest hits
    return {
        "BS_18": top_8th['BatSpeed'].mean() if 'BatSpeed' in top_8th.columns else top_8th['Bat Speed (mph)'].mean(),
        "EV_18": top_8th['ExitSpeed'].mean(),
        "SF_18": top_8th['SmashFactor'].mean() if 'SmashFactor' in top_8th.columns else 0,
        "LA_18": top_8th['Angle'].mean() if 'Angle' in top_8th.columns else 0,
        "HLA_18": top_8th['Direction'].mean() if 'Direction' in top_8th.columns else 0,
        "Top_Hits": top_8th
    }

# --- UI NAVIGATION ---
st.title("⚾ Fast RBI Analytics Dashboard")
menu = st.sidebar.selectbox("Menu", ["Athlete Dashboard", "Check-In / Upload"])

master_df, checkins_df = load_data()

if menu == "Check-In / Upload":
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📍 Physical Check-In")
        with st.form("checkin"):
            name = st.text_input("Athlete Name")
            w = st.number_input("Weight (lbs)", 100, 250, 140)
            h = st.number_input("Height (in)", 40, 80, 66)
            if st.form_submit_button("Submit to Google Sheets"):
                new_c = pd.DataFrame([{"Athlete": name, "Date": str(pd.Timestamp.now().date()), "Weight": w, "Height": h}])
                updated_c = pd.concat([checkins_df, new_c])
                conn.update(worksheet="Checkins", data=updated_c)
                st.success("Check-in Saved!")

    with col2:
        st.subheader("Upload Session")
        b_file = st.file_uploader("Blast CSV")
        fs_file = st.file_uploader("Full Swing CSV")
        if st.button("Merge & Save to Google"):
            if b_file and fs_file:
                b_df = clean_blast(b_file)
                fs_df = clean_full_swing(fs_file)
                
                # FUZZY MERGE (7 second tolerance)
                b_df = b_df.sort_values('Timestamp')
                fs_df = fs_df.sort_values('Timestamp')
                merged = pd.merge_asof(fs_df, b_df[['Timestamp', 'Bat Speed (mph)', 'Rotational Acceleration (g)', 'Attack Angle (deg)']], 
                                     on='Timestamp', direction='nearest', tolerance=pd.Timedelta('7s'))
                
                updated_m = pd.concat([master_df, merged])
                conn.update(worksheet="Master", data=updated_m)
                st.success("Session Saved to Google Sheets!")

elif menu == "Athlete Dashboard":
    athlete = st.sidebar.selectbox("Select Athlete", master_df['Athlete'].unique() if not master_df.empty else ["No Data"])
    
    if not master_df.empty:
        a_df = master_df[master_df['Athlete'] == athlete].copy()
        a_df['Timestamp'] = pd.to_datetime(a_df['Timestamp'])
        a_df['Month'] = a_df['Timestamp'].dt.strftime('%b %Y')
        
        # Monthly Logic
        report = []
        for month in a_df['Month'].unique():
            m_df = a_df[a_df['Month'] == month]
            stats = get_1_8th_metrics(m_df)
            
            if stats:
                top_hits = stats['Top_Hits']
                report.append({
                    "Month": month,
                    "EV Max": m_df['ExitSpeed'].max(),
                    "EV 1/8th": stats['EV_18'],
                    "BS 1/8th": stats['BS_18'],
                    "SF 1/8th": stats['SF_18'],
                    "LA Avg": stats['LA_18'],
                    "Burners %": (len(top_hits[(top_hits['Angle'] >= -1) & (top_hits['Angle'] <= 9.9)]) / len(top_hits) * 100),
                    "Ropes %": (len(top_hits[(top_hits['Angle'] >= 10) & (top_hits['Angle'] <= 20)]) / len(top_hits) * 100),
                    "Bombs %": (len(top_hits[(top_hits['Angle'] >= 21) & (top_hits['Angle'] <= 31)]) / len(top_hits) * 100),
                })
        
        st.write(f"### Results for {athlete}")
        st.dataframe(pd.DataFrame(report).style.format(precision=1))
