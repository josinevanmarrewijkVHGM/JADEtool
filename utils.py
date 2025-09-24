import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# import matplotlib.dates as mdates
# from datetime import datetime
# from matplotlib.dates import MonthLocator, date2num
# import os
from matplotlib.colors import to_rgb
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
    print(df_debiet)
    print(df_temp)

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