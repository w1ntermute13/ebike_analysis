from flask import Flask, request, jsonify
import boto3
import pandas as pd
import io
import os

from analysisScripts import basic_analysis

app = Flask(__name__)

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

def make_json_response(data, status_code=200):
    response = jsonify(data)
    response.status_code = status_code
    return response

@app.route('/load_csv', methods=['POST'])
def load_csv_from_s3():
    data = request.get_json()

    bucket = data.get("bucket")
    key = data.get("key")

    if not bucket or not key:
        return make_json_response({"error": "Missing 'bucket' or 'key' in request"}, 400)

    try:
        response_s3 = s3_client.get_object(Bucket=bucket, Key=key)
        csv_content = response_s3['Body'].read()
        df = pd.read_csv(io.BytesIO(csv_content))

        analysis_results = basic_analysis.basic_diagnostics(df)
        return make_json_response(analysis_results, 200)

    except s3_client.exceptions.NoSuchKey:
        return make_json_response({"error": "The specified key does not exist in the bucket."}, 404)
    except s3_client.exceptions.NoSuchBucket:
        return make_json_response({"error": "The specified bucket does not exist."}, 404)
    except Exception as e:
        return make_json_response({"error": str(e)}, 500)

if __name__ == '__main__':
    app.run(debug=True)
