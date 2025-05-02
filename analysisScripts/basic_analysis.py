default_voltage_bounds = (0,70)
default_current_bounds=(0, 30)
default_temp_bounds=(0, 70)
default_torque_bounds=(0, 150)
default_expected_efficiency_max=1.2

import pandas as pd
import numpy as np

def basic_diagnostics(df, voltage_bounds=default_voltage_bounds, current_bounds=default_current_bounds,
                           temp_bounds=default_temp_bounds, torque_bounds=default_torque_bounds, expected_efficiency_max=default_expected_efficiency_max):
    diagnostics = {}

    # 1. Signal Integrity Checks
    for col in df.select_dtypes(include='number').columns:
        diagnostics[f"{col}_missing_values"] = df[col].isna().sum()
        diagnostics[f"{col}_constant_value"] = df[col].nunique() <= 1
        diagnostics[f"{col}_inf_values"] = np.isinf(df[col]).sum()

    # 2. Sampling Rate Consistency (timestamp is the index)
    if isinstance(df.index, pd.DatetimeIndex):
        time_deltas = df.index.to_series().diff().dropna()
        diagnostics["irregular_sampling"] = time_deltas.value_counts().shape[0] > 1
        diagnostics["most_common_interval"] = time_deltas.value_counts().idxmax()

    # 3. Physical Bounds Checks
    diagnostics["voltage_out_of_bounds"] = df[
        (df['batteryVoltage'] < voltage_bounds[0]) | (df['batteryVoltage'] > voltage_bounds[1])
    ].shape[0]

    diagnostics["current_out_of_bounds"] = df[
        (df['batteryCurrent'] < current_bounds[0]) | (df['batteryCurrent'] > current_bounds[1])
    ].shape[0]

    diagnostics["temperature_out_of_bounds"] = df[
        (df['batteryTemperatureCelsius'] < temp_bounds[0]) | (df['batteryTemperatureCelsius'] > temp_bounds[1])
    ].shape[0]

    diagnostics["torque_out_of_bounds"] = df[
        (df['torqueCrankNm'] < torque_bounds[0]) | (df['torqueCrankNm'] > torque_bounds[1])
    ].shape[0]

    # 4. Efficiency Check
    df['efficiency'] = df['wheelPowerWatt'] / df['enginePowerWatt'].replace(0, np.nan)
    df['efficiency'] = df['efficiency'].replace([np.inf, -np.inf], np.nan).fillna(0)
    diagnostics["avg_efficiency"] = df['efficiency'].mean()
    diagnostics["max_efficiency"] = df['efficiency'].max()
    diagnostics["efficiency_over_limit"] = (df['efficiency'] > expected_efficiency_max).sum()

    # 5. Voltage present when current > 0
    diagnostics["current_without_voltage"] = df[
        (df['batteryCurrent'] > 0) & (df['batteryVoltage'] <= 0)
    ].shape[0]

    return diagnostics