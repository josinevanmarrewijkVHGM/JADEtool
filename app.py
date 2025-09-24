import streamlit as st
import pandas as pd
from utils import process_data
import matplotlib.pyplot as plt
from datetime import datetime

st.title("Water Temperature & Discharge Analysis Tool")

# File upload

temp_file = st.file_uploader("Upload Water Temperature CSV", type="csv")
discharge_file = st.file_uploader("Upload Discharge CSV", type="csv")


# Standaardwaarden
default_start = datetime.strptime('01-01-2020', '%d-%m-%Y')
default_end = datetime.strptime('01-01-2025', '%d-%m-%Y')

# Input parameters
start_date = st.date_input("Startdatum", value=default_start)
end_date = st.date_input("Einddatum", value=default_end)

deltaT = st.slider("Temperature difference (°K)", min_value=0, max_value=12, value=10)
maintenance = st.number_input("Maintenance factor (onderhoud)", min_value=0.0, max_value=1.0, value=0.2, step=0.01)
min_dif = st.selectbox("Minimum difference (min_dif)", options=[2, 3, 4], index=1)

use_monthly_loz = st.checkbox("Set minimum loz temperature per month?", value=True)

if use_monthly_loz:
    print('Not integrated yet')
    # min_loz_month = []
    # months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    # for i, month in enumerate(months):
    #     val = st.number_input(
    #         f"Minimum loz temperature for {month}",
    #         min_value=0,
    #         max_value=40,
    #         value=20 if month not in ["May", "Jun", "Jul", "Aug", "Sep"] else 12
    #     )
    #     min_loz_month.append(val)
else:
    loz_temp = st.number_input("Minimum loz temperature for the whole year", min_value=0, max_value=40, value=20)
    min_loz_month = [loz_temp] * 12

# Optioneel: omzetten naar string voor je functie
start_date_str = start_date.strftime('%d-%m-%Y')
end_date_str = end_date.strftime('%d-%m-%Y')


# Run analysis
if temp_file and discharge_file:
    # final_df = process_data(debiet_file,temperature_file, start_date,end_date)
    final_df = process_data(discharge_file,temp_file, start_date,end_date)
    
# Check the data
    st.subheader("Temperatuur en debiet over tijd (controleer data)")
    fig, ax1 = plt.subplots(figsize=(10, 4))
    
    # Linker y-as: debiet
    if 'waarde' in final_df.columns:
        ax1.plot(final_df.index, final_df['waarde'], label='Debiet (waarde)', color='blue')
        ax1.set_ylabel('Debiet (m³/s)', color='blue')
        ax1.tick_params(axis='y', labelcolor='blue')
    
    # Rechter y-as: temperatuur
    ax2 = ax1.twinx()
    if 'temp' in final_df.columns:
        ax2.plot(final_df.index, final_df['temp'], label='Temperatuur (temp)', color='red')
        ax2.set_ylabel('Temperatuur (°C)', color='red')
        ax2.tick_params(axis='y', labelcolor='red')
    
    ax1.set_xlabel("Datum")
    fig.tight_layout()
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper right')
    ax1.grid(True)
    st.pyplot(fig)