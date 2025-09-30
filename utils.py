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
# from matplotlib.offsetbox import OffsetImage, AnnotationBbox

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


        for col in df.columns:
            if col != 'DateTime':
                df[col] = pd.to_numeric(df[col], errors='coerce')
                # Outlier removal: z-score methode
                col_mean = df[col].mean()
                col_std = df[col].std()
                # Houd alleen waarden binnen 3 standaarddeviaties
                df = df[(df[col] - col_mean).abs() <= 10 * col_std]

        if 'DateTime' in df.columns:
            try:
                df['DateTime'] = pd.to_datetime(df['DateTime'], format='%d-%m-%Y %H:%M')
            except Exception:
                df['DateTime'] = pd.to_datetime(df['DateTime'], errors='coerce', dayfirst=True)
        else:
            raise ValueError(f"No valid datetime column in {file_type} file found, make sure name is 'DateTime'")

        df.set_index('DateTime', inplace=True)
        df = df.resample('H').mean()

        return df

    df_debiet = read_and_prepare(debiet_file, 'Debiet')
    df_temp = read_and_prepare(temperature_file, 'Temperature')
    df_temp.replace(-999, np.nan, inplace=True)    
    final_df = pd.merge(df_debiet, df_temp, left_index=True, right_index=True, how='outer')
    final_df.columns = ['debiet', 'temperatuur'] + list(final_df.columns[2:])

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

    df_hourly['Month'] = df_hourly.index.month
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
        Count=('Temp_Difference', 'size'),
        Draaiuren=('Above_Threshold', 'sum'),
        Gemiddelde_delta_T =('Temp_Difference', 'mean')
    ).reset_index()
    yearly_summary['Vollast_uren'] = (yearly_summary['Gemiddelde_delta_T'] / delta_T) * yearly_summary['Draaiuren']
    yearly_summary = yearly_summary.round({"Gemiddelde_delta_T": 2, "Vollast_uren": 0})
    
    return df_hourly, monthly_summary, yearly_summary 




