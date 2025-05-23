import requests
import json
import google.auth
import google.auth.transport.requests
import logging
import os
from dotenv import load_dotenv
from google.oauth2 import service_account

load_dotenv()

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration Constants ---
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
LOCATION_ID = os.environ.get("GCP_LOCATION")
MODEL_ID = "claude-3-7-sonnet"
API_VERSION = "v1"
PUBLISHER = "anthropic"
METHOD = "rawPredict"
ENDPOINT_HOSTNAME = f"{LOCATION_ID}-aiplatform.googleapis.com"
API_ENDPOINT_URL = f"https://{ENDPOINT_HOSTNAME}/{API_VERSION}/projects/{PROJECT_ID}/locations/{LOCATION_ID}/publishers/{PUBLISHER}/models/{MODEL_ID}:{METHOD}"

# Anthropic-specific parameters
ANTHROPIC_VERSION = "vertex-2023-10-16"
MAX_TOKENS = 10000
TEMPERATURE = 0
TOP_P = 0.8
TOP_K = 1

# --- Service Account Key File Path ---
SERVICE_ACCOUNT_KEY_FILE = "service_account_credentials.json"  # Get from environment variable

# Global cache for credentials
_credentials = None
_auth_request = None

def _get_auth_token():
    """Gets a Google Cloud access token using a service account key file."""
    global _credentials, _auth_request
    try:
        if not _credentials or not _credentials.valid:
            scopes = ["https://www.googleapis.com/auth/cloud-platform"]
            
            # Use service account credentials
            if SERVICE_ACCOUNT_KEY_FILE:
                _credentials = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_KEY_FILE, scopes=scopes
                )
                logging.info(f"Using service account key file: {SERVICE_ACCOUNT_KEY_FILE}")
            else:
                raise ValueError(
                    "GOOGLE_APPLICATION_CREDENTIALS environment variable not set. "
                    "Please provide the path to your service account key file."
                )
            _auth_request = google.auth.transport.requests.Request()

        # Refresh the token if necessary
        _credentials.refresh(_auth_request)
        return _credentials.token
    except ValueError as e:
        logging.error(f"Configuration Error: {e}")
        return None
    except google.auth.exceptions.GoogleAuthError as e:
        logging.error(f"GCP Authentication Error: {e}")
        return None
    except Exception as e:
        logging.error(f"Error getting/refreshing GCP auth token: {e}")
        return None

def get_claude_raw_response(prompt_text: str) -> str | None:
    """
    Sends a prompt to the specified Claude model via Vertex AI rawPredict.

    Args:
        prompt_text: The user prompt string.

    Returns:
        The extracted text response from the model as a string,
        or None if an error occurs or the response is malformed.
    """
    access_token = _get_auth_token()
    if not access_token:
        return None  # Error logged in _get_auth_token

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    payload = {
        "anthropic_version": ANTHROPIC_VERSION,
        "stream": False,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "top_k": TOP_K,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt_text
                    }
                ]
            }
        ]
    }

    try:
        logging.info(f"Sending request to {MODEL_ID}...")
        response = requests.post(API_ENDPOINT_URL, headers=headers, json=payload, timeout=120)

        if response.status_code == 429:
            logging.error(f"Quota exceeded (429). Base Model: {MODEL_ID}. Consider adding delays between calls.")
            logging.error(f"Response body: {response.text}")
            return None
        elif response.status_code == 401 or response.status_code == 403:
            logging.error(f"Authentication/Authorization error ({response.status_code}). Check token and permissions.")
            logging.error(f"Response body: {response.text}")
            return None

        response.raise_for_status()

        response_data = response.json()

        content_blocks = response_data.get('content', [])
        if content_blocks and isinstance(content_blocks, list) and len(content_blocks) > 0:
            first_block = content_blocks[0]
            if isinstance(first_block, dict) and first_block.get('type') == 'text':
                logging.info(f"Successfully received response from {MODEL_ID}.")
                return first_block.get('text', '')
            else:
                logging.warning(f"First content block is not a valid text block: {first_block}")
                return None
        else:
            logging.warning(f"No valid content blocks found in response: {response_data}")
            return None

    except requests.exceptions.Timeout:
        logging.error("The request timed out.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"An HTTP request error occurred: {e}")
        if e.response is not None:
            logging.error(f"Response status code: {e.response.status_code}")
            logging.error(f"Response body: {e.response.text}")
        return None
    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON response: {response.text}")
        return None
    except (KeyError, IndexError, TypeError) as e:
        logging.error(f"Failed to parse expected content from response: {e}")
        logging.error(f"Full Response Data: {response_data}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None

# --- Example Usage ---
if __name__ == "__main__":
    # Set the environment variable before running
    # export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service_account_key.json"
    # Or set it in your IDE's run configuration

    prompt1 = "Explain the concept of zero-shot learning in simple terms."
    print(f"\n--- Request 1 ---")
    response1 = get_claude_raw_response(prompt1)
    if response1:
        print("\nModel Response:")
        print(response1)
    else:
        print("\nFailed to get response for prompt 1.")

    prompt2 = "What is the capital of France?"
    print(f"\n--- Request 2 ---")
    response2 = get_claude_raw_response(prompt2)
    if response2:
        print("\nModel Response:")
        print(response2)
    else:
        print("\nFailed to get response for prompt 2.")

    prompt3 = "This prompt might be tricky or cause an issue."
    print(f"\n--- Request 3 ---")
    response3 = get_claude_raw_response(prompt3)
    if response3:
        print("\nModel Response:")
        print(response3)
    else:
        print("\nFailed to get response for prompt 3.")
