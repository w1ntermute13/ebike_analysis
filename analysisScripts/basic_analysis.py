import pandas as pd
import numpy as np
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default bounds
DEFAULT_BOUNDS = {
    'batteryVoltage': (0, 70),
    'batteryCurrent': (0, 30),
    'batteryTemperatureCelsius': (0, 70),
    'torqueCrankNm': (0, 150)
}
DEFAULT_EFFICIENCY_MAX = 1.2


def make_json_serializable(obj):
    """Convert objects to JSON-serializable formats."""
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (np.ndarray, list, tuple)):
        return [make_json_serializable(o) for o in obj]
    if isinstance(obj, (pd.Timestamp, pd.Timedelta)):
        return str(obj)
    if pd.isna(obj):
        return None
    return obj


def check_constant_columns(df, bad_data_set):
    """Add columns with constant values to bad data set."""
    for col in df.select_dtypes(include='number').columns:
        if df[col].nunique() <= 1:
            bad_data_set.add(f"{col}_constant")


def check_missing_and_inf(df, bad_data_set):
    """Add columns with missing or infinite values to bad data set."""
    for col in df.select_dtypes(include='number').columns:
        if df[col].isna().any():
            bad_data_set.add(f"{col}_missing")
        if np.isinf(df[col]).any():
            bad_data_set.add(f"{col}_inf")


def check_bounds(df, bounds_dict, bad_data_set):
    """Add columns with values outside specified bounds to bad data set."""
    for col, (low, high) in bounds_dict.items():
        if ((df[col] < low) | (df[col] > high)).any():
            bad_data_set.add(f"{col}_out_of_bounds")


def check_current_without_voltage(df, bad_data_set):
    """Add flag for instances where current is present without voltage."""
    mask = (df['batteryCurrent'] > 0) & (df['batteryVoltage'] <= 0)
    if mask.any():
        bad_data_set.add('current_without_voltage')


def compute_efficiency(df):
    """Calculate efficiency column safely."""
    with np.errstate(divide='ignore', invalid='ignore'):
        efficiency = df['wheelPowerWatt'] / df['enginePowerWatt'].replace(0, np.nan)
        return efficiency.replace([np.inf, -np.inf], np.nan)


def compute_energy(df):
    """Compute total energy usage if timestamp index is valid."""
    if not isinstance(df.index, pd.DatetimeIndex):
        logger.warning("DatetimeIndex is required to compute energy usage.")
        return None

    df['delta_seconds'] = df.index.to_series().diff().dt.total_seconds().fillna(0)
    df['instant_power_W'] = df['batteryVoltage'] * df['batteryCurrent']
    df['energy_Wh'] = (df['instant_power_W'] * df['delta_seconds']) / 3600
    return float(df['energy_Wh'].sum())


def basic_diagnostics(df, bounds=DEFAULT_BOUNDS, expected_efficiency_max=DEFAULT_EFFICIENCY_MAX):
    """Perform basic diagnostics on e-bike sensor data."""
    diagnostics = {}

    try:
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame.")

        required_columns = [
            'timestamp', 'batteryVoltage', 'batteryCurrent', 'batteryTemperatureCelsius',
            'torqueCrankNm', 'wheelPowerWatt', 'enginePowerWatt'
        ]
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')

        bad_data_set = set()
        check_constant_columns(df, bad_data_set)
        check_missing_and_inf(df, bad_data_set)
        check_bounds(df, bounds, bad_data_set)
        check_current_without_voltage(df, bad_data_set)

        # Efficiency-based checks
        df['efficiency'] = compute_efficiency(df)
        if (df['efficiency'] > expected_efficiency_max).any():
            bad_data_set.add("efficiency_over_limit")

        diagnostics["BadData"] = sorted(bad_data_set)

        # Summary stats
        df['efficiency'] = df['efficiency'].fillna(0)
        diagnostics["avg_efficiency"] = df['efficiency'].mean()
        diagnostics["max_efficiency"] = df['efficiency'].max()

        # Energy stats
        total_energy = compute_energy(df)
        if total_energy is not None:
            diagnostics["total_energy_used_Wh"] = total_energy

        diagnostics["peak_power_output_W"] = float(df[['wheelPowerWatt', 'enginePowerWatt']].max().max())
        diagnostics["max_battery_temp_C"] = float(df['batteryTemperatureCelsius'].max())

        # Make all values JSON-serializable
        diagnostics = {k: make_json_serializable(v) for k, v in diagnostics.items()}

    except Exception as e:
        logger.error("Error during diagnostics: %s", str(e), exc_info=True)
        raise

    return diagnostics
