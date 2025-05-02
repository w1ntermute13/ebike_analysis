import pandas as pd
import numpy as np
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

default_voltage_bounds = (0, 70)
default_current_bounds = (0, 30)
default_temp_bounds = (0, 70)
default_torque_bounds = (0, 150)
default_expected_efficiency_max = 1.2

def make_json_serializable(obj):
    """Convert objects to JSON-serializable formats."""
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, (np.bool_)):
        return bool(obj)
    elif isinstance(obj, (np.ndarray, list, tuple)):
        return [make_json_serializable(o) for o in obj]
    elif isinstance(obj, (pd.Timestamp, pd.Timedelta)):
        return str(obj)
    elif pd.isna(obj):
        return None
    else:
        return obj

def basic_diagnostics(df, voltage_bounds=default_voltage_bounds, current_bounds=default_current_bounds,
                      temp_bounds=default_temp_bounds, torque_bounds=default_torque_bounds,
                      expected_efficiency_max=default_expected_efficiency_max):
    diagnostics = {}

    try:
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame.")

        required_columns = [
            'timestamp','batteryVoltage', 'batteryCurrent', 'batteryTemperatureCelsius',
            'torqueCrankNm', 'wheelPowerWatt', 'enginePowerWatt'
        ]
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"The following required columns are missing from the DataFrame: {missing_cols}")

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')

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
        else:
            logger.warning("Index is not a DatetimeIndex; skipping sampling rate check.")

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
        with np.errstate(divide='ignore', invalid='ignore'):
            df['efficiency'] = df['wheelPowerWatt'] / df['enginePowerWatt'].replace(0, np.nan)
            df['efficiency'] = df['efficiency'].replace([np.inf, -np.inf], np.nan).fillna(0)

        diagnostics["avg_efficiency"] = df['efficiency'].mean()
        diagnostics["max_efficiency"] = df['efficiency'].max()
        diagnostics["efficiency_over_limit"] = (df['efficiency'] > expected_efficiency_max).sum()

        # --- Additional Scalar Stats ---

        # 1. Total Energy Used (Wh)
        if isinstance(df.index, pd.DatetimeIndex):
            df['delta_seconds'] = df.index.to_series().diff().dt.total_seconds().fillna(0)
            df['instant_power_W'] = df['batteryVoltage'] * df['batteryCurrent']
            df['energy_Wh'] = (df['instant_power_W'] * df['delta_seconds']) / 3600
            diagnostics["total_energy_used_Wh"] = float(df['energy_Wh'].sum())
        else:
            logger.warning("DatetimeIndex is required to compute energy usage.")

        # 2. Peak Power Output (W)
        diagnostics["peak_power_output_W"] = float(df[['wheelPowerWatt', 'enginePowerWatt']].max().max())

        # 3. Max Temperature (°C)
        diagnostics["max_battery_temp_C"] = float(df['batteryTemperatureCelsius'].max())

        # --- Additional Scalar Stats ---

        # 1. Total Energy Used (Wh)
        if isinstance(df.index, pd.DatetimeIndex):
            df['delta_seconds'] = df.index.to_series().diff().dt.total_seconds().fillna(0)
            df['instant_power_W'] = df['batteryVoltage'] * df['batteryCurrent']
            df['energy_Wh'] = (df['instant_power_W'] * df['delta_seconds']) / 3600
            diagnostics["total_energy_used_Wh"] = float(df['energy_Wh'].sum())
        else:
            logger.warning("DatetimeIndex is required to compute energy usage.")

        # 2. Peak Power Output (W)
        diagnostics["peak_power_output_W"] = float(df[['wheelPowerWatt', 'enginePowerWatt']].max().max())

        # 3. Max Temperature (°C)
        diagnostics["max_battery_temp_C"] = float(df['batteryTemperatureCelsius'].max())


        # 5. Voltage present when current > 0
        diagnostics["current_without_voltage"] = df[
            (df['batteryCurrent'] > 0) & (df['batteryVoltage'] <= 0)
        ].shape[0]

        # Make diagnostics JSON-serializable
        diagnostics = {k: make_json_serializable(v) for k, v in diagnostics.items()}

    except Exception as e:
        logger.error("Error during diagnostics: %s", str(e), exc_info=True)
        raise

    return diagnostics
