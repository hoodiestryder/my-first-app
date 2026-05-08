import streamlit as st
import pandas as pd
import plotly.express as px

# --- PAGE SETUP ---
st.set_page_config(page_title="Athlete Performance Lab", layout="wide")

st.title("⚾ Athlete Data Assistant")

# --- DATA STORAGE ---
# This keeps the data active while you are using the app
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame()

# --- SIDEBAR ---
st.sidebar.header("Navigation")
page = st.sidebar.radio("Go to:", ["Upload Data", "Athlete Profiles", "Leaderboard"])

# --- HELPER FUNCTION: Clean Blast Data ---
def load_blast(file):
    # Blast has 8 lines of header info before the actual data starts
    df = pd.read_csv(file, skiprows=8)
    df.columns = [c.strip() for c in df.columns]
    # Clean up the Date
    df['Date_Clean'] = pd.to_datetime(df['Date']).dt.date
    # Blast doesn't always have a 'Name' column in individual exports
    # We will add a placeholder if it's missing
    if 'Athlete' not in df.columns:
        df['Athlete'] = "Unknown Athlete"
    return df

# --- HELPER FUNCTION: Clean Full Swing Data ---
def load_fullswing(file):
    df = pd.read_csv(file)
    df.columns = [c.strip() for c in df.columns]
    # Standardize 'Batter' to 'Athlete' so they match
    if 'Batter' in df.columns:
        df = df.rename(columns={'Batter': 'Athlete'})
    df['Date_Clean'] = pd.to_datetime(df['Date']).dt.date
    return df

# --- PAGE 1: UPLOAD ---
if page == "Upload Data":
    st.header("Upload CSV Files")
    
    col1, col2 = st.columns(2)
    
    with col1:
        blast_file = st.file_uploader("Upload Blast Motion (Monthly)", type="csv")
        if blast_file:
            try:
                b_df = load_blast(blast_file)
                st.success("Blast Data Loaded!")
                if st.button("Save Blast Data"):
                    b_df['Source'] = "Blast"
                    st.session_state.master_df = pd.concat([st.session_state.master_df, b_df], ignore_index=True)
            except:
                st.error("Error reading Blast file. Make sure it's the original export.")

    with col2:
        fs_file = st.file_uploader("Upload Full Swing (Daily)", type="csv")
        if fs_file:
            try:
                fs_df = load_fullswing(fs_file)
                st.success("Full Swing Data Loaded!")
                if st.button("Save Full Swing Data"):
                    fs_df['Source'] = "FullSwing"
                    st.session_state.master_df = pd.concat([st.session_state.master_df, fs_df], ignore_index=True)
            except:
                st.error("Error reading Full Swing file.")

# --- PAGE 2: ATHLETE PROFILES ---
elif page == "Athlete Profiles":
    if st.session_state.master_df.empty:
        st.warning("No data found. Please upload files first.")
    else:
        df = st.session_state.master_df
        
        # Athlete Selection
        athlete_list = df['Athlete'].unique()
        selected_athlete = st.sidebar.selectbox("Select Athlete", athlete_list)
        
        athlete_df = df[df['Athlete'] == selected_athlete]
        
        st.header(f"Performance Profile: {selected_athlete}")
        
        # --- METRIC CARDS ---
        c1, c2, c3, c4 = st.columns(4)
        
        # Calculate Averages based on what data is available
        if 'Exit Velocity (mph)' in athlete_df.columns:
            avg_exit = athlete_df['Exit Velocity (mph)'].mean()
            c1.metric("Avg Exit Velocity", f"{avg_exit:.1f} mph")
            
        if 'Bat Speed (mph)' in athlete_df.columns:
            avg_bat = athlete_df['Bat Speed (mph)'].mean()
            c2.metric("Avg Bat Speed", f"{avg_bat:.1f} mph")

        if 'SmashFactor' in athlete_df.columns:
            avg_smash = pd.to_numeric(athlete_df['SmashFactor'], errors='coerce').mean()
            c3.metric("Avg Smash Factor", f"{avg_smash:.2f}")

        if 'Rotational Acceleration (g)' in athlete_df.columns:
            avg_rot = athlete_df['Rotational Acceleration (g)'].mean()
            c4.metric("Avg Rotational Accel", f"{avg_rot:.1f} g")

        # --- CHARTS ---
        st.subheader("Progress Over Time")
        # List all numeric columns for the user to pick a chart
        numeric_cols = athlete_df.select_dtypes(include=['float64', 'int64']).columns
        chart_metric = st.selectbox("Select Metric to View Trend:", numeric_cols)
        
        fig = px.line(athlete_df.sort_values('Date_Clean'), 
                     x='Date_Clean', y=chart_metric, 
                     markers=True, title=f"{chart_metric} Trend")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Raw Session Data")
        st.dataframe(athlete_df)

# --- PAGE 3: LEADERBOARD ---
elif page == "Leaderboard":
    if st.session_state.master_df.empty:
        st.warning("No data found.")
    else:
        st.header("Team Leaderboard")
        metric_choice = st.selectbox("Rank By:", ["Bat Speed (mph)", "Exit Velocity (mph)", "Rotational Acceleration (g)"])
        
        if metric_choice in st.session_state.master_df.columns:
            leaderboard = st.session_state.master_df.groupby("Athlete")[metric_choice].max().sort_values(ascending=False)
            st.table(leaderboard)
        else:
            st.info(f"Not enough data to rank by {metric_choice}")
