import streamlit as st
import pandas as pd
from utils import process_data, calculate_temperature_adjustments_month
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
from matplotlib.colors import to_rgb

red = to_rgb('#ee1c25')
blue = to_rgb('#003d73')

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

# Optioneel: omzetten naar string voor je functie
start_date_str = start_date.strftime('%d-%m-%Y')
end_date_str = end_date.strftime('%d-%m-%Y')




delta_T = st.slider("Temperature difference (°K)", min_value=0, max_value=12, value=10)
max_deltaT = delta_T
maintenance = st.number_input("Maintenance factor (onderhoud)", min_value=0.0, max_value=1.0, value=0.2, step=0.01)
min_dif = st.selectbox("Minimum difference (min_dif)", options=[2, 3, 4], index=1)

use_monthly_loz = st.checkbox("Set minimum lozings temperature per month?", value=False)

if use_monthly_loz:
    print('Not integrated yet')
    min_loz_month = []
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

threshold_temp_month = [temp + min_dif for temp in min_loz_month]


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
    
    df_hourly, monthly_summary, yearly_summary = calculate_temperature_adjustments_month(final_df, threshold_temp_month, min_dif, delta_T, min_loz_month, max_deltaT, method='estimation')
    
    
    # In Streamlit:
    st.subheader("Jaarlijkse samenvatting")
    
    fig1, ax1 = plt.subplots(figsize=(14, 5))
    positions_year = np.arange(len(yearly_summary))
    bar_width = 0.4
    
    # Bar voor vollasturen
    bars_draaiuren = ax1.bar(positions_year, yearly_summary['Hours'], bar_width, label='Draaiuren', color=red, edgecolor='black', alpha=0.7)
    bars_vollasturen = ax1.bar(positions_year+ bar_width, yearly_summary['Vollast_uren'], bar_width, label='Vollast uren', color=blue, edgecolor='black', alpha=0.7)
    ax1.set_ylabel('Vollasturen (uren)', color=blue, fontsize=14)
    ax1.tick_params(axis='y', labelcolor=blue)
    
    # Lijn voor gemiddelde temperatuur
    ax2 = ax1.twinx()
    ax2.plot(positions_year + bar_width / 2, yearly_summary['Avg_del_T'], color=red, marker='o', label='Gemiddelde temperatuur')
    ax2.set_ylabel('Gemiddelde temperatuur (°C)', color=red, fontsize=14)
    ax2.tick_params(axis='y', labelcolor=red)
    
    ax1.set_xlabel('Jaar', fontsize=14)
    ax1.set_title('Jaarlijkse samenvatting: Vollasturen en temperatuur', fontsize=16)
    ax1.set_xticks(positions_year + bar_width / 2)
    ax1.set_xticklabels(yearly_summary['YearMonth'], fontsize=12)
    
    # Datalabels
    for bar in bars_vollasturen:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + 10, f'{yval:.0f}', ha='center', va='bottom', fontsize=13, color='black')
    for bar in bars_draaiuren:
        yval = bar.get_height()
        ax1.text(bar.get_x()+bar.get_width()/2, yval + 10, f'{yval:.0f}', ha='center', va='bottom', fontsize=13, color='black')
        
    for x, y in zip(positions_year + bar_width / 2, yearly_summary['Avg_del_T']):
        ax2.text(x, y, f'{y:.1f}°C', ha='center', va='bottom', fontsize=13, color='black')
    
    fig1.tight_layout()
    st.dataframe(yearly_summary)
    st.pyplot(fig1)