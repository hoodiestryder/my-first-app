import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Setup the Page
st.set_page_config(page_title="Athlete Performance App", layout="wide")

st.title("⚾ Athlete Data Assistant")
st.write("Upload your CSVs below to update athlete profiles.")

# 2. Create a place to store data (Temporarily)
if 'all_data' not in st.session_state:
    st.session_state.all_data = pd.DataFrame()

# 3. The Sidebar Menu
menu = st.sidebar.selectbox("Go To", ["Upload Files", "Athlete Profiles"])

# --- PAGE 1: UPLOADING ---
if menu == "Upload Files":
    st.header("Upload New Data")
    
    source = st.radio("What are you uploading?", ["Full Swing", "Blast Motion"])
    uploaded_file = st.file_uploader("Upload CSV", type="csv")

    if uploaded_file is not None:
        # Read the file
        df = pd.read_csv(uploaded_file)
        
        # Clean up column names (remove spaces)
        df.columns = [c.strip() for c in df.columns]
        
        st.write("I found these columns in your file:", df.columns.tolist())
        st.write("Preview:", df.head())

        if st.button("Add to Database"):
            # Add a column to track where it came from
            df['Source'] = source
            # Combine it with our master list
            st.session_state.all_data = pd.concat([st.session_state.all_data, df], ignore_index=True)
            st.success("Successfully added! Go to 'Athlete Profiles' to see it.")

# --- PAGE 2: ATHLETE PROFILES ---
elif menu == "Athlete Profiles":
    if st.session_state.all_data.empty:
        st.warning("No data found. Please upload a CSV first.")
    else:
        df = st.session_state.all_data
        
        # Try to find the name column automatically
        # We will look for "Player", "Athlete", or "Name"
        name_col = ""
        for col in ["Player", "Athlete", "Name", "player_name"]:
            if col in df.columns:
                name_col = col
                break
        
        if name_col == "":
            st.error("I couldn't find a 'Name' or 'Player' column. Check your CSV headers!")
        else:
            # Filter by Athlete
            athletes = df[name_col].unique()
            selected_athlete = st.sidebar.selectbox("Choose Athlete", athletes)
            
            athlete_df = df[df[name_col] == selected_athlete]
            
            st.header(f"Stats for {selected_athlete}")
            
            # Show a simple chart of the first numeric column we find
            numeric_cols = athlete_df.select_dtypes(include=['float64', 'int64']).columns
            if len(numeric_cols) > 0:
                metric = st.selectbox("Select Metric to Chart", numeric_cols)
                fig = px.scatter(athlete_df, y=metric, title=f"{metric} History")
                st.plotly_chart(fig)
            
            st.subheader("Raw Data")
            st.write(athlete_df)
