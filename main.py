from flask import Flask, request, jsonify
import pandas as pd
import io

from analysisScripts import basic_analysis

app = Flask(__name__)

def make_json_response(data, status_code=200):
    response = jsonify(data)
    response.status_code = status_code
    return response

@app.route('/analyze_csv', methods=['POST'])
def analyze_csv_from_json():
    data = request.get_json()

    csv_string = data.get("csv_string")

    if not csv_string:
        return make_json_response({"error": "Missing 'csv_string' in request"}, 400)

    try:
        # Read CSV string into DataFrame
        df = pd.read_csv(io.StringIO(csv_string))

        # Perform analysis
        analysis_results = basic_analysis.basic_diagnostics(df)

        return make_json_response(analysis_results, 200)

    except Exception as e:
        return make_json_response({"error": str(e)}, 500)

if __name__ == '__main__':
    app.run(debug=True)
