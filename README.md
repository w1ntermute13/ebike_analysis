# CSV Analysis API

**Endpoint**: `POST /analyze_csv`  
**Description**: Performs diagnostic analysis on uploaded CSV data using technician-defined parameters.

---

## Request
- **Content-Type**: `multipart/form-data`
- **Required Parts**:

| Part Name          | Type         | Description                                | Example Value                                                                 |
|--------------------|--------------|--------------------------------------------|-------------------------------------------------------------------------------|
| `csv_file`         | File         | CSV data as binary (octet-stream)          | [Attach file in Postman]                                                     |
| `technician_input` | Text (JSON)  | Analysis parameters in JSON format         | `{ "promised_motor_power": 350, "promised_torque": 70, ... }`                |

---

## Requirements
1. CSV file part **must** use `Content-Type: application/octet-stream`
2. JSON input must contain all required technician parameters:
```json
{
  "promised_motor_power": 350,
  "promised_torque": 70,
  "promised_wheel_power": 320,
  "promised_battery_capacity_Wh": 500,
  "promised_temperature_deviation": 40,
  "horizontal_vibration_threshold": 2.0,
  "vertical_vibration_threshold": 40
}
