import streamlit as st
import pandas as pd
from utils import process_data, calculate_temperature_adjustments_month, calculate_temperature_adjustments_month_v2, add_logo, plot_monthly_temperature_debiet_v2, plot_monthly_temperature_v2
import io
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
st.title("🔍 Aquathermie Data Explorer")

# Sidebar for file upload and parameters
with st.sidebar:
    st.header("📁 Upload")
    titel = st.text_input("Titel", value="Naam watergang", max_chars=100)    
    temp_file = st.file_uploader("Upload Watertemperatuur CSV (°C)", type="csv")
    discharge_file = st.file_uploader("Upload CSV van debiet (m3/s) (optional)", type="csv")

    st.header("📅 Tijdsperiode")
    default_start = datetime.strptime('01-01-2020', '%d-%m-%Y')
    default_end = datetime.strptime('01-01-2026', '%d-%m-%Y')
    start_date = st.date_input("Start datum", value=default_start)
    end_date = st.date_input("Eind datum", value=default_end)
    start_date_str = start_date.strftime('%d-%m-%Y')
    end_date_str = end_date.strftime('%d-%m-%Y')
    
    st.header("⚙️ Uitgangspunten standaard")
    delta_T_global = st.slider("Temperatuur verschil (K)", min_value=2, max_value=12, value=10)
    maintenance = st.number_input("Onderhouds factor", min_value=0.0, max_value=1.0, value=0.2, step=0.01)
    min_dif = st.selectbox("Minimaal temperatuur verschil (K)", options=[2, 3, 4, 5], index=1)
    loz_temp = st.number_input("Jaarlijkse minimale lozingstemperatuur", min_value=0, max_value=30, value=12)
    
    st.header("⚙️ Uitgangspunten uitgebreid")
    use_monthly_loz = st.checkbox("Maandelijkse minimale lozingstemperaturen", value=False)
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
    
    # Lozing temperatures
    min_loz_month = []
    if use_monthly_loz:
        st.subheader("🌡️ Maandelijkse minimum lozingstemperatuur")
        use_monthly = True
        for m in months:
            val = st.number_input(f"{m}", min_value=0, max_value=30, value=12)
            min_loz_month.append(val)
    else:
        use_monthly = False
        min_loz_month = [loz_temp] * 12
    
    # Threshold temps
    threshold_temp_month = [temp + min_dif for temp in min_loz_month]
    
            
    st.header("⚙️ Uitgangspunten automatisch")
    # (value1 for ≥16°C, value2 for 10–16°C, value3 for 2–10°C)

    # Mode selection
    auto_mode = st.radio(
        "Kies automatische modus:",
        options=[
            "Geen automatische modus",
            "Aquathermie voor alleen regeneratie bodemenergiesysteem",
            "Aquathermie voor regeneratie en directe levering",
            "Aquathermie voor directe levering"
        ],
        index=0
    )
    
    automatic = False
    auto_values = (0, 0, 0)  # default
    
    if auto_mode == "Aquathermie voor alleen regeneratie bodemenergiesysteem":
        automatic = True
        modus = "automatic"
        st.subheader("Instellingen: Alleen regeneratie")
        delta_T1 = st.slider("Temperatuur verschil (K), ≥16°C", min_value=3, max_value=12, value=10)
        auto_values = (delta_T1, 0, 0)
    
    elif auto_mode == "Aquathermie voor regeneratie en directe levering":
        automatic = True
        st.subheader("Instellingen: Regeneratie + directe levering")
        modus = "automatic"
        delta_T1 = st.slider("Temperatuur verschil (K), ≥16°C", min_value=5, max_value=12, value=10)
        delta_T2 = st.slider("Temperatuur verschil (K), 10–16°C", min_value=3, max_value=10, value=3)
        delta_T3 = st.slider("Temperatuur verschil (K), 2–10°C", min_value=3, max_value=8, value=3)
        auto_values = (delta_T1, delta_T2, delta_T3)
    
    elif auto_mode == "Aquathermie voor directe levering":
        automatic = True
        st.subheader("Instellingen: Directe levering")
        modus = "automatic"
        delta_T_all = st.slider("Temperatuur verschil (K) voor alle bereiken", min_value=2, max_value=6, value=6)
        auto_values = (delta_T_all, delta_T_all, delta_T_all)
    
    # --- Determine delta_T input for non-automatic modes ---
    if not automatic:
        delta_T_input = delta_T_global
        if use_monthly:
            modus = 'uitgebreid'
        else:
            modus = 'standaard'
    else:
        delta_T_input = None  # ignored in automatic mode
        modus = 'automatic'

    st.header("📊 Keuze grafieken")
    show_fig1 = st.checkbox(f"1. Data visualisatie {titel}", value=True)
    show_fig2 = st.checkbox(f"2. Resultaten analyse ({start_date_str} to {end_date_str})", value=True)
    show_fig3 = st.checkbox(f"3. JADE grafiek {titel}", value=True)

