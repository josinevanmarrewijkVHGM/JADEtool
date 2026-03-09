import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# import matplotlib.dates as mdates
# from datetime import datetime
# from matplotlib.dates import MonthLocator, date2num
# import os
from matplotlib.colors import to_rgb
from matplotlib.offsetbox import OffsetImage, AnnotationBbox


import matplotlib.dates as mdates
from matplotlib.dates import date2num

import os
import matplotlib.image as mpimg
plt.rcParams['font.family'] = 'sans-serif'
# from matplotlib.offsetbox import OffsetImage, AnnotationBbox
logopath = "assets/logo.png"

# Set the font to Tahoma
# plt.rcParams['font.family'] = 'Tahoma'

red = to_rgb('#ee1c25')
blue = to_rgb('#003d73')

# Load your image file
# image_path = r"C:\Users\JosinevanMarrewijk\OneDrive - vhgm.nl\Aquathermie sharepoint\Afbeeldingen\Schermafbeelding 2024-09-05 080412.png"  # Replace with your image file path
# img = mpimg.imread(image_path)

### Berekening temperatuurwinst 
# standaardwaarden
rhow = 998 #kg/m3
cp = 4185 # warmtecoefficient water J/ (kg*K)
cp_adjusted = 4200 * 1000/3600 # warmtecoefficient water kWh/(m^3 K)  

def process_data(debiet_file, temperature_file, start_date, end_date):
    def read_and_prepare(file_path, file_type):
        df = pd.read_csv(file_path, delimiter=';', encoding='ISO-8859-1')
        print(f'{file_type} columns:', df.columns)

        # Converteer alle numerieke kolommen en verwijder outliers
        for col in df.columns:
            if col != 'DateTime':
                df[col] = pd.to_numeric(df[col], errors='coerce')
                if file_type == 'Temperature':
                    high_values = df[col] > 50
                    if high_values.any():
                        print(f"⚠️ {high_values.sum()} waarden > 50 verwijderd in kolom '{col}'")
                    df.loc[high_values, col] = np.nan
                # Bereken z-score en markeer outliers (>3 std)
                col_mean = df[col].mean()
                col_std = df[col].std()
                outliers = (df[col] - col_mean).abs() > 3 * col_std
                df.loc[outliers, col] = np.nan  # vervang outliers door NaN

                # Interpoleer ontbrekende waarden
                df[col] = df[col].interpolate(method='linear')

        # Datum parsing
        if 'DateTime' in df.columns:
            try:
                df['DateTime'] = pd.to_datetime(df['DateTime'], format='%d-%m-%Y %H:%M')
            except Exception:
                df['DateTime'] = pd.to_datetime(df['DateTime'], errors='coerce', dayfirst=True)
        else:
            raise ValueError(f"Geen geldige 'DateTime' kolom gevonden in {file_type}, zorg ervoor dat de kolumnaam van de datum en tijd 'DateTime' is en data bevat gemeten per x minuten of uurlijks.")

        # Zet index en resample naar uur
        df.set_index('DateTime', inplace=True)
        df = df.resample('H').mean()

        return df

    # Lees debietbestand (optioneel)
    if debiet_file:
        df_debiet = read_and_prepare(debiet_file, 'Debiet')
    else:
        df_debiet = pd.DataFrame()

    # Lees temperatuurbestand
    df_temp = read_and_prepare(temperature_file, 'Temperature')
    df_temp.replace(-999, np.nan, inplace=True)

    # Merge beide datasets
    if not df_debiet.empty:
        final_df = pd.merge(df_debiet, df_temp, left_index=True, right_index=True, how='outer')
        final_df.columns = ['debiet', 'temperatuur'] + list(final_df.columns[2:])
    else:
        final_df = df_temp.copy()
        final_df.columns = ['temperatuur'] + list(final_df.columns[1:])

    # Filter op start- en einddatum
    try:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        final_df = final_df[(final_df.index >= start_date) & (final_df.index < end_date)]
    except ValueError as e:
        print(f"Error: Incorrect date format for start_date or end_date. Please use a valid date format. {e}")
        return None

    print('Final df columns:', final_df.columns)
    return final_df


def calculate_temperature_adjustments_month(df, threshold_temp_month, min_dif, delta_T, min_loz_month, max_deltaT, method=None):
    """
    Calculate temperature adjustments based on threshold temperature and other parameters.
    Returns: df_hourly, monthly_summary, yearly_summary
    """
    if method == 'estimation':
        df_hourly = df.resample('H').interpolate(method='linear')
    else:
        df_hourly = df.resample('H').mean()
    
    try:
        df_hourly['Month'] = df_hourly.index.month
    except ValueError as e:
        print(f"Error: Verkeerd datumbereik geselecteerd: het csv-document bevat geen data in de geselecteerde periode.")
        return None
    df_hourly['Year'] = df_hourly.index.year

    threshold_temp_map = {month: temp for month, temp in enumerate(threshold_temp_month, start=1)}
    df_hourly['Threshold_Temperature'] = df_hourly['Month'].map(threshold_temp_map)

    df_hourly['Above_Threshold'] = (df_hourly['temperatuur'] > df_hourly['Threshold_Temperature']).astype(int)
    df_hourly['Above_Threshold'] = df_hourly['Above_Threshold'].rolling(window=2, min_periods=2).sum().shift(-1).fillna(0).astype(int)
    df_hourly['Above_Threshold'] = (df_hourly['Above_Threshold'] == 2).astype(int)

    min_loz_map = {month: temp for month, temp in enumerate(min_loz_month, start=1)}
    df_hourly['Min_Lozingstemperatuur'] = df_hourly['Month'].map(min_loz_map)
    df_hourly['Average_bron'] = np.where(df_hourly['Above_Threshold'] == 1, df_hourly['temperatuur'], np.nan)

    df_hourly['Temp_Difference'] = np.where(df_hourly['Above_Threshold'] == 1, df_hourly['temperatuur'] - df_hourly['Min_Lozingstemperatuur'], np.nan)
    df_hourly['Temp_Difference'] = df_hourly['Temp_Difference'].clip(upper=delta_T)
    df_hourly['Lozingstemperatuur'] = np.where(df_hourly['Above_Threshold'] == 1, df_hourly['temperatuur'] - df_hourly['Temp_Difference'], np.nan)

    df_hourly['Yearly_Avg_delta_T'] = df_hourly.groupby(df_hourly.index.year)['Temp_Difference'].transform('mean')
    df_hourly['Draaiuren'] = df_hourly.groupby('Year')['Above_Threshold'].cumsum()

    # Maandelijkse samenvatting
    df_hourly['YearMonth'] = df_hourly.index.to_period('M')
    non_zero = df_hourly[df_hourly['Temp_Difference'].notna()]
    monthly_summary = non_zero.groupby('YearMonth').agg(
        Count=('Temp_Difference', 'size'),
        Hours=('Above_Threshold', 'sum'),
        Avg_del_T=('Temp_Difference', 'mean')
    ).reset_index()
    
    # Energie en vollasturen berekenen (stel Q = 1 voor demo, pas aan indien nodig)
    # Q = 1.0
    # monthly_summary['Energie_onttrokken_GJ'] = monthly_summary['Hours'] * monthly_summary['Avg_del_T'] * Q * 998 * 4180 * 1e-9
    monthly_summary['Vollast_uren'] = (monthly_summary['Avg_del_T'] / delta_T) * monthly_summary['Hours']
    monthly_summary = monthly_summary.round({"Avg_del_T": 2, "Vollast_uren": 2})

    
    if max_deltaT is None:
        max_deltaT = delta_T
    # Maandelijkse samenvatting
    df_hourly['YearMonth'] = df_hourly.index.to_period('Y')
    non_zero = df_hourly[df_hourly['Temp_Difference'].notna()]
    yearly_summary = non_zero.groupby('YearMonth').agg(
        Draaiuren=('Above_Threshold', 'sum'),
        Gemiddelde_delta_T =('Temp_Difference', 'mean')
    ).reset_index()
    yearly_summary['Vollast_uren'] = (yearly_summary['Gemiddelde_delta_T'] / delta_T) * yearly_summary['Draaiuren']
    yearly_summary = yearly_summary.round({"Gemiddelde_delta_T": 2, "Vollast_uren": 0})
    
    return df_hourly, monthly_summary, yearly_summary 


def calculate_temperature_adjustments_month_v2(
    df,
    threshold_temp_month,
    min_dif,
    delta_T,
    min_loz_month,
    max_deltaT=None,
    method=None,
    automatic=False,
    auto_values=(8, 6, 4)  # (value1 for ≥16°C, value2 for 10–16°C, value3 for 2–10°C)
):
    """
    Calculate temperature adjustments based on monthly threshold temperatures and other parameters.

    Parameters
    ----------
    automatic : bool
        If True, delta_T is chosen dynamically based on measured temperature ranges.
    auto_values : tuple of 3 floats
        Values for delta_T when T ≥16°C, 10–16°C, and 2–10°C respectively.
    """

    # --- Resampling ---
    if method == 'estimation':
        df_hourly = df.resample('H').interpolate(method='linear')
    else:
        df_hourly = df.resample('H').mean()

    # Validate datetime index
    try:
        df_hourly['Month'] = df_hourly.index.month
    except ValueError:
        print("Error: Verkeerd datumbereik geselecteerd.")
        return None
    df_hourly['Year'] = df_hourly.index.year

    # Validate monthly inputs
    if len(threshold_temp_month) != 12:
        raise ValueError("threshold_temp_month must have 12 values.")
    if len(min_loz_month) != 12:
        raise ValueError("min_loz_month must have 12 values.")

    # Maps for monthly values
    threshold_temp_map = {month: temp for month, temp in enumerate(threshold_temp_month, start=1)}
    df_hourly['Threshold_Temperature'] = df_hourly['Month'].map(threshold_temp_map)

    min_loz_map = {month: temp for month, temp in enumerate(min_loz_month, start=1)}
    df_hourly['Min_Lozingstemperatuur'] = df_hourly['Month'].map(min_loz_map)

    # --- DeltaT logic ---
    if automatic:
        # Dynamic assignment based on measured temperature
        cond1 = df_hourly['temperatuur'] >= 16
        cond2 = (df_hourly['temperatuur'] >= 10) & (df_hourly['temperatuur'] < 16)
        cond3 = (df_hourly['temperatuur'] >= 2) & (df_hourly['temperatuur'] < 10)
        df_hourly['DeltaT_Cap'] = np.select([cond1, cond2, cond3],
                                            [auto_values[0], auto_values[1], auto_values[2]],
                                            default=auto_values[2])  # fallback to lowest
    else:
        # Original scalar or monthly logic

        df_hourly['DeltaT_Cap'] = float(delta_T)


    # --- Above threshold logic ---
    df_hourly['Above_Threshold'] = (df_hourly['temperatuur'] > df_hourly['Threshold_Temperature']).astype(int)
    df_hourly['Above_Threshold'] = (
        df_hourly['Above_Threshold'].rolling(window=2, min_periods=2).sum().shift(-1).fillna(0).astype(int)
    )
    df_hourly['Above_Threshold'] = (df_hourly['Above_Threshold'] == 2).astype(int)

    # --- Core calculations ---
    df_hourly['Average_bron'] = np.where(df_hourly['Above_Threshold'] == 1, df_hourly['temperatuur'], np.nan)
    df_hourly['Temp_Difference'] = np.where(
        df_hourly['Above_Threshold'] == 1,
        df_hourly['temperatuur'] - df_hourly['Min_Lozingstemperatuur'],
        np.nan
    )
    df_hourly['Temp_Difference'] = np.where(
        df_hourly['Temp_Difference'].notna(),
        np.minimum(df_hourly['Temp_Difference'], df_hourly['DeltaT_Cap']),
        np.nan
    )
    df_hourly['Lozingstemperatuur'] = np.where(
        df_hourly['Above_Threshold'] == 1,
        df_hourly['temperatuur'] - df_hourly['Temp_Difference'],
        np.nan
    )

    # Vollast contribution
    df_hourly['Vollast_uren_contrib'] = np.where(
        (df_hourly['Above_Threshold'] == 1) & (df_hourly['DeltaT_Cap'] > 0),
        df_hourly['Temp_Difference'] / df_hourly['DeltaT_Cap'],
        0.0
    )

    # Summaries
    mask = df_hourly['Temp_Difference'].notna()
    df_hourly['YearMonth'] = df_hourly.index.to_period('M')
    monthly_summary = (
        df_hourly.loc[mask].groupby('YearMonth').agg(
            Count=('Temp_Difference', 'size'),
            Hours=('Above_Threshold', 'sum'),
            Avg_del_T=('Temp_Difference', 'mean'),
            Vollast_uren=('Vollast_uren_contrib', 'sum'),
        ).reset_index()
    ).round({"Avg_del_T": 2, "Vollast_uren": 2})

    yearly_summary = (
        df_hourly.loc[mask].groupby('Year').agg(
            Draaiuren=('Above_Threshold', 'sum'),
            Gemiddelde_delta_T=('Temp_Difference', 'mean'),
            Vollast_uren=('Vollast_uren_contrib', 'sum'),
        ).reset_index()
    ).round({"Gemiddelde_delta_T": 2, "Vollast_uren": 0})

    df_hourly['Yearly_Avg_delta_T'] = df_hourly.groupby(df_hourly.index.year)['Temp_Difference'].transform('mean')
    df_hourly['Draaiuren'] = df_hourly.groupby('Year')['Above_Threshold'].cumsum()

    return df_hourly, monthly_summary, yearly_summary






def plot_monthly_temperature_debiet(
    df_final, start_date, end_date, delta_T, min_loz, min_dif, threshold_temp,
    maintenance_factor, alleen_temp, titel='naam',
    fontsize=15, t_lim=[0, 30],
    draaiseizoen_shade=True, wko=True, s1=10, s2=10
):
    """
    Plots water temperature and flow rate data with optional logo, seasonal shading, and summary statistics.
    """
    df = df_final.copy()
    df_day = df.resample('D').mean()
    df_month_rolling = df_day.select_dtypes(include='number').rolling(window=30, center=True, min_periods=1).mean()
    df_month = df_day.resample('M').mean()
    df_month.index = pd.to_datetime(df_month.index).to_period('M').start_time

    # Create figure and axes
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(s1, s2), sharex=True)
    fig.suptitle(
        f'\n Analyse watertemperatuur, draaiuren en debiet\n{titel}',
        fontsize=fontsize,  # Maak het groter voor meer nadruk
        x=0.45,                  # Centreer horizontaal
        ha='center',            # Zorg dat de uitlijning ook gecentreerd is
        weight='bold'           # Maak de tekst vetgedrukt
    )
    ax1.set_title('Watertemperatuur', size=fontsize-2)

    # Plot temperature data
    ax1.scatter(df.index, df['temperatuur'], s=0.5, alpha=1, label='Gemeten watertemperatuur')
    ax1.plot(df_month_rolling['temperatuur'], color=red, lw=1.5, label='Maandelijks gemiddelde')
    df['Lozingstemperatuur'].plot(ax=ax1, label='Lozingstemperatuur', linestyle='-', color='g', linewidth=1.5)


    # Controleer of er meer dan één uniek jaar in de index zit
    years = df.index.year.unique()
    
    if len(years) > 1:
        # Annotaties alleen toevoegen als er meerdere jaren zijn
        for year, group in df.groupby(df.index.year):
            max_draaiuren = group['Draaiuren'].max()
            avg_delta_T = group['Yearly_Avg_delta_T'].mean()
            if max_draaiuren > 0:
                max_date = group['Draaiuren'].idxmax()
                ax1.text(
                    max_date - pd.Timedelta(days=120),
                    0.5,
                    f"{year}\nDraaiuren {max_draaiuren:,.0f}".replace(',', '.') +
                    "\nGem. ΔT: " + f"{avg_delta_T:.2f}".replace('.', ',') + " Kelvin",
                    fontsize=fontsize - 3,
                    ha='center',
                    va='bottom',
                    bbox=dict(facecolor='white', alpha=0.8)
                )

    # Plot discharge data
    ax2.scatter(df.index, df['debiet'], alpha=0.5, color=blue, s=1, label='Gemeten (uurlijks)')
    percentile_10th = df['debiet'].quantile(0.1)
    ax2.axhline(y=percentile_10th, color=red, linestyle='--', alpha=0.6, linewidth=2,
                    label=f'10e Percentiel = {percentile_10th:.3f}'.replace('.', ',') + ' m³/s')

    # Axis labels
    ax1.set_ylabel('Watertemperatuur [°C]', fontsize=fontsize-2)
    ax2.set_title('Debiet', size=fontsize-2)
    ax2.set_xlabel('Datum', fontsize=fontsize-2)
    ax2.set_ylabel('Debiet [m³/s]', fontsize=fontsize-2)
    ax2.set_ylim(0,  np.max(df['debiet']))

    # Shade draaiseizoen
    if draaiseizoen_shade:
        df_shade = df.reset_index()
        legend_added = False
        for i in range(len(df_shade)):
            if df_shade['Above_Threshold'][i] == 1:
                ax1.axvspan(date2num(df_shade['DateTime'][i]), date2num(df_shade['DateTime'][i] + pd.Timedelta(hours=1)),
                            color='black', alpha=0.005, label='Draaiseizoen' if not legend_added else None)
                ax2.axvspan(date2num(df_shade['DateTime'][i]), date2num(df_shade['DateTime'][i] + pd.Timedelta(hours=1)),
                                color='black', alpha=0.005, label='Draaiseizoen' if not legend_added else None)
                legend_added = True
        # Adjust legend alpha
        handles, labels = ax1.get_legend_handles_labels()
        for handle, label in zip(handles, labels):
            if label == 'Draaiseizoen':
                handle.set_alpha(0.2)

    # Add horizontal lines
    if isinstance(min_loz, int):
        ax1.hlines(y=min_loz, xmin=start_date, xmax=end_date, alpha=0.9, ls='--',
                   label=f'Min. lozingstemperatuur {min_loz} °C', linewidth=1.5, color='green')
        ax1.hlines(y=threshold_temp, xmin=start_date, xmax=end_date, ls=':',
                   label=f'Min. innametemperatuur {threshold_temp} °C', linewidth=1.5, color='purple')
        ax1.fill_between(df.index, 0, threshold_temp, color=blue, alpha=0.1)

    # Format x-axis
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_minor_locator(mdates.MonthLocator())
    ax2.xaxis.set_minor_formatter(mdates.DateFormatter('%b'))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%b'))
    ax2.tick_params(axis='x', which='major', size=10, pad=5)
    ax2.tick_params(axis='y', which='major', size=10)
    ax2.tick_params(axis='x', which='minor', pad=10, rotation=90)
    ax2.grid(True, which='both', axis='x')
    ax2.grid(True, which='both', axis='y')
    plt.setp(ax2.get_xticklabels(which='major'), fontsize=fontsize-2, rotation=90, ha='left')
    plt.setp(ax2.get_xticklabels(which='minor'), fontsize=fontsize-2, rotation=90, ha='left')
    ax2.legend(fontsize=fontsize-2, markerscale=5, loc='upper left', ncol=2)
    ax1.tick_params(axis='y', which='minor', labelsize=fontsize-2)
    ax1.tick_params(axis='both', which='major', size=10, labelsize=fontsize-2)
    ax1.grid(True, which='both', axis='x')
    ax1.grid(True, which='both', axis='y')
    ax1.set_ylim(t_lim[0], t_lim[1])

    # Summary statistics
    avg_draaiuren = df[df['Draaiuren'] > 0].groupby(df.index.to_series().dt.year)['Draaiuren'].max().mean()
    avg_delta_T_all_years = df.groupby(df.index.year)['Yearly_Avg_delta_T'].mean().mean()
    avg_bron = df['Average_bron'].mean()
    debiet_inschatting = percentile_10th * 0.1 #m3/s
    
    # deb = debiet_inschatting * 3600 
    
    dt = avg_delta_T_all_years
    
    W =  debiet_inschatting * 998  * 4185 * dt #mass and thermal  W

    MWH =  avg_draaiuren / (1 + maintenance_factor) * W / 10**6 #KW

    # MWH = round(MWH / 500) * 500

    plot_type = 'TEO'
    text = "voor regeneratie "

    if len(set(min_loz)) == 1:
        min_loz_text = f"Min. lozingstemperatuur: {min_loz[0]} °C"
    else:
        min_loz_text = "Min. lozingstemperatuur: 2 °C"

    results_data = {
        "Plot Type": [plot_type],
        "ΔT max (Kelvin)": [delta_T],
        "Min. Lozingstemperatuur": [min_loz_text],
        "Gem. aantal draaiuren": [avg_draaiuren],
        "Ontwerp draaiuren": [avg_draaiuren / (1 + maintenance_factor)],
        "Gem. ΔT (Kelvin)": [avg_delta_T_all_years],
        "Gem. innametemperatuur (°C)": [avg_bron]
        # "E (MWh/jaar)": [MWH]
    }

    results_df = pd.DataFrame(results_data)

    # text_content = (
    #     f"$\\bf{{{plot_type}}} $ " + '\n'
    #     f"$\\bf{{Uitgangspunten   }} $" + '\n' 
    #     f"ΔT max: {delta_T} Kelvin\n"
    #     f"{min_loz_text}\n\n"
    #     f"$\\mathbf{{Resultaten}}$" + '\n'
    #     f"Gem. aantal draaiuren = {avg_draaiuren:,.0f}".replace(',', '.') + '\n'
    #     f"Ontwerp draaiuren = {avg_draaiuren / (1 + maintenance_factor):,.0f}".replace(',', '.') + '\n'
    #     "Gem. ΔT = " + f"{avg_delta_T_all_years:.2f}".replace('.', ',') + " Kelvin" + '\n'
    #     "Gem. innametemperatuur = " + f"{avg_bron:.2f}".replace('.', ',') + " °C"
    # )

    # if MWH is not None:
    #     text_content += "\nQ =" + f"{debiet_inschatting:.2f}"
    #     + "m3/s  (op basis van" + f"{avg_draaiuren/(1 + maintenance_factor):.0f}".replace(',', '.') 
    #     + " uur en dT = "+ f"{avg_delta_T_all_years:.2f})".replace(',', '.')
    #     +  f"E = {MWH:.0f} MWh (jaarlijks)".replace(',', '.')

    # if not alleen_temp:
    #     fig.text(0.88, 0.90, text_content, fontsize=fontsize - 2,
    #              bbox=dict(facecolor='k', alpha=0.1, edgecolor='black'), ha='center')


    # Basis tekstinhoud opbouwen
    text_content = (
        f"$\\bf{{{plot_type}}}$\n"
        f"$\\bf{{Uitgangspunten}}$\n"
        f"ΔT max: {delta_T} Kelvin\n"
        f"{min_loz_text}\n\n"
        f"$\\mathbf{{Resultaten}}$\n"
        f"Gem. aantal draaiuren = {avg_draaiuren:,.0f}".replace(',', '.') + "\n"
        f"Ontwerp draaiuren = {(avg_draaiuren / (1 + maintenance_factor)):,.0f}".replace(',', '.') + "\n"
        "Gem."+f"ΔT = {avg_delta_T_all_years:.2f}".replace('.', ',') + " Kelvin\n"
        "Gem."+f" innametemperatuur = {avg_bron:.2f}".replace('.', ',') + " °C"
    )
    
    # Optionele toevoeging van Q en E
    # if MWH is not None:
    #     q = f"{debiet_inschatting:.2f}"
    #     draaiuren = f"{avg_draaiuren / (1 + maintenance_factor):,.0f}".replace(',', '.')
    #     dT = f"{avg_delta_T_all_years:.2f}".replace(',', '.')
    #     energie = f"{MWH:.0f}".replace(',', '.')
    #     text_content += (
    #         f"\nQ = {q} m3/s  (op basis van bovenstaande):\n"
    #         f"E = {energie} MWh (jaarlijks)"
    #     )
    
    # Toevoegen aan matplotlib figuur
    if not alleen_temp:
        fig.text(
            0.88, 0.90, text_content,
            fontsize=fontsize - 2,
            bbox=dict(facecolor='k', alpha=0.1, edgecolor='black'),
            ha='center'
        )




    ax1.legend(loc='upper left', fontsize=fontsize-2, ncol=2)
    # add_logo(fig, zoom=0.01, logo_path=logopath, position=(0.1, 0.98))

    # add_logo(fig, logopath, position=(0.1, 0.98), zoom=0.005)
    fig.tight_layout()
    return fig, ax1, ax2, results_data


