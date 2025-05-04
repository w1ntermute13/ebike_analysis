import pandas as pd
import numpy as np
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default bounds and thresholds
DEFAULT_BOUNDS = {
    'batteryVoltage': (0, 70),
    'batteryCurrent': (0, 30),
    'batteryTemperatureCelsius': (0, 70),
    'torqueCrankNm': (0, 150)
}
DEFAULT_EFFICIENCY_MAX = 1.2

DEFAULT_VISUAL = pd.Series({
    "promised_motor_power": 350,
    "promised_torque": 70,
    "promised_wheel_power": 320,
    "promised_battery_capacity_Wh": 500,
    "promised_temperature_deviation": 40,
    "horizontal_vibration_threshold": 2.0,
    "vertical_vibration_threshold": 1.5
})



def round_and_make_json_serializable(obj):
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        return round(float(obj), 2)
    if isinstance(obj, float):
        return round(obj, 2)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (np.ndarray, list, tuple)):
        return [round_and_make_json_serializable(o) for o in obj]
    if isinstance(obj, (pd.Timestamp, pd.Timedelta)):
        return str(obj)
    if pd.isna(obj):
        return None
    return obj


def compute_efficiency(df):
    with np.errstate(divide='ignore', invalid='ignore'):
        eff = df['wheelPowerWatt'] / df['enginePowerWatt'].replace(0, np.nan)
        return eff.replace([np.inf, -np.inf], np.nan)


def compute_energy(df):
    if not isinstance(df.index, pd.DatetimeIndex):
        logger.warning("DatetimeIndex required for energy computation.")
        return None
    delta = df.index.to_series().diff().dt.total_seconds().fillna(0)
    power = df['batteryVoltage'] * df['batteryCurrent']
    return float((power * delta).sum() / 3600)


def run_data_quality(df, bounds, expected_eff_max):
    """
    Returns a list of data anomalies (formerly BadData).
    """
    anomalies = set()
    for col in df.select_dtypes(include='number').columns:
        if df[col].nunique() <= 1:
            anomalies.add(f"{col}_constant")
        if df[col].isna().any():
            anomalies.add(f"{col}_missing")
        if np.isinf(df[col]).any():
            anomalies.add(f"{col}_inf")
    for col, (low, high) in bounds.items():
        if ((df[col] < low) | (df[col] > high)).any():
            anomalies.add(f"{col}_out_of_bounds")
    if ((df['batteryCurrent'] > 0) & (df['batteryVoltage'] <= 0)).any():
        anomalies.add('current_without_voltage')
    eff = compute_efficiency(df)
    if (eff > expected_eff_max).any():
        anomalies.add('efficiency_over_limit')
    return sorted(anomalies)


def run_efficiency_test(df):
    eff = compute_efficiency(df)
    total_energy = compute_energy(df)
    result = {
        'average_efficiency': eff.fillna(0).mean(),
        'max_efficiency': eff.max(),
    }
    if total_energy is not None:
        result['available_capacity_Wh'] = total_energy
    return result


def run_performance_tests(df, promised):
    max_eng = df['enginePowerWatt'].max()
    max_whe = df['wheelPowerWatt'].max()
    max_tor = df['torqueCrankNm'].max()
    prom_pow = promised.get('promised_motor_power', max_eng)
    support = 100 - (prom_pow / max_eng * 100) if max_eng > 0 else 0
    devs = []
    result = {
        'engine_power_max_W': max_eng,
        'wheel_power_max_W': max_whe,
        'torque_max_Nm': max_tor,
        'max_support_level_percent': support
    }
    for key, measured, prom_key in [
        ('engine_power_max_W', max_eng, 'promised_motor_power'),
        ('torque_max_Nm', max_tor, 'promised_torque'),
        ('wheel_power_max_W', max_whe, 'promised_wheel_power')
    ]:
        prom_val = promised.get(prom_key)
        dev = abs(measured - prom_val) / prom_val * 100 if prom_val else 0
        devs.append(dev)
        result[f'deviation_{key}_percent'] = dev
    result['test_procedure_score'] = 100 - np.mean(devs)
    return result


def run_nominal_load_test(df, promised):
    actual_rise = df['batteryTemperatureCelsius'].max() - df['batteryTemperatureCelsius'].min()
    expected_rise = promised.get('promised_temperature_deviation')

    # Score decreases as actual_rise increases compared to expected
    score = max(0, min(100, (expected_rise / actual_rise) * 100))

    return {
        'continuous_load_W': df['enginePowerWatt'].mean(),
        'temperature_rise_C': actual_rise,
        'nominal_load_test_score': score
    }



def run_battery_health_test(df, promised):
    energy = compute_energy(df)
    prom_cap = promised.get('promised_battery_capacity_Wh', energy or 1)
    health = (energy / prom_cap * 100) if prom_cap else 0
    return {
        'battery_health_percent': health,
        'battery_test_score': round(health),
        'peak_power_output_W': float(max(df['enginePowerWatt'].max(), df['wheelPowerWatt'].max())),
        'max_battery_temperature_C': float(df['batteryTemperatureCelsius'].max())
    }


def run_vibration_test(df, promised):
    hr = df['horizontalInclination'].max() - df['horizontalInclination'].min()
    vr = df['verticalInclination'].max() - df['verticalInclination'].min()
    ht = promised.get('horizontal_vibration_threshold', np.inf)
    vt = promised.get('vertical_vibration_threshold', np.inf)
    return {
        'bearing_health': 'good' if (hr <= ht and vr <= vt) else 'bad',
        'horizontal_vibration_range': hr,
        'vertical_vibration_range': vr
    }


def basic_diagnostics(df, promised_series=DEFAULT_VISUAL, bounds=DEFAULT_BOUNDS, expected_efficiency_max=DEFAULT_EFFICIENCY_MAX):
    # Validate input
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")
    required = [
        'timestamp','batteryVoltage','batteryCurrent','batteryTemperatureCelsius',
        'torqueCrankNm','wheelPowerWatt','enginePowerWatt',
        'horizontalInclination','verticalInclination'
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Prepare DataFrame
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')

    diagnostics = {}
    # Insert each test result
    diagnostics['data_anomalies'] = run_data_quality(df, bounds, expected_efficiency_max)
    diagnostics['efficiency_test'] = run_efficiency_test(df)
    diagnostics['performance_tests'] = run_performance_tests(df, promised_series)
    diagnostics['nominal_load_test'] = run_nominal_load_test(df,promised_series)
    diagnostics['battery_health_test'] = run_battery_health_test(df, promised_series)
    diagnostics['vibration_test'] = run_vibration_test(df, promised_series)

    # Round/serialize all values
    for section, content in diagnostics.items():
        if isinstance(content, dict):
            diagnostics[section] = {k: round_and_make_json_serializable(v) for k, v in content.items()}
        else:
            diagnostics[section] = round_and_make_json_serializable(content)

    return diagnostics