# Run button to trigger analysis
st.write("De JADE-tool is ontwikkeld om inzicht te krijgen in de potentie van oppervlaktewateren voor TEO-systemen of RWZI's. Met deze functie kan snel inzicht verkregen worden in de hoeveelheid draaiuren, de gemiddelde innametemperatuur en de gemiddelde afkoeling. Dit maakt het mogelijk om snel en nauwkeurig de potentie van een watersysteem te bepalen, afhankelijk van de gekozen uitgangspunten.")

st.write("- Maximale delta T: Dit is de maximale temperatuurverschil tussen inname en lozing. Een hogere delta T betekent een efficiënter systeem, maar kan beperkt worden door technische of ecologische randvoorwaarden.")
st.write("- Minimale lozingstemperatuur: De minimale temperatuur van het geloosde water. Deze grenswaarde voorkomt onacceptabele invloed op het ontvangend water.")
st.write("- Minimaal verschil tussen lozing en inname: dit criterium waarborgt dat er voldoende thermisch rendement is. Een te klein verschil kan duiden op inefficiëntie of ongeschiktheid van het systeem.")
st.write("- Percentage onderhoud (standaard 20 %): Dit percentage houdt rekening met de tijd waarin het systeem niet operationeel is door gepland onderhoud. Het beïnvloedt direct het aantal draaiuren dat beschikbaar is.")

