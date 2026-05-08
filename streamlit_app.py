import streamlit as st
import pandas as pd

st.title("🔍 Data Diagnostic Scanner")

uploaded_file = st.file_uploader("Upload any CSV (Blast or Full Swing)")

if uploaded_file:
    st.write("### Raw File Analysis")
    
    # Check the first 15 lines of the file as raw text
    lines = uploaded_file.readlines()
    st.write("First 5 lines of the file (Raw Text):")
    for i in range(min(5, len(lines))):
        st.text(lines[i])
    
    # Try to read it normally
    try:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file)
        st.write("---")
        st.success("Successfully read with NO skips!")
        st.write("Found these columns:", df.columns.tolist())
        st.write("Preview of first 2 rows:", df.head(2))
    except Exception as e:
        st.error(f"Normal read failed: {e}")
        
    # Try reading with Blast Skip (8 rows)
    try:
        uploaded_file.seek(0)
        df_skip = pd.read_csv(uploaded_file, skiprows=8)
        st.write("---")
        st.success("Successfully read with 8-ROW SKIP!")
        st.write("Found these columns:", df_skip.columns.tolist())
        st.write("Preview of first 2 rows:", df_skip.head(2))
    except Exception as e:
        st.warning(f"Skip-8 read failed: {e}")
