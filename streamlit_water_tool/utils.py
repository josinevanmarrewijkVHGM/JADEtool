import pandas as pd

def load_data(temp_file, discharge_file):
    temp_df = pd.read_csv(temp_file)
    discharge_df = pd.read_csv(discharge_file)
    return temp_df, discharge_df

def calculate_output(temp_df, discharge_df, threshold):
    # Example logic: filter and merge
    temp_filtered = temp_df[temp_df['temperature'] > threshold]
    merged = pd.merge(temp_filtered, discharge_df, on='timestamp')
    return merged
