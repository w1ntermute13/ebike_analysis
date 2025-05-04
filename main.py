from flask import Flask, request, jsonify
import pandas as pd
import io
import json
from analysisScripts import basic_analysis

app = Flask(__name__)


@app.route('/analyze_csv', methods=['POST'])
def analyze_csv():
    # Check if the request is multipart form data
    if not request.content_type or 'multipart/form-data' not in request.content_type:
        return jsonify({"error": "Only multipart/form-data supported"}), 415

    # Check if both parts are present
    if 'csv_file' not in request.files or 'technician_input' not in request.form:
        return jsonify({"error": "Missing required parts (need 'csv_file' and 'technician_input')"}), 400

    try:
        # Get CSV file part
        csv_file = request.files['csv_file']
        if csv_file.content_type != 'application/octet-stream':
            return jsonify({"error": "CSV file must be sent as octet-stream"}), 415

        # Read CSV data
        df = pd.read_csv(io.BytesIO(csv_file.read()))

        # Get and parse technician input
        tech_input = request.form['technician_input']
        tech_params = pd.Series(json.loads(tech_input))

        # Analysis
        results = basic_analysis.basic_diagnostics(df, tech_params)
        return jsonify(results)

    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON in technician_input"}), 400
    except pd.errors.EmptyDataError:
        return jsonify({"error": "Empty CSV file"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)