import streamlit as st
import pandas as pd
from utils import load_data, calculate_output

st.title("Water Temperature & Discharge Analysis Tool")

# File upload
temp_file = st.file_uploader("Upload Water Temperature CSV", type="csv")
discharge_file = st.file_uploader("Upload Discharge CSV", type="csv")

# Parameter input
threshold = st.slider("Temperature Threshold (°C)", min_value=0, max_value=30, value=10)

# Run analysis
if temp_file and discharge_file:
    temp_df, discharge_df = load_data(temp_file, discharge_file)
    result_df = calculate_output(temp_df, discharge_df, threshold)

    st.subheader("Filtered & Merged Output")
    st.dataframe(result_df)

    st.subheader("Temperature Distribution")
    st.bar_chart(temp_df['temperature'])
