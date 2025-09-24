import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# import matplotlib.dates as mdates
# from datetime import datetime
# from matplotlib.dates import MonthLocator, date2num
# import os
from matplotlib.colors import to_rgb
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

# from matplotlib.offsetbox import OffsetImage, AnnotationBbox

# Set the font to Tahoma
plt.rcParams['font.family'] = 'Tahoma'

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
        Hours=('Above_Threshold', 'sum'),
        Avg_del_T=('Temp_Difference', 'mean')
    ).reset_index()
    yearly_summary['Vollast_uren'] = (yearly_summary['Avg_del_T'] / delta_T) * yearly_summary['Hours']
    yearly_summary = yearly_summary.round({"Avg_del_T": 2, "Vollast_uren": 2})
    
    return df_hourly, monthly_summary, yearly_summary 




def add_logo(fig, logopath, position=(0.95, 0.95), zoom=0.05):
    """
    Add a logo to the plot.

    Parameters:
    fig (matplotlib.figure.Figure): The figure object to add the logo to.
    logo_path (str): Path to the logo image file.
    position (tuple): Position of the logo in figure coordinates (0 to 1).
    zoom (float): Zoom factor for the logo image.

    Returns:
        
    None
    """
    import matplotlib.image as mpimg

    logo = mpimg.imread(logopath)
    imagebox = OffsetImage(logo, zoom=zoom)
    ab = AnnotationBbox(imagebox, position, xycoords='figure fraction', frameon=False)
    fig.add_artist(ab)
    

logopath = r"C:\Users\JosinevanMarrewijk\Github\JADEtool\Afbeeldingen\logo VHGM.png"
fig, ax =  plt.subplots(figsize=(10, 4))
add_logo(fig, logopath)