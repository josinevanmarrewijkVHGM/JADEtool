import streamlit as st
import pandas as pd
from utils import load_data, calculate_output

st.title("Water Temperature & Discharge Analysis Tool")

# File upload

temp_file = st.file_uploader("Upload Water Temperature CSV", type="csv")
discharge_file = st.file_uploader("Upload Discharge CSV", type="csv")

# Parameter input

deltaT = st.slider("Temperature difference (°K)", min_value=0, max_value=12, value=10)
maintenance = st.number_input("Maintenance factor (onderhoud)", min_value=0.0, max_value=1.0, value=0.2, step=0.01)

min_dif = st.selectbox("Minimum difference (min_dif)", options=[2, 3, 4], index=1)

use_monthly_loz = st.checkbox("Set minimum loz temperature per month?", value=True)

if use_monthly_loz:
    min_loz_month = []
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for i, month in enumerate(months):
        val = st.number_input(f"Minimum loz temperature for {month}", min_value=0, max_value=40, value=20 if month not in ["May", "Jun", "Jul", "Aug", "Sep"] else 12)
        min_loz_month.append(val)
else:
    loz_temp = st.number_input("Minimum loz temperature for the whole year", min_value=0, max_value=40, value=20)
    min_loz_month = [loz_temp] * 12


# Run analysis
if temp_file and discharge_file:
    temp_df, discharge_df = load_data(temp_file, discharge_file)
    result_df = calculate_output(temp_df, discharge_df, deltaT)

    st.subheader("Filtered & Merged Output")
    st.dataframe(result_df)

    st.subheader("Temperature Distribution")
    st.bar_chart(temp_df['temperature'])
