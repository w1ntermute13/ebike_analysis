# CSV Analysis API
**Endpoint**: `POST /analyze_csv`  
**Description**: Performs diagnostic analysis on uploaded CSV data with technician parameters.

## **Request**
- **Content-Type**: `multipart/form-data`
- **Required Parts**:

| Part Name          | Type       | Description                          | Example Value                     |
|--------------------|------------|--------------------------------------|-----------------------------------|
| `csv_file`         | File       | CSV data as binary (octet-stream)    | [Attach file in Postman]          |
| `technician_input` | Text (JSON)| Analysis parameters in JSON format   | `{"technician_id": "tech_123"}`   |

## **Requirements**
- CSV must be sent with `Content-Type: application/octet-stream` for the file part.
- JSON input must be valid and include required fields (e.g., `technician_id`).

## **Responses**
### Success (200 OK)
```json
{
  "analysis_summary": {
    "mean_value": 25.3,
    "alerts_detected": 2
  }
}