if st.button("🚀 Start analyse"):
    st.success("Gestart...")

    # %%% ______________________________________Watergang met debiet en temperatuur
    if temp_file and discharge_file:
        st.write("Files uploaded successfully.")
        st.write(f"Start: {start_date_str}, Eind datum: {end_date_str}")
        try:
            st.write(f"Delta T: {delta_T_global} Kelvin, Onderhoudsfactor: {maintenance}, Minimaal verschil: {min_dif} Kelvin")
        except:
            st.write(f"Delta T: {delta_T_global} Kelvin, Onderhoudsfactor: {maintenance}, Minimaal verschil: {min_dif} Kelvin")
        finally:
            st.write(f"Automatic mode {auto_mode}, {auto_values}, Onderhoudsfactor: {maintenance}, Minimaal verschil: {min_dif} Kelvin")

        st.write(f"Minimale innametemperatuur (per maand): {threshold_temp_month} °C")
        plot_debiet = True

        final_df = process_data(discharge_file, temp_file, start_date, end_date)
        
        if show_fig1: # Figuur 1: debiet en temperatuur
            st.markdown("---")
            st.subheader("📈 Temperatuur en debiet over tijd (controleer data)")
            fig, ax1 = plt.subplots(figsize=(10, 4), constrained_layout=True)
            ax1.plot(final_df.index, final_df['debiet'], label='Debiet', color='blue')
            ax1.set_ylabel('Debiet (m³/s)', color='blue')
            ax1.tick_params(axis='y', labelcolor='blue')
            ax2 = ax1.twinx()
            ax2.plot(final_df.index, final_df['temperatuur'], label='Temperatuur', color='red')
            ax2.set_ylabel('Temperatuur (°C)', color='red')
            ax2.tick_params(axis='y', labelcolor='red')
            ax1.set_xlabel("Datum")
            ax1.legend(loc='upper left')
            ax2.legend(loc='upper right')
            ax1.grid(True)
            # add_logo(fig, zoom=0.2, logo_path=logopath, position=(0.9, 0.1))
            fig.tight_layout()
            st.pyplot(fig)
        
        # Berekeningen

        df_hourly, monthly_summary, yearly_summary = calculate_temperature_adjustments_month_v2(
            final_df,
            threshold_temp_month,
            min_dif,
            delta_T_input,
            min_loz_month,
            max_deltaT=delta_T_input,
            method='estimation',
            automatic=automatic,
            auto_values=auto_values
        )


        if show_fig2:
            # Figuur 2: jaarlijkse samenvatting
            st.markdown("---")
            st.subheader("📊 Jaarlijkse samenvatting draaiuren en vollasturen")
            st.dataframe(yearly_summary)
            delta_T= delta_T_input
        
            # --- Build ΔT reference per year robustly for scalar/monthly/automatic ---
            # df_hourly must include 'Year' and 'DeltaT_Cap' from calculate_temperature_adjustments_month_v2
            if 'DeltaT_Cap' not in df_hourly.columns:
                st.warning("DeltaT_Cap ontbreekt in df_hourly. Controleer de aanroep van calculate_temperature_adjustments_month_v2.")
                # Fallback: compute from input when possible
                # Scalar fallback:
                if np.isscalar(delta_T):
                    df_hourly['DeltaT_Cap'] = float(delta_T)
                else:
                    # Generic fallback: assume max yearly cap equals max of provided list/dict
                    try:
                        # Try to normalize delta_T_input into list of 12
                        months_short = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
                        if isinstance(delta_T, dict):
                            if all(k in range(1, 13) for k in delta_T.keys()):
                                monthly_caps = [float(delta_T[i]) for i in range(1, 13)]
                            else:
                                name_to_idx = {m: i+1 for i, m in enumerate(months_short)}
                                monthly_caps = [float(delta_T[m]) for m in months_short]
                        else:
                            monthly_caps = list(delta_T)  # list/tuple/array
                        df_hourly['DeltaT_Cap'] = np.nan  # unknown per hour; just avoid crash
                    except Exception:
                        df_hourly['DeltaT_Cap'] = np.nan
        
            fig1, ax1 = plt.subplots(figsize=(8, 4))
            positions_year = np.arange(len(yearly_summary))
            bar_width = 0.4
        
            # Bars
            bars_draaiuren = ax1.bar(
                positions_year, yearly_summary['Draaiuren'], bar_width,
                label='Draaiuren', color='red', edgecolor='black', alpha=0.7
            )
            bars_vollasturen = ax1.bar(
                positions_year + bar_width, yearly_summary['Vollast_uren'], bar_width,
                label='Vollast uren', color='blue', edgecolor='black', alpha=0.7
            )
        
            ax1.set_ylabel('Vollasturen (uren)', color='blue', fontsize=14)
            ax1.tick_params(axis='y', labelcolor='blue')
            ax1.grid(True)
        
            # Twin axis for temperatures
            ax2 = ax1.twinx()
            line_temp, = ax2.plot(
                positions_year + bar_width / 2,
                yearly_summary['Gemiddelde_delta_T'],
                color='red', marker='o', label='Gem. ΔT'
            )
        
 
        
            ax2.set_ylabel('Gemiddelde afkoeling (°K)', color='k', fontsize=14)
            ax2.tick_params(axis='y', labelcolor='k')
        
            # Dynamic y-limit: consider actual averages + caps
            ylim_candidates = [yearly_summary['Gemiddelde_delta_T'].max()]

            ax2.set_ylim(0, max(ylim_candidates) + 2)
        
            ax1.set_xlabel('Jaar', fontsize=14)
            ax1.set_title('Jaarlijkse samenvatting: Draaiuren, vollasturen en temperatuur', fontsize=16)
            ax1.set_xticks(positions_year - bar_width / 2)
            ax1.set_xticklabels(yearly_summary['Year'], fontsize=12)
        
            # Value labels for bars
            for bar in bars_vollasturen:
                yval = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2, yval + 10, f'{yval:.0f}', ha='center', va='bottom', fontsize=13, color='black')
        
            for bar in bars_draaiuren:
                yval = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2, yval + 10, f'{yval:.0f}', ha='center', va='bottom', fontsize=13, color='black')
        
            # Point labels for average ΔT
            for x, y in zip(positions_year + bar_width / 2, yearly_summary['Gemiddelde_delta_T']):
                ax2.text(x, y, f'{y:.1f}°K', ha='center', va='bottom', fontsize=13, color='black')
        
            # Gecombineerde legenda op figuurniveau
            handles1, labels1 = ax1.get_legend_handles_labels()
            handles2, labels2 = ax2.get_legend_handles_labels()
            # Remove None handles if caps were missing
            merged_handles = [h for h in handles1 + handles2 if h is not None]
            merged_labels = []
            for h in handles1 + handles2:
                if h is not None:
                    idx = (handles1 + handles2).index(h)
                    merged_labels.append((labels1 + labels2)[idx])
            fig1.legend(merged_handles, merged_labels, loc='upper center', ncol=3, bbox_to_anchor=(0.5, 1.05))
        
            fig1.tight_layout(pad=2.0)
            st.pyplot(fig1)

        
    
        if show_fig3:
            # Figuur 3: maandelijkse samenvatting
            st.markdown("---")
            st.subheader("📉 Analyse watertemperatuur")
            # if plot_debiet:
            s_1 = 14
            s_2 = 10
            fig3, (ax1, ax2) = plt.subplots(2, 1, figsize=(s_1, s_2), sharex=True)
            # fig3, ax1, ax2, results_df = plot_monthly_temperature_debiet_v2(df_hourly, start_date, end_date, delta_T, 
            #                                 min_loz_month, min_dif, threshold_temp_month,
            #                                 maintenance, alleen_temp, titel=titel, 
            #                                 fontsize=15, t_lim=[0, 30],
            #                                 draaiseizoen_shade=True, wko=True,
            #                                 s1=s_1, s2=s_2)
            print(modus)
            fig3, ax1, ax2, results_df = plot_monthly_temperature_debiet_v2(df_hourly, start_date, end_date,
                                                                            delta_T_input, min_loz_month, min_dif, threshold_temp_month,
                                                                            maintenance, titel=titel,
                                                                            fontsize=15, t_lim=[0, 30],
                                                                            draaiseizoen_shade=True, wko=True,
                                                                            s1=s_1, s2=s_2,
                                                                            mode=modus, auto_mode=auto_mode, auto_values=auto_values)
            # add_logo(fig3, zoom=0.1, logo_path=logopath, position=(0.8, 0.99))

            st.pyplot(fig3)
            buf = io.BytesIO()
            fig3.savefig(buf, format="png", bbox_inches='tight', dpi=300)
            buf.seek(0)
            
            st.dataframe(results_df, width='stretch')

            st.download_button(
                label="📥 Download grafiek Aquathermie Data Explorer als PNG",
                data=buf,
                file_name=f"JADE_{titel}.png",
                mime="image/png"
            )