import matplotlib.pyplot as plt

# Expect that colors 'red' and 'blue' are defined somewhere in your module, e.g.:
# red = '#d62728'
# blue = '#1f77b4'

def plot_monthly_temperature_debiet_v2(
    df_final, start_date, end_date, delta_T, min_loz, min_dif, threshold_temp,
    maintenance_factor, titel='naam',
    fontsize=15, t_lim=[0, 30],
    draaiseizoen_shade=True, wko=True, s1=10, s2=10,
    mode="standaard", auto_mode=None, auto_values=None
    ):
    
    """
    Plots water temperature and flow rate data with optionele tekstbox afhankelijk van modus.

    Parameters
    ----------
    ----------
    delta_T : float OR list-like(12) OR dict
        - Scalar: single ΔT cap; labels show that scalar.
        - List/tuple/np.ndarray/pd.Series: 12 monthly ΔT values (Jan..Dec).
        - Dict: keys 1..12 or "Jan".."Dec" to ΔT values.
    min_loz : int OR list-like(12)
        - Scalar: single minimum lozing temperature (draws horizontal line).
        - List-like 12: monthly minima; label summarizes (equal value or min–max).

    mode : str
        'standaard', 'uitgebreid', of 'automatic'
    auto_mode : str
        Naam van automatische modus (alleen bij mode='automatic')
    auto_values : tuple
        Waarden voor automatische modus (alleen bij mode='automatic')
        
    """
    
    # ---------------------------
    # Helpers for flexible inputs
    # ---------------------------
    
    months_short = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
    
    def to_month_map_12(x):
        """Return ({1..12: float}, is_scalar, scalar_value_or_None)."""
        if np.isscalar(x):
            return None, True, float(x)
        if isinstance(x, (list, tuple, np.ndarray, pd.Series)):
            if len(x) != 12:
                raise ValueError("Monthly value must have length 12 (Jan..Dec).")
            return {i+1: float(x[i]) for i in range(12)}, False, None
        if isinstance(x, dict):
            # allow 1..12 or month names
            if all(k in range(1, 13) for k in x.keys()):
                return {int(k): float(v) for k, v in x.items()}, False, None
            name_to_idx = {m: i+1 for i, m in enumerate(months_short)}
            if all(str(k) in name_to_idx for k in x.keys()):
                return {name_to_idx[str(k)]: float(v) for k, v in x.items()}, False, None
            raise ValueError("Dict keys must be 1..12 or month names 'Jan'..'Dec'.")
        raise TypeError("Value must be scalar, 12-long list-like, or dict keyed by months.")

    def summarize_deltaT_for_label(delta_T_input):
        """Return (label_text, scalar_for_table_or_str) for results/annotation."""
        m, is_scalar, scalar = to_month_map_12(delta_T_input)
        if is_scalar:
            # Nice formatting (no trailing .0 if integer)
            s = int(scalar) if float(scalar).is_integer() else float(scalar)
            return f"{s}", s
        # monthly
        vals = np.array([m[i] for i in range(1, 13)], dtype=float)
        avg = vals.mean()
        vmin, vmax = vals.min(), vals.max()
        # concise human-readable label
        label = f"variabel per maand (gem. {avg:.2f} K; min {vmin:g} – max {vmax:g})"
        # for results table, store a short summary string
        return label, label

    def summarize_min_loz_for_label(min_loz_input):
        """Return a user-friendly description for min_loz in the text box / table."""
        if np.isscalar(min_loz_input):
            s = int(min_loz_input) if float(min_loz_input).is_integer() else float(min_loz_input)
            return f"Min. lozingstemperatuur: {s} °C"
        # list-like monthly
        arr = np.array(min_loz_input, dtype=float)
        if arr.size != 12:
            return "Min. lozingstemperatuur: per maand (ongeldig formaat)"
        if np.allclose(arr, arr[0]):
            s = int(arr[0]) if float(arr[0]).is_integer() else float(arr[0])
            return f"Min. lozingstemperatuur: {s} °C"
        return f"Min. lozingstemperatuur: per maand (min {arr.min():g} – max {arr.max():g} °C)"

    # --------------------------------
    # Prepare data (unchanged plotting)
    # --------------------------------
    df = df_final.copy()
    df_day = df.resample('D').mean()
    df_month_rolling = df_day.select_dtypes(include='number').rolling(window=30, center=True, min_periods=1).mean()
    df_month = df_day.resample('M').mean()
    df_month.index = pd.to_datetime(df_month.index).to_period('M').start_time

    # Create figure and axes
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(s1, s2), sharex=True)
    fig.suptitle(
        f'\n Analyse watertemperatuur, draaiuren en debiet\n{titel}',
        fontsize=fontsize,
        x=0.45,
        ha='center',
        weight='bold'
    )
    ax1.set_title('Watertemperatuur', size=fontsize-2)

    # Plot temperature data
    ax1.scatter(df.index, df['temperatuur'], s=0.5, alpha=1, label='Gemeten watertemperatuur')
    ax1.plot(df_month_rolling['temperatuur'], color=red, lw=1.5, label='Maandelijks gemiddelde')
    df['Lozingstemperatuur'].plot(ax=ax1, label='Lozingstemperatuur', linestyle='-', color='g', linewidth=1.5)

    # Annotaties per jaar (alleen als meerdere jaren)
    years = df.index.year.unique()
    if len(years) > 1:
        for year, group in df.groupby(df.index.year):
            max_draaiuren = group['Draaiuren'].max()
            avg_delta_T = group['Yearly_Avg_delta_T'].mean()
            if max_draaiuren > 0:
                max_date = group['Draaiuren'].idxmax()
                ax1.text(
                    max_date - pd.Timedelta(days=120),
                    0.5,
                    f"{year}\nDraaiuren {max_draaiuren:,.0f}".replace(',', '.') +
                    "\nGem. ΔT: " + f"{avg_delta_T:.2f}".replace('.', ',') + " Kelvin",
                    fontsize=fontsize - 3,
                    ha='center',
                    va='bottom',
                    bbox=dict(facecolor='white', alpha=0.8)
                )

    # Plot discharge data
    ax2.scatter(df.index, df['debiet'], alpha=0.5, color=blue, s=1, label='Gemeten (uurlijks)')
    percentile_10th = df['debiet'].quantile(0.1)
    ax2.axhline(
        y=percentile_10th, color=red, linestyle='--', alpha=0.6, linewidth=2,
        label=f'10e Percentiel = {percentile_10th:.3f}'.replace('.', ',') + ' m³/s'
    )

    # Axis labels
    ax1.set_ylabel('Watertemperatuur [°C]', fontsize=fontsize-2)
    ax2.set_title('Debiet', size=fontsize-2)
    ax2.set_xlabel('Datum', fontsize=fontsize-2)
    ax2.set_ylabel('Debiet [m³/s]', fontsize=fontsize-2)
    ax2.set_ylim(0,  np.max(df['debiet']))

    # Shade draaiseizoen (robust to index name)
    if draaiseizoen_shade:
        df_shade = df.reset_index()
        dt_col = df.index.name or 'index'  # the reset_index() column for datetime
        legend_added = False
        for i in range(len(df_shade)):
            if df_shade.get('Above_Threshold', pd.Series([0]*len(df_shade))).iloc[i] == 1:
                start_t = df_shade.loc[i, dt_col]
                end_t = start_t + pd.Timedelta(hours=1)
                ax1.axvspan(date2num(start_t), date2num(end_t),
                            color='black', alpha=0.005,
                            label='Draaiseizoen' if not legend_added else None)
                ax2.axvspan(date2num(start_t), date2num(end_t),
                            color='black', alpha=0.005,
                            label='Draaiseizoen' if not legend_added else None)
                legend_added = True
        # Adjust legend alpha
        handles, labels = ax1.get_legend_handles_labels()
        for handle, label in zip(handles, labels):
            if label == 'Draaiseizoen':
                handle.set_alpha(0.2)

    # Horizontal lines only when scalar inputs (to keep visuals simple)
    if np.isscalar(min_loz):
        ax1.hlines(y=min_loz, xmin=start_date, xmax=end_date, alpha=0.9, ls='--',
                   label=f'Min. lozingstemperatuur {min_loz} °C', linewidth=1.5, color='green')
    if np.isscalar(threshold_temp):
        ax1.hlines(y=threshold_temp, xmin=start_date, xmax=end_date, ls=':',
                   label=f'Min. innametemperatuur {threshold_temp} °C', linewidth=1.5, color='purple')
        ax1.fill_between(df.index, 0, threshold_temp, color=blue, alpha=0.1)

    # Format x-axis
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_minor_locator(mdates.MonthLocator())
    ax2.xaxis.set_minor_formatter(mdates.DateFormatter('%b'))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%b'))
    ax2.tick_params(axis='x', which='major', size=10, pad=5)
    ax2.tick_params(axis='y', which='major', size=10)
    ax2.tick_params(axis='x', which='minor', pad=10, rotation=90)
    ax2.grid(True, which='both', axis='x')
    ax2.grid(True, which='both', axis='y')
    plt.setp(ax2.get_xticklabels(which='major'), fontsize=fontsize-2, rotation=90, ha='left')
    plt.setp(ax2.get_xticklabels(which='minor'), fontsize=fontsize-2, rotation=90, ha='left')
    ax2.legend(fontsize=fontsize-2, markerscale=5, loc='upper left', ncol=2)
    ax1.tick_params(axis='y', which='minor', labelsize=fontsize-2)
    ax1.tick_params(axis='both', which='major', size=10, labelsize=fontsize-2)
    ax1.grid(True, which='both', axis='x')
    ax1.grid(True, which='both', axis='y')
    ax1.set_ylim(t_lim[0], t_lim[1])
  
    # -------------------
    # Summary statistics
    # -------------------
    avg_draaiuren = df[df['Draaiuren'] > 0].groupby(df.index.to_series().dt.year)['Draaiuren'].max().mean()
    avg_delta_T_all_years = df.groupby(df.index.year)['Yearly_Avg_delta_T'].mean().mean()
    avg_bron = df['Average_bron'].mean()
    percentile_10th = df['debiet'].quantile(0.1)

    # Tekst voor standaard en automatic
    if mode == "standaard":
        deltaT_label_text, _ = summarize_deltaT_for_label(delta_T)
        min_loz_text = summarize_min_loz_for_label(min_loz)
        text_content = (
            f"$\\bf{{TEO}}$\n"
            f"$\\bf{{Uitgangspunten}}$\n"
            f"ΔT max: {deltaT_label_text}\n"
            f"{min_loz_text}\n\n"
            f"$\\mathbf{{Resultaten}}$\n"
            f"Gem. draaiuren = {avg_draaiuren:,.0f}".replace(',', '.') + "\n"
            f"Ontwerp draaiuren = {(avg_draaiuren / (1 + maintenance_factor)):,.0f}".replace(',', '.') + "\n"
            f"Gem. ΔT = {avg_delta_T_all_years:.2f}".replace('.', ',') + " K\n"
            f"Gem. innametemp = {avg_bron:.2f}".replace('.', ',') + " °C"
        )

    elif mode == "automatic":
        # Toon naam van automatische modus en waarden
        auto_text = f"Modus: {auto_mode}\nΔT waarden: ≥ 16°C={auto_values[0]} | 10–16 °C={auto_values[1]} | 2–10 °C={auto_values[2]}"
        text_content = (
            f"$\\bf{{TEO}}$\n"
            f"$\\bf{{Automatisch}}$\n"
            f"{auto_text}\n\n"
            f"$\\mathbf{{Resultaten (gemiddeld)}}$\n"
            f"Draaiuren = {avg_draaiuren:,.0f}".replace(',', '.') + "\n"
            f"ΔT = {avg_delta_T_all_years:.2f}".replace('.', ',') + " K\n"
            f"Innametemp = {avg_bron:.2f}".replace('.', ',') + " °C"
        )

    else:  # uitgebreid
        text_content = None  # Geen uitgangspunten tonen

    # Voeg tekstbox toe als nodig
    if text_content:
        fig.text(
            0.88, 0.90, text_content,
            fontsize=fontsize - 2,
            bbox=dict(facecolor='k', alpha=0.1, edgecolor='black'),
            ha='center'
        )

    ax1.legend(loc='upper left', fontsize=fontsize-2, ncol=2)
    fig.tight_layout()
    
    results_data = {
        "Gem. aantal draaiuren": [avg_draaiuren],
        "Ontwerp draaiuren": [avg_draaiuren / (1 + maintenance_factor)],
        "Gem. ΔT (Kelvin)": [avg_delta_T_all_years],
        "Gem. innametemperatuur (°C)": [avg_bron]
    # "E (MWh/jaar)": [MWH]
        }
    results_df = pd.DataFrame(results_data)
    return fig, ax1, ax2, results_df



