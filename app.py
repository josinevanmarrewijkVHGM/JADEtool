import streamlit as st
import pandas as pd
from utils import process_data, calculate_temperature_adjustments_month, add_logo, plot_monthly_temperature_debiet, plot_monthly_temperature

import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
from matplotlib.colors import to_rgb
import os
red = to_rgb('#ee1c25')
blue = to_rgb('#003d73')
logopath = "assets/logo.png"

alleen_temp = False

# Page configuration
st.set_page_config(page_title="Water Analysis Tool", layout="wide")

# Title and logo
if os.path.exists(logopath):
    st.image(logopath, width=100)
st.title("🔍 Water Temperature & Discharge Analysis Tool")

# Sidebar for file upload and parameters
with st.sidebar:
    st.header("📁 Upload Data Files")
    titel = st.text_input("Titel", value="Naam watergang", max_chars=100)    
    temp_file = st.file_uploader("Upload Water Temperature CSV", type="csv")
    discharge_file = st.file_uploader("Upload Discharge CSV (optional)", type="csv")

    st.header("📅 Date Range Selection")
    default_start = datetime.strptime('01-01-2020', '%d-%m-%Y')
    default_end = datetime.strptime('01-01-2025', '%d-%m-%Y')
    start_date = st.date_input("Start Date", value=default_start)
    end_date = st.date_input("End Date", value=default_end)
    start_date_str = start_date.strftime('%d-%m-%Y')
    end_date_str = end_date.strftime('%d-%m-%Y')

    st.header("⚙️ Analysis Parameters")
    delta_T = st.slider("Temperature Difference (°K)", min_value=2, max_value=12, value=10)
    maintenance = st.number_input("Maintenance Factor", min_value=0.0, max_value=1.0, value=0.2, step=0.01)
    min_dif = st.selectbox("Minimum Difference", options=[2, 3, 4], index=1)

    use_monthly_loz = st.checkbox("Set Monthly Minimum Lozing Temperature?", value=False)

    min_loz_month = []
    if use_monthly_loz:
        st.subheader("🌡️ Monthly Minimum Lozing Temperatures")
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for month in months:
            val = st.number_input(f"{month}", min_value=0, max_value=25)
            min_loz_month.append(val)
    else:
        loz_temp = st.number_input("Annual Minimum Lozing Temperature", min_value=0, max_value=25, value=12)
        min_loz_month = [loz_temp] * 12

    threshold_temp_month = [temp + min_dif for temp in min_loz_month]

    st.header("📊 Visualization Options")
    show_fig1 = st.checkbox("Show Discharge & Temperature Data Visualization", value=True)
    show_fig2 = st.checkbox(f"Show Analysis Results ({start_date_str} to {end_date_str})", value=True)
    show_fig3 = st.checkbox("Show JADE Chart", value=True)