def plot_monthly_temperature(
    df_final, start_date, end_date, delta_T, min_loz, min_dif, threshold_temp,
    maintenance_factor, alleen_temp, titel='naam', plot_debiet=True,
    logopath=None, fontsize=15, t_lim=[0, 30],
    draaiseizoen_shade=True, wko=True
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
    if plot_debiet:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 10), sharex=True)
        fig.suptitle(f'\n Analyse watertemperatuur, draaiuren en debiet\n\n{titel}', fontsize=fontsize+4)
        ax1.set_title('Watertemperatuur', size=fontsize-2)
    else:
        fig, ax1 = plt.subplots(1, 1, figsize=(15, 6))
        fig.suptitle(f'\n', fontsize=fontsize)
        ax1.set_title(f'Watertemperatuur {titel}', size=fontsize+2)

    # Plot temperature data
    ax1.scatter(df.index, df['temperatuur'], s=0.5, alpha=1, label='Gemeten watertemperatuur')
    ax1.plot(df_month_rolling['temperatuur'], color=red, lw=1.5, label='Maandelijks gemiddelde')
    df['Lozingstemperatuur'].plot(ax=ax1, label='Lozingstemperatuur', linestyle='-', color='g', linewidth=1.5)

    # Annotate draaiuren and delta T per year
    for year, group in df.groupby(df.index.year):
        max_draaiuren = group['Draaiuren'].max()
        avg_delta_T = group['Yearly_Avg_delta_T'].mean()
        if max_draaiuren > 0:
            max_date = group['Draaiuren'].idxmax()
            ax1.text(
                max_date - pd.Timedelta(days=120),
                0.5,
                f"{year}\nDraaiuren {max_draaiuren:,.0f}".replace(',', '.') + "\nGem. ΔT: " + f"{avg_delta_T:.2f}".replace('.', ',') + " Kelvin",
                fontsize=fontsize - 3,
                ha='center',
                va='bottom',
                bbox=dict(facecolor='white', alpha=0.8)
            )

    # Plot discharge data
    if plot_debiet:
        ax2.scatter(df.index, df['debiet'], alpha=0.5, color=blue, s=1, label='Gemeten (uurlijks)')
        percentile_10th = df['debiet'].quantile(0.1)
        ax2.axhline(y=percentile_10th, color=red, linestyle='--', alpha=0.6, linewidth=2,
                    label=f'10e Percentiel = {percentile_10th:.3f}'.replace('.', ',') + ' m³/s')

    # Axis labels
    ax1.set_ylabel('Watertemperatuur [°C]', fontsize=fontsize-2)
    if plot_debiet:
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
                if plot_debiet:
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
    if plot_debiet:
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
    else:
        ax1.xaxis.set_minor_formatter(mdates.DateFormatter('%b'))
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%b'))
        ax1.tick_params(axis='x', which='major', size=10, pad=5)
        ax1.tick_params(axis='y', which='major', size=10)
        ax1.tick_params(axis='x', which='minor', pad=10, rotation=90)
        plt.setp(ax1.get_xticklabels(which='major'), fontsize=fontsize-2, rotation=90, ha='left')
        plt.setp(ax1.get_xticklabels(which='minor'), fontsize=fontsize-2, rotation=90, ha='left')
        ax1.set_xlabel('Datum')

    ax1.tick_params(axis='y', which='minor', labelsize=fontsize-2)
    ax1.tick_params(axis='both', which='major', size=10, labelsize=fontsize-2)
    ax1.grid(True, which='both', axis='x')
    ax1.grid(True, which='both', axis='y')

    # Summary statistics
    avg_draaiuren = df[df['Draaiuren'] > 0].groupby(df.index.to_series().dt.year)['Draaiuren'].max().mean()
    avg_delta_T_all_years = df.groupby(df.index.year)['Yearly_Avg_delta_T'].mean().mean()
    avg_bron = df['Average_bron'].mean()

    MWH = None
    if plot_debiet:
        debiet_inschatting = percentile_10th * 0.1
        deb = debiet_inschatting * 3600
        MWH = avg_delta_T_all_years * avg_draaiuren / (1 + maintenance_factor) * deb * 4185 * 998 / 3600 / 10**6 
        MWH = round(MWH / 500) * 500

    plot_type = 'TEO'
    text = "(met wko) "

    if len(set(min_loz)) == 1:
        min_loz_text = f"Min. lozingstemperatuur: {min_loz[0]} °C"
    else:
        min_loz_text = "Min. lozingstemperatuur: verschilt per maand"

    results_data = {
        "Plot Type": [plot_type],
        "ΔT max (Kelvin)": [delta_T],
        "Min. Lozingstemperatuur": [min_loz_text],
        "Gem. aantal draaiuren": [avg_draaiuren],
        "Ontwerp draaiuren": [avg_draaiuren / (1 + maintenance_factor)],
        "Gem. ΔT (Kelvin)": [avg_delta_T_all_years],
        "Gem. innametemperatuur (°C)": [avg_bron],
        "E (MWh/jaar)": [MWH]
    }

    results_df = pd.DataFrame(results_data)

    text_content = (
        f"$\\bf{{{plot_type}}} $ " + " "
        f"$\\bf{{{text}}} $" + '\n'
        f"$\\bf{{Uitgangspunten   }} $" + '\n'
        f"ΔT max: {delta_T} Kelvin\n"
        f"{min_loz_text}\n\n"
        f"Gem. aantal draaiuren = {avg_draaiuren:,.0f}".replace(',', '.') + '\n'
        f"Ontwerp draaiuren = {avg_draaiuren / (1 + maintenance_factor):,.0f}".replace(',', '.') + '\n'
        "Gem. ΔT = " + f"{avg_delta_T_all_years:.2f}".replace('.', ',') + " Kelvin" + '\n'
        "Gem. innametemperatuur = " + f"{avg_bron:.2f}".replace('.', ',') + " °C"
    )

    if MWH is not None:
        text_content += f"\nQ = {debiet_inschatting:.0f} m3/s (op basis van {avg_draaiuren:.0f} uur en dT = {avg_delta_T_all_years:.2f}"
        text_content += f"\nE = {MWH:,.3f} MWh (jaarlijks)".replace(',', '.')

    if not alleen_temp:
        fig.text(0.88, 0.90, text_content, fontsize=fontsize - 2,
                 bbox=dict(facecolor='k', alpha=0.1, edgecolor='black'), ha='center')

    ax1.legend(loc='upper left', fontsize=fontsize-2, ncol=2)

    add_logo(fig, logopath, position=(0.12, 0.98), zoom=0.05)

    fig.tight_layout()
    


        
def add_logo(fig, logo_path="assets/logo.png", position=(0.85, 0.85), zoom=0.1):
    """
    Voeg een logo toe aan een matplotlib figuur.
    Als het logo niet gevonden wordt, gebruik dan een fallback-logo.
    """
    # Controleer of het opgegeven logo bestaat

    
    
    if os.path.exists(logo_path):
        logo_img = mpimg.imread(logo_path)
        fig.figimage(logo_img, xo=int(fig.bbox.xmax * position[0]), yo=int(fig.bbox.ymax * position[1]), origin='upper', zorder=10, resize=True)
    else:
        print("Bestaat bestand?", os.path.exists(logo_path))
        print(f"❌ Geen logo beschikbaar. Controleer pad: {logo_path}")
        return  # Stop zonder fout

    # logo = mpimg.imread(logo_path)
    # ax_logo = fig.add_axes([position[0], position[1], zoom, zoom], anchor='NE', zorder=1)
    # ax_logo.imshow(logo)
    # ax_logo.axis('off')

    