def plot_monthly_temperature_v1(
    df_final, start_date, end_date, delta_T, min_loz, min_dif, threshold_temp,
    maintenance_factor, alleen_temp, titel='naam',
    fontsize=15, t_lim=[0, 30],
    draaiseizoen_shade=True, wko=True, s1=10, s2=10
):
    df = df_final.copy()
    df_day = df.resample('D').mean()
    df_month_rolling = df_day.select_dtypes(include='number').rolling(window=30, center=True, min_periods=1).mean()
    df_month = df_day.resample('M').mean()
    df_month.index = pd.to_datetime(df_month.index).to_period('M').start_time

    # Detect scalar vs monthly ΔT
    months_short = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
    def to_month_map_12(x):
        if np.isscalar(x):
            return None, True, float(x)
        if isinstance(x, (list, tuple, np.ndarray, pd.Series)):
            if len(x) != 12:
                raise ValueError("delta_T list-like must have length 12.")
            return {i+1: float(x[i]) for i in range(12)}, False, None
        if isinstance(x, dict):
            if all(k in range(1, 13) for k in x.keys()):
                return {int(k): float(v) for k, v in x.items()}, False, None
            name_to_idx = {m: i+1 for i, m in enumerate(months_short)}
            if all(str(k) in name_to_idx for k in x.keys()):
                return {name_to_idx[str(k)]: float(v) for k, v in x.items()}, False, None
            raise ValueError("delta_T dict keys must be 1..12 or month names.")
        raise TypeError("delta_T must be scalar, list(12), or dict.")
    deltaT_map, is_scalar, scalar_val = to_month_map_12(delta_T)

    # Create figure
    fig, ax1 = plt.subplots(1, 1, figsize=(s1, s2))
    fig.suptitle(f'\n Analyse watertemperatuur en draaiuren\n{titel}',
                 fontsize=fontsize, x=0.5, ha='center', weight='bold')
    ax1.set_title('Watertemperatuur', size=fontsize-2)

    # Plot temperature data
    ax1.scatter(df.index, df['temperatuur'], s=0.5, alpha=1, label='Gemeten watertemperatuur')
    ax1.plot(df_month_rolling['temperatuur'], color='red', lw=1.5, label='Maandelijks gemiddelde')
    df['Lozingstemperatuur'].plot(ax=ax1, label='Lozingstemperatuur', linestyle='-', color='g', linewidth=1.5)

    # # Add ΔT lines
    # if is_scalar:
    #     ax1.axhline(y=scalar_val, xmin=start_date, xmax=end_date, color='orange', ls='--',
    #                 label=f"ΔT max: {scalar_val} K")
    # else:
    #     # Draw per-month segments
    #     for month, val in deltaT_map.items():
    #         # Get start and end of this month in the data range
    #         month_start = pd.Timestamp(year=df.index.min().year, month=month, day=1)
    #         month_end = month_start + pd.offsets.MonthEnd(0)
    #         # Clip to plot range
    #         if month_end < start_date or month_start > end_date:
    #             continue
    #         x_start = max(month_start, start_date)
    #         x_end = min(month_end, end_date)
    #         ax1.hlines(y=val, xmin=x_start, xmax=x_end, color='orange', lw=2, alpha=0.7)
    #     ax1.plot([], [], color='orange', lw=2, label='ΔT per maand')

    # Horizontal lines for min_loz and threshold
    if np.isscalar(min_loz):
        ax1.hlines(y=min_loz, xmin=start_date, xmax=end_date, ls='--', color='green',
                   label=f'Min. lozingstemperatuur {min_loz} °C')
    if np.isscalar(threshold_temp):
        ax1.hlines(y=threshold_temp, xmin=start_date, xmax=end_date, ls=':', color='purple',
                   label=f'Min. innametemperatuur {threshold_temp} °C')
        ax1.fill_between(df.index, 0, threshold_temp, color='blue', alpha=0.1)

    if scalar_val is not None and np.isfinite(float(scalar_val)):
        ax1.axhline(
            y=float(scalar_val),
            color='orange',
            ls='--',
            linewidth=0.8,
            label=f"ΔT max: {float(scalar_val):.1f} K",
        )
    else:
        # Draw per-month segments
        for month, val in deltaT_map.items():
            # Get start and end of this month in the data range
            month_start = pd.Timestamp(year=df.index.min().year, month=month, day=1)
            month_end = month_start + pd.offsets.MonthEnd(0)
            # Clip to plot range
            if month_end < start_date or month_start > end_date:
                continue
            x_start = max(month_start, start_date)
            x_end = min(month_end, end_date)
            ax1.hlines(y=val, xmin=x_start, xmax=x_end, color='orange', lw=2, alpha=0.7)
        ax1.plot([], [], color='orange', lw=2, label='ΔT per maand')

    # Format axes
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_minor_locator(mdates.MonthLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%b'))
    ax1.xaxis.set_minor_formatter(mdates.DateFormatter('%b'))
    plt.setp(ax1.get_xticklabels(which='major'), fontsize=fontsize-2, rotation=90)
    ax1.set_ylim(t_lim)
    
    
    # if scalar_val is not None and np.isfinite(float(scalar_val)):
    #     x_min, x_max = ax1.get_xlim()  # data coords (numbers, even for datetime axis)
    #     ax1.hlines(
    #         y=float(scalar_val), xmin=x_min, xmax=x_max,
    #         colors='orange', linestyles='--', linewidth=0.8,
    #         label=f"ΔT max: {float(scalar_val):.1f} K",
    #     )
    # else:
    #     # Draw per-month segments
    #     for month, val in deltaT_map.items():
    #         # Get start and end of this month in the data range
    #         month_start = pd.Timestamp(year=df.index.min().year, month=month, day=1)
    #         month_end = month_start + pd.offsets.MonthEnd(0)
    #         # Clip to plot range
    #         if month_end < start_date or month_start > end_date:
    #             continue
    #         x_start = max(month_start, start_date)
    #         x_end = min(month_end, end_date)
    #         ax1.hlines(y=val, xmin=x_start, xmax=x_end, color='orange', lw=2, alpha=0.7)
    #     ax1.plot([], [], color='orange', lw=2, label='ΔT per maand')

    ax1.grid(True)

    # Summary stats
    avg_draaiuren = df[df['Draaiuren'] > 0].groupby(df.index.year)['Draaiuren'].max().mean()
    avg_delta_T_all_years = df.groupby(df.index.year)['Yearly_Avg_delta_T'].mean().mean()
    avg_bron = df['Average_bron'].mean()

    # ΔT label for text
    if is_scalar:
        deltaT_label = f"{scalar_val} K"
    else:
        vals = np.array(list(deltaT_map.values()))
        deltaT_label = f"variabel per maand (gem. {vals.mean():.2f} K; min {vals.min()} – max {vals.max()})"

    text_content = (
        f"$\\bf{{TEO}}$\n"
        f"$\\bf{{Uitgangspunten}}$\n"
        f"ΔT max: {deltaT_label}\n"
        f"Aantal draaiuren = {avg_draaiuren:,.0f}".replace(',', '.') + "\n"
        f"ΔT gem = {avg_delta_T_all_years:.2f}".replace('.', ',') + " K\n"
        f"Innametemperatuur gem = {avg_bron:.2f}".replace('.', ',') + " °C"
    )
    if not alleen_temp:
        fig.text(0.88, 0.90, text_content, fontsize=fontsize-2,
                 bbox=dict(facecolor='k', alpha=0.1, edgecolor='black'), ha='center')

    ax1.legend(loc='upper left', fontsize=fontsize-2)
    fig.tight_layout()
    return fig, ax1




def plot_monthly_temperature_v2(
    df_final, start_date, end_date, delta_T, min_loz, min_dif, threshold_temp,
    maintenance_factor, alleen_temp, titel='naam',
    fontsize=15, t_lim=[0, 30],
    draaiseizoen_shade=True, wko=True, s1=10, s2=10
):
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    # -----------------------------
    # Ensure datetime index
    # -----------------------------
    df = df_final.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
            df = df.set_index("datetime")
            df = df[~df.index.isna()]
        else:
            raise ValueError("df_final must have a DatetimeIndex or a 'datetime' column.")

    # -----------------------------
    # Daily + rolling month
    # -----------------------------
    df_day = df.resample('D').mean()
    df_month_rolling = df_day.select_dtypes(include='number').rolling(
        window=30, center=True, min_periods=1
    ).mean()

    # Monthly mean (for plotting)
    df_month = df_day.resample('M').mean()
    df_month.index = pd.to_datetime(df_month.index).to_period('M').start_time

    # -----------------------------
    # ΔT input → scalar or monthly map
    # -----------------------------
    months_short = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
                    "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]

    def to_month_map_12(x):
        """Return: (month_map, is_scalar, scalar_val)"""
        if np.isscalar(x):
            return None, True, float(x)

        if isinstance(x, (list, tuple, np.ndarray, pd.Series)):
            if len(x) != 12:
                raise ValueError("delta_T list-like must have length 12.")
            return {i+1: float(x[i]) for i in range(12)}, False, None

        if isinstance(x, dict):
            # numeric keys 1..12
            if all(k in range(1,13) for k in x.keys()):
                return {int(k): float(v) for k,v in x.items()}, False, None

            # month name keys
            name_to_idx = {m: i+1 for i,m in enumerate(months_short)}
            if all(str(k) in name_to_idx for k in x.keys()):
                return {name_to_idx[str(k)]: float(v) for k,v in x.items()}, False, None

            raise ValueError("delta_T dict keys must be 1..12 or month names.")

        raise TypeError("delta_T must be scalar, list(12) or dict.")

    deltaT_map, is_scalar, scalar_val = to_month_map_12(delta_T)

    # -----------------------------
    # Set up figure
    # -----------------------------
    fig, ax1 = plt.subplots(1, 1, figsize=(s1, s2))
    fig.suptitle(
        f"\nAnalyse watertemperatuur en draaiuren\n{titel}",
        fontsize=fontsize, x=0.5, ha='center', weight='bold'
    )
    ax1.set_title("Watertemperatuur", size=fontsize-2)

    # -----------------------------
    # Plot temperature data
    # -----------------------------
    ax1.scatter(df.index, df['temperatuur'], s=0.5, alpha=1,
                label="Gemeten watertemperatuur")
    ax1.plot(df_month_rolling['temperatuur'], color='red', lw=1.5,
             label="Maandelijks gemiddelde")

    if "Lozingstemperatuur" in df.columns:
        df['Lozingstemperatuur'].plot(
            ax=ax1,
            label="Lozingstemperatuur",
            linestyle='-',
            color='g',
            linewidth=1.5
        )

    # -----------------------------
    # Min lozing / threshold temperature lines
    # Use full scale (not xmin=start_date)
    # -----------------------------
    x_min, x_max = ax1.get_xlim()

    if np.isscalar(min_loz):
        ax1.hlines(
            y=min_loz, xmin=x_min, xmax=x_max, ls='--', color='green',
            label=f"Min. lozingstemperatuur {min_loz} °C"
        )

    if np.isscalar(threshold_temp):
        ax1.hlines(
            y=threshold_temp, xmin=x_min, xmax=x_max, ls=':', color='purple',
            label=f"Min. innametemperatuur {threshold_temp} °C"
        )
        ax1.fill_between(
            df.index, 0, threshold_temp,
            color='blue', alpha=0.1
        )

    # -----------------------------
    # ΔT Lines (scalar or monthly)
    # -----------------------------
    if is_scalar:
        if scalar_val is not None and np.isfinite(scalar_val):
            ax1.hlines(
                y=scalar_val,
                xmin=x_min, xmax=x_max,
                colors='orange',
                linestyles='--',
                linewidth=1.2,
                label=f"ΔT max: {scalar_val:.1f} K"
            )
    else:
        # monthly segments
        for month, val in deltaT_map.items():
            # compute real dates
            for year in range(df.index.min().year, df.index.max().year + 1):
                m_start = pd.Timestamp(year=year, month=month, day=1)
                m_end   = m_start + pd.offsets.MonthEnd(0)

                # clip to visible range:
                if m_end < start_date or m_start > end_date:
                    continue

                xs = max(m_start, start_date)
                xe = max(xs, min(m_end, end_date))
                ax1.hlines(
                    y=val, xmin=xs, xmax=xe,
                    color='orange', lw=1.5, alpha=0.8
                )
        ax1.plot([], [], color='orange', lw=2, label="ΔT per maand")

    # -----------------------------
    # X‑axis formatting
    # -----------------------------
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_minor_locator(mdates.MonthLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%b'))
    ax1.xaxis.set_minor_formatter(mdates.DateFormatter('%b'))

    plt.setp(ax1.get_xticklabels(which='major'),
             fontsize=fontsize-2, rotation=90)

    ax1.set_ylim(t_lim)
    ax1.grid(True)

    # -----------------------------
    # Summary statistics (robust fix!)
    # -----------------------------
    # Avoid groupby-length mismatch by using the filtered index
    if "Draaiuren" in df.columns:
        mask = df['Draaiuren'] > 0
        df_pos = df.loc[mask]

        if df_pos.empty:
            avg_draaiuren = 0.0
        else:
            avg_draaiuren = (
                df_pos['Draaiuren'].resample("Y").max().mean()
            )
    else:
        avg_draaiuren = 0.0

    if "Yearly_Avg_delta_T" in df.columns:
        avg_delta_T_all_years = df['Yearly_Avg_delta_T'].resample("Y").mean().mean()
    else:
        avg_delta_T_all_years = np.nan

    if "Average_bron" in df.columns:
        avg_bron = df['Average_bron'].mean()
    else:
        avg_bron = np.nan

    # -----------------------------
    # Text box (only if not temp-only)
    # -----------------------------
    if is_scalar:
        deltaT_label = f"{scalar_val} K"
    else:
        vals = np.array(list(deltaT_map.values()))
        deltaT_label = f"variabel (gem. {vals.mean():.2f} K; min {vals.min()} – max {vals.max()})"

    if not alleen_temp:
        text_content = (
            f"$\\bf{{TEO}}$\n"
            f"$\\bf{{Uitgangspunten}}$\n"
            f"ΔT max: {deltaT_label}\n"
            f"Aantal draaiuren = {avg_draaiuren:,.0f}".replace(",", ".") + "\n"
            f"ΔT gem = {avg_delta_T_all_years:.2f}".replace(".", ",") + " K\n"
            f"Innametemperatuur gem = {avg_bron:.2f}".replace(".", ",") + " °C"
        )

        fig.text(
            0.88, 0.90,
            text_content,
            fontsize=fontsize-2,
            bbox=dict(facecolor='k', alpha=0.1, edgecolor='black'),
            ha='center'
        )

    ax1.legend(loc='upper left', fontsize=fontsize-2)
    fig.tight_layout()
    results_data = {
        "Gem. aantal draaiuren": [avg_draaiuren],
        "Ontwerp draaiuren": [avg_draaiuren / (1 + maintenance_factor)],
        "Gem. ΔT (Kelvin)": [avg_delta_T_all_years],
        "Gem. innametemperatuur (°C)": [avg_bron]
    # "E (MWh/jaar)": [MWH]
        }
    results_df = pd.DataFrame(results_data)
    return fig, ax1, results_df
        
from PIL import Image

import matplotlib.pyplot as plt

def add_logo(fig, zoom, logo_path="assets/logo.png", position=(0.85, 0.85)):
    """
    Voeg een logo toe aan een matplotlib figuur met een zoomfactor.
    De positie is relatief ten opzichte van de volledige figuur (0.0 tot 1.0).
    Als het logo niet gevonden wordt, gebruik dan een fallback-logo.
    """
    if os.path.exists(logo_path):
        # Lees het logo in en pas zoom toe
        logo_img = Image.open(logo_path)
        width, height = logo_img.size
        new_size = (int(width * zoom), int(height * zoom))
        logo_img = logo_img.resize(new_size, Image.Resampling.LANCZOS)

        # Converteer naar numpy array
        logo_array = np.array(logo_img)

        # Bereken de positie op basis van de figuurgrootte
        fig_width, fig_height = fig.get_size_inches() * fig.dpi  # pixels
        logo_h, logo_w = logo_array.shape[:2]

        xo = int(fig_width * position[0]) - logo_w
        yo = int(fig_height * position[1]) - logo_h

        # Voeg het logo toe
        fig.figimage(
            logo_array,
            xo=xo,
            yo=yo,
            origin='upper',
            zorder=10
        )
    else:
        print("Bestaat bestand?", os.path.exists(logo_path))
        print(f"❌ Geen logo beschikbaar. Controleer pad: {logo_path}")
    # logo = mpimg.imread(logo_path)
    # ax_logo = fig.add_axes([position[0], position[1], zoom, zoom], anchor='NE', zorder=1)
    # ax_logo.imshow(logo)
    # ax_logo.axis('off')

    

