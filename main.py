from flask import Flask, request, jsonify
import pandas as pd
import io
import json
import os
import logging
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from analysisScripts import basic_analysis


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


load_dotenv() #ENVIROMENT_VARIABLES

AZURE_STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")

if not AZURE_STORAGE_ACCOUNT or not AZURE_STORAGE_CONTAINER:
    logger.error("Missing Azure storage account or container name in environment variables.")
    raise ValueError("Missing Azure storage account or container name in environment variables.")

try:
    account_url = f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net"
    credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
    logger.info("Successfully authenticated with Azure using DefaultAzureCredential.")
except Exception as e:
    logger.exception("Failed to authenticate with Azure Blob Storage.")
    raise

app = Flask(__name__)

@app.route('/analyze_csv', methods=['POST'])
def analyze_csv():
    logger.info("Received /analyze_csv request")

    if not request.is_json:
        logger.warning("Request content type is not JSON")
        return jsonify({"error": "Request must be JSON"}), 415

    data = request.get_json()

    if 'params' not in data:
        logger.warning("Missing 'technician_input' in request body")
        return jsonify({"error": "Missing 'technician_input' in request body"}), 400

    technician_input = data['params']

    if 'serviceLogId' not in data:
        logger.warning("Missing 'serviceLogId' in the request body")
        return jsonify({"error": "Missing 'serviceLogId' in technician_input"}), 400

    try:
        blob_name = f"{data['serviceLogId']}.csv"
        logger.info(f"Attempting to download blob: {blob_name}")

        blob_client = blob_service_client.get_blob_client(container=AZURE_STORAGE_CONTAINER, blob=blob_name)
        csv_content = blob_client.download_blob().readall()
        df = pd.read_csv(io.BytesIO(csv_content))

        logger.info("Blob downloaded and CSV loaded successfully.")

        tech_params = pd.Series(technician_input)

        logger.info("Starting analysis...")
        results = basic_analysis.basic_diagnostics(df, tech_params)
        logger.info("Analysis completed successfully.")

        return jsonify(results)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in technician input")
        return jsonify({"error": "Invalid JSON in technician_input"}), 400
    except pd.errors.EmptyDataError:
        logger.error("Empty or invalid CSV blob")
        return jsonify({"error": "Empty or invalid CSV blob"}), 400
    except Exception as e:
        logger.exception("Unhandled error during analysis")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting Flask app on 0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000)