# Run button to trigger analysis
if st.button("🚀 Run Analysis"):
    st.success("Analysis started...")

    
    if temp_file and discharge_file:
        st.write("Files uploaded successfully.")
        st.write(f"Start Date: {start_date_str}, End Date: {end_date_str}")
        st.write(f"Delta T: {delta_T} Kelvin, Maintenance: {maintenance}, Minimaal verschil: {min_dif} Kelvin")
        st.write(f"Threshold Temperatures: {threshold_temp_month} °C")
        plot_debiet = True

        final_df = process_data(discharge_file, temp_file, start_date, end_date)
        
        if show_fig1: # Figuur 1: debiet en temperatuur
            st.markdown("---")
            st.subheader("📈 Temperatuur en debiet over tijd (controleer data)")
            fig, ax1 = plt.subplots(figsize=(10, 4), constrained_layout=True)
            ax1.plot(final_df.index, final_df['debiet'], label='Debiet (waarde)', color='blue')
            ax1.set_ylabel('Debiet (m³/s)', color='blue')
            ax1.tick_params(axis='y', labelcolor='blue')
            ax2 = ax1.twinx()
            ax2.plot(final_df.index, final_df['temperatuur'], label='Temperatuur (temp)', color='red')
            ax2.set_ylabel('Temperatuur (°C)', color='red')
            ax2.tick_params(axis='y', labelcolor='red')
            ax1.set_xlabel("Datum")
            ax1.legend(loc='upper left')
            ax2.legend(loc='upper right')
            ax1.grid(True)
            # add_logo(fig, logopath, position=(0.9, 0.1), zoom=0.05)
            fig.tight_layout()
            st.pyplot(fig)
        
        # Berekeningen
        df_hourly, monthly_summary, yearly_summary = calculate_temperature_adjustments_month(
            final_df, threshold_temp_month, min_dif, delta_T, min_loz_month, max_deltaT=delta_T, method='estimation'
        )
    
        if show_fig2:
            # Figuur 2: jaarlijkse samenvatting
            st.markdown("---")
            st.subheader("📊 Jaarlijkse samenvatting draaiuren en vollasturen")
            st.dataframe(yearly_summary)

            fig1, ax1 = plt.subplots(figsize=(14, 14))
            positions_year = np.arange(len(yearly_summary))
            bar_width = 0.4
            bars_draaiuren = ax1.bar(positions_year, yearly_summary['Draaiuren'], bar_width, label='Draaiuren', color='red', edgecolor='black', alpha=0.7)
            bars_vollasturen = ax1.bar(positions_year + bar_width, yearly_summary['Vollast_uren'], bar_width, label='Vollast uren', color='blue', edgecolor='black', alpha=0.7)
            ax1.set_ylabel('Vollasturen (uren)', color='blue', fontsize=14)
            ax1.tick_params(axis='y', labelcolor='blue')
            ax2 = ax1.twinx()
            ax2.plot(positions_year + bar_width / 2, yearly_summary['Gemiddelde_delta_T'], color='red', marker='o', label='Gemiddelde temperatuur')
            ax2.set_ylabel('Gemiddelde temperatuur (°C)', color='red', fontsize=14)
            ax2.tick_params(axis='y', labelcolor='red')
            ax1.set_xlabel('Jaar', fontsize=14)
            ax1.set_title('Jaarlijkse samenvatting: Vollasturen en temperatuur', fontsize=16)
            ax1.set_xticks(positions_year + bar_width / 2)
            ax1.set_xticklabels(yearly_summary['YearMonth'], fontsize=12)
            for bar in bars_vollasturen:
                yval = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2, yval + 10, f'{yval:.0f}', ha='center', va='bottom', fontsize=13, color='black')
            for bar in bars_draaiuren:
                yval = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2, yval + 10, f'{yval:.0f}', ha='center', va='bottom', fontsize=13, color='black')
            for x, y in zip(positions_year + bar_width / 2, yearly_summary['Gemiddelde_delta_T']):
                ax2.text(x, y, f'{y:.1f}°C', ha='center', va='bottom', fontsize=13, color='black')

            # fig1.tight_layout()
            fig1.tight_layout(pad=2.0)
            add_logo(fig1, zoom=0.01, logopath=logopath, position=(0.95, 0.85))
            

            st.pyplot(fig1)
        
    
        if show_fig3:
            # Figuur 3: maandelijkse samenvatting
            st.markdown("---")
            st.subheader("📉 Analyse watertemperatuur")
            # if plot_debiet:
            fig3, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12), sharex=True)
            fig3, ax1, ax2 = plot_monthly_temperature_debiet(df_hourly, start_date, end_date, delta_T, 
                                            min_loz_month, min_dif, threshold_temp_month,
                                            maintenance, alleen_temp, titel=titel, 
                                            logopath=logopath, fontsize=15, t_lim=[0, 30],
                                            draaiseizoen_shade=True, wko=True
                                            )
            add_logo(fig3, zoom=0.01, logopath=logopath, position=(0.1, 0.98))
            st.pyplot(fig3)

        
    elif temp_file and not discharge_file:
    #     # Your code here
        st.write("Temperature file uploaded successfully.")
        st.write(f"Start Date: {start_date_str}, End Date: {end_date_str}")
        st.write(f"Delta T: {delta_T} Kelvin, Maintenance: {maintenance}, Minimaal verschil: {min_dif} Kelvin")
        st.write(f"Threshold Temperatures: {threshold_temp_month} °C")
        dicharge_file = None
        final_df = process_data(discharge_file, temp_file, start_date, end_date)
        if show_fig1:
            # Figuur 1: debiet en temperatuur
            st.subheader("📈 Temperatuur en debiet over tijd (controleer data)")
            fig, ax2 = plt.subplots(figsize=(10, 4))
            ax2.plot(final_df.index, final_df['temperatuur'], label='Temperatuur (temp)', color='red')
            ax2.set_ylabel('Temperatuur (°C)', color='red')
            ax2.tick_params(axis='y', labelcolor='red')
            ax2.set_xlabel("Datum")
            ax2.grid()
            fig.tight_layout()
            ax2.legend(loc='upper right')
            add_logo(fig, zoom=0.01, logopath=logopath, position=(0.95, 0.85))
            st.pyplot(fig)
        
    #     #         # Berekeningen
        df_hourly, monthly_summary, yearly_summary = calculate_temperature_adjustments_month(
                final_df, threshold_temp_month, min_dif, delta_T, min_loz_month, max_deltaT=delta_T, method='estimation'
            )
        
        if show_fig2:
            # Figuur 2: jaarlijkse samenvatting
            st.subheader("📊 Jaarlijkse samenvatting draaiuren en vollasturen")
            
            fig1, ax1 = plt.subplots(figsize=(13, 10))
            st.dataframe(yearly_summary)

            add_logo(fig1, zoom=0.01, logopath=logopath, position=(0.95, 0.85))
            
            positions_year = np.arange(len(yearly_summary))
            bar_width = 0.4
            bars_draaiuren = ax1.bar(positions_year, yearly_summary['Draaiuren'], bar_width, label='Draaiuren', color='red', edgecolor='black', alpha=0.7)
            bars_vollasturen = ax1.bar(positions_year + bar_width, yearly_summary['Vollast_uren'], bar_width, label='Vollast uren', color='blue', edgecolor='black', alpha=0.7)
            ax1.set_ylabel('Vollasturen (uren)', color='blue', fontsize=14)
            ax1.tick_params(axis='y', labelcolor='blue')
            ax2 = ax1.twinx()
            ax2.plot(positions_year + bar_width / 2, yearly_summary['Gemiddelde_delta_T'], color='red', marker='o', label='Gemiddelde temperatuur')
            ax2.set_ylabel('Gemiddelde temperatuur (°C)', color='red', fontsize=14)
            ax2.tick_params(axis='y', labelcolor='red')
            ax1.set_xlabel('Jaar', fontsize=14)
            ax1.set_title('Jaarlijkse samenvatting: Vollasturen en temperatuur', fontsize=16)
            ax1.set_xticks(positions_year + bar_width / 2)
            ax1.set_xticklabels(yearly_summary['YearMonth'], fontsize=12)
            for bar in bars_vollasturen:
                yval = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2, yval + 10, f'{yval:.0f}', ha='center', va='bottom', fontsize=13, color='black')
            for bar in bars_draaiuren:
                yval = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2, yval + 10, f'{yval:.0f}', ha='center', va='bottom', fontsize=13, color='black')
            for x, y in zip(positions_year + bar_width / 2, yearly_summary['Gemiddelde_delta_T']):
                ax2.text(x, y, f'{y:.1f}°C', ha='center', va='bottom', fontsize=13, color='black')
            fig1.tight_layout()
            
            st.pyplot(fig1)
                
        if show_fig3:
            # Figuur 3: maandelijkse samenvatting
            st.markdown("---")
            st.subheader("📉 Analyse watertemperatuur")
            # if plot_debiet:
            fig3, ax1 = plt.subplots(1, 1, figsize=(13, 8))
            fig3, ax1 = plot_monthly_temperature(df_hourly, start_date, end_date, delta_T, 
                                            min_loz_month, min_dif, threshold_temp_month,
                                            maintenance, alleen_temp, titel=titel, 
                                            logopath=logopath, fontsize=15, t_lim=[0, 30],
                                            draaiseizoen_shade=True, wko=True
                                            ) 
            add_logo(fig3, zoom=0.01, logopath=logopath, position=(0.01, 0.95))
            st.pyplot(fig3)
            
    else:
        st.error("Please upload both temperature and discharge CSV files to proceed.")



