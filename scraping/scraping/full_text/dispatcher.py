import json
import boto3

lambda_client = boto3.client("lambda")

LAMBDA_FUNCTIONS = {
    "pubmed": "fulltext_pubmed_code",
    "medrxiv": "fulltext_biorxiv_code",
    "plos": "fulltext_plos_code"
}

def lambda_handler(event, context):

    query_params = event.get("queryStringParameters", {})
    source = query_params.get("source")
    url = query_params.get("url")

    cors_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*", 
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

    if not source or source not in LAMBDA_FUNCTIONS:
        return {
            "statusCode": 400,
            "headers": cors_headers,
            "body": json.dumps({"error": "Invalid or missing 'source'. Choose from 'pubmed', 'medrxiv', 'plos'."})
        }
    if not url:
        return {
            "statusCode": 400,
            "headers": cors_headers,
            "body": json.dumps({"error": "Missing 'url' parameter. Provide a valid URL."})
        }

    target_lambda = LAMBDA_FUNCTIONS[source]

    invoke_params = {
        "FunctionName": target_lambda,
        "InvocationType": "RequestResponse",  
        "Payload": json.dumps({"queryStringParameters": {"url": url}})  
    }

    try:
       
        response = lambda_client.invoke(**invoke_params)
        response_payload = response["Payload"].read().decode("utf-8")

        return {
            "statusCode": response["StatusCode"],
            "headers": cors_headers,  
            "body": response_payload 
        }

    except Exception as e:
        print(f"Error invoking {target_lambda}: {str(e)}")
        return {
            "statusCode": 500,
            "headers": cors_headers,  
            "body": json.dumps({"error": "Internal server error while invoking Lambda."})
        }