# %%% ______________________________________Alleen temperatuur
        
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
            st.subheader("📈 Temperatuur over tijd (controleer data)")
            fig, ax2 = plt.subplots(figsize=(10, 4))
            ax2.plot(final_df.index, final_df['temperatuur'], label='Temperatuur', color='red')
            ax2.set_ylabel('Temperatuur (°C)', color='red')
            ax2.tick_params(axis='y', labelcolor='red')
            ax2.set_xlabel("Datum")
            ax2.grid()
            fig.tight_layout()
            ax2.legend(loc='upper right')
            st.pyplot(fig)
        
 # Berekeningen
        df_hourly, monthly_summary, yearly_summary = calculate_temperature_adjustments_month_v2(
                final_df, threshold_temp_month, min_dif, delta_T, min_loz_month, max_deltaT=delta_T, method='estimation'
            )

        st.write(f"Check max:  {np.max(df_hourly['temperatuur'])}")
        st.write(f"Check min:  {np.min(df_hourly['temperatuur'])}")
        st.write(f"Check mean:  {np.mean(df_hourly['temperatuur'])}")

        
        if show_fig2:
            # Figuur 2: jaarlijkse samenvatting
            st.markdown("---")
            st.subheader("📊 Jaarlijkse samenvatting draaiuren en vollasturen")
            st.dataframe(yearly_summary)
            
            fig1, ax1 = plt.subplots(figsize=(8, 4))
            positions_year = np.arange(len(yearly_summary))
            bar_width = 0.4
            
            bars_draaiuren = ax1.bar(positions_year, yearly_summary['Draaiuren'], bar_width, label='Draaiuren', color='red', edgecolor='black', alpha=0.7)
            bars_vollasturen = ax1.bar(positions_year + bar_width, yearly_summary['Vollast_uren'], bar_width, label='Vollast uren', color='blue', edgecolor='black', alpha=0.7)
            
            ax1.set_ylabel('Vollasturen (uren)', color='blue', fontsize=14)
            ax1.tick_params(axis='y', labelcolor='blue')
            ax1.grid(True)
            
            ax2 = ax1.twinx()
            line_temp, = ax2.plot(positions_year + bar_width / 2, yearly_summary['Gemiddelde_delta_T'], color='red', marker='o')
            line_max = ax2.axhline(y=delta_T, color='orange', linestyle='--', linewidth=0.5, label='max delta T')
            ax2.set_ylabel('Gemiddelde afkoeling (°K)', color='k', fontsize=14)
            ax2.tick_params(axis='y', labelcolor='k')
            ax2.set_ylim(0, delta_T + 2)
            
            ax1.set_xlabel('Jaar', fontsize=14)
            ax1.set_title('Jaarlijkse samenvatting: Draaiuren, vollasturen en temperatuur', fontsize=16)
            ax1.set_xticks(positions_year - bar_width / 2)
            ax1.set_xticklabels(yearly_summary['YearMonth'], fontsize=12)
            
            for bar in bars_vollasturen:
                yval = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2, yval + 10, f'{yval:.0f}', ha='center', va='bottom', fontsize=13, color='black')
            
            for bar in bars_draaiuren:
                yval = bar.get_height()

            ax1.text(bar.get_x() + bar.get_width()/2, yval + 10, f'{yval:.0f}', ha='center', va='bottom', fontsize=13, color='black')
            
            for x, y in zip(positions_year + bar_width / 2, yearly_summary['Gemiddelde_delta_T']):
                ax2.text(x, y, f'{y:.1f}°K', ha='center', va='bottom', fontsize=13, color='black')
            
            # Gecombineerde legenda op figuurniveau
            handles1, labels1 = ax1.get_legend_handles_labels()
            handles2, labels2 = ax2.get_legend_handles_labels()
            fig1.legend(handles1 + handles2, labels1 + labels2, loc='upper center', ncol=3, bbox_to_anchor=(0.5, 1.05))
            
            fig1.tight_layout(pad=2.0)
            plt.show()
            st.pyplot(fig1)


                
        if show_fig3:
            # Figuur 3: maandelijkse samenvatting
            st.markdown("---")
            st.subheader("📉 Analyse watertemperatuur")
            
            s_1 = 14
            s_2 = 10
            fig3, ax1 = plt.subplots(1, 1, figsize=(s_1, s_2))
            fig3, ax1, results_df = plot_monthly_temperature_v2(df_hourly, start_date, end_date, delta_T, 
                                            min_loz_month, min_dif, threshold_temp_month,
                                            maintenance, alleen_temp, titel=titel, 
                                            fontsize=15, t_lim=[0, 30],
                                            draaiseizoen_shade=True, wko=True,
                                            s1=s_1, s2=s_2)
            
            
            # add_logo(fig3, zoom=0.3, logo_path=logopath, position=(0.01, 0.99))
            st.pyplot(fig3)


            buf = io.BytesIO()
            fig3.savefig(buf, format="png", bbox_inches='tight', dpi=300)
            buf.seek(0)
            
            # # Styling toepassen
            # styled_df = results_df.style\
            #     .format(precision=2)\
            #     .highlight_max(axis=0, color='lightgreen')\
            #     .highlight_min(axis=0, color='lightcoral')
            
            # # Weergeven in Streamlit
            # st.dataframe(styled_df, use_container_width=True)
            st.dataframe(results_df, width='stretch')
            st.download_button(
                label="📥 Download grafiek Aquathermie Data Explorer als PNG",
                data=buf,
                file_name=f"JADE_{delta_T}_{titel}.png",
                mime="image/png"
            )

            
    else:
        st.error("Please upload both temperature and discharge CSV files to proceed.")



