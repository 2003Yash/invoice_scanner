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
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "easework-projects")  # Default project ID
LOCATION_ID = os.environ.get("GCP_LOCATION", "global")  # Default to us-central1 if not set
MODEL_ID = "gemini-2.5-pro-preview-05-06"  # Updated model ID
PUBLISHER = "google"  # Changed publisher from anthropic to google
API_VERSION = "v1"

# Validation for required parameters
if not LOCATION_ID:
    logging.warning("GCP_LOCATION not set in environment variables. Using default: us-central1")
if not PROJECT_ID:
    logging.warning("GCP_PROJECT_ID not set in environment variables. Using default from code.")

ENDPOINT_HOSTNAME = f"{LOCATION_ID}-aiplatform.googleapis.com"
BASE_API_ENDPOINT = f"https://{ENDPOINT_HOSTNAME}/{API_VERSION}/projects/{PROJECT_ID}/locations/{LOCATION_ID}/publishers/{PUBLISHER}/models/{MODEL_ID}"
GENERATE_ENDPOINT = f"{BASE_API_ENDPOINT}:generateContent"
STREAM_ENDPOINT = f"{BASE_API_ENDPOINT}:streamGenerateContent"

# Gemini-specific parameters
TEMPERATURE = 0.0
# TOP_P = 0.8
# TOP_K = 1
# MAX_OUTPUT_TOKENS = 10000  # Renamed from MAX_TOKENS

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

def get_gemini_response(prompt_text: str, stream=False) -> str | None:
    """
    Sends a prompt to the specified Gemini model via Vertex AI.

    Args:
        prompt_text: The user prompt string.
        stream: Whether to stream the response (default: False).

    Returns:
        The extracted text response from the model as a string,
        or None if an error occurs or the response is malformed.
    """
    # Validate configuration
    if not PROJECT_ID or not LOCATION_ID:
        logging.error("Missing required configuration. Please set GCP_PROJECT_ID and GCP_LOCATION environment variables.")
        return None
        
    access_token = _get_auth_token()
    if not access_token:
        return None  # Error logged in _get_auth_token

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt_text
                    }
                ]
            }
        ],
        "generation_config": {
            "temperature": TEMPERATURE,
            # "topP": TOP_P,
            # "topK": TOP_K,
            # "maxOutputTokens": MAX_OUTPUT_TOKENS
        },
        "safety_settings": [
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
    }

    # Use the appropriate endpoint - no stream parameter in the payload for non-streaming
    endpoint = GENERATE_ENDPOINT
    if stream:
        endpoint = STREAM_ENDPOINT

    try:
        logging.info(f"Sending request to {MODEL_ID} at {LOCATION_ID}...")
        response = requests.post(endpoint, headers=headers, json=payload, timeout=120)

        if response.status_code == 429:
            logging.error(f"Quota exceeded (429). Base Model: {MODEL_ID}. Consider adding delays between calls.")
            logging.error(f"Response body: {response.text}")
            return None
        elif response.status_code == 401 or response.status_code == 403:
            logging.error(f"Authentication/Authorization error ({response.status_code}). Check token and permissions.")
            logging.error(f"Response body: {response.text}")
            return None
        elif response.status_code == 404:
            logging.error(f"Resource not found (404). Verify MODEL_ID, LOCATION_ID, and PROJECT_ID.")
            logging.error(f"Endpoint URL: {endpoint}")
            logging.error(f"Response body: {response.text}")
            return None

        response.raise_for_status()

        response_data = response.json()
        
        # Parse Gemini response structure
        candidates = response_data.get('candidates', [])
        if candidates and len(candidates) > 0:
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            
            if parts and len(parts) > 0:
                text_parts = [part.get('text', '') for part in parts if part.get('text')]
                full_text = ''.join(text_parts)
                logging.info(f"Successfully received response from {MODEL_ID}.")
                return full_text
            else:
                logging.warning(f"No valid parts found in content: {content}")
                return None
        else:
            logging.warning(f"No candidates found in response: {response_data}")
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

def get_gemini_stream_response(prompt_text: str):
    """
    Sends a prompt to the Gemini model and returns a generator for streaming responses.
    
    Args:
        prompt_text: The user prompt string.
        
    Yields:
        Chunks of text from the model response.
    """
    # Validate configuration
    if not PROJECT_ID or not LOCATION_ID:
        logging.error("Missing required configuration. Please set GCP_PROJECT_ID and GCP_LOCATION environment variables.")
        yield "Error: Missing required configuration. Please set GCP_PROJECT_ID and GCP_LOCATION environment variables."
        return
        
    access_token = _get_auth_token()
    if not access_token:
        yield "Error: Failed to get authentication token"
        return

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json"
    }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt_text
                    }
                ]
            }
        ],
        "generation_config": {
            "temperature": TEMPERATURE,
            # "topP": TOP_P,
            # "topK": TOP_K,
            # "maxOutputTokens": MAX_OUTPUT_TOKENS
        },
        "safety_settings": [
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
    }

    try:
        logging.info(f"Sending streaming request to {MODEL_ID} at {LOCATION_ID}...")
        response = requests.post(STREAM_ENDPOINT, headers=headers, json=payload, stream=True, timeout=180)
        
        if response.status_code == 404:
            logging.error(f"Resource not found (404). Verify MODEL_ID, LOCATION_ID, and PROJECT_ID.")
            logging.error(f"Endpoint URL: {STREAM_ENDPOINT}")
            logging.error(f"Response body: {response.text}")
            yield f"Error: Resource not found (404). Please check your configuration."
            return
        elif response.status_code != 200:
            logging.error(f"Error: {response.status_code}")
            logging.error(f"Response body: {response.text}")
            yield f"Error: Received status code {response.status_code}"
            return

        # For streamGenerateContent, the response is actually a complete JSON object
        # that contains multiple chunks. We need to parse it differently.
        response_text = response.text
        
        try:
            # Parse the complete JSON response
            data = json.loads(response_text)
            
            # Check if this is a list of responses or just one response
            if isinstance(data, list):
                for response_obj in data:
                    candidates = response_obj.get('candidates', [])
                    for candidate in candidates:
                        content = candidate.get('content', {})
                        parts = content.get('parts', [])
                        for part in parts:
                            if 'text' in part:
                                yield part['text']
            else:
                # Single response object
                candidates = data.get('candidates', [])
                for candidate in candidates:
                    content = candidate.get('content', {})
                    parts = content.get('parts', [])
                    for part in parts:
                        if 'text' in part:
                            yield part['text']
                    
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error: {e}")
            logging.error(f"Response text: {response_text[:200]}...")  # Log first 200 chars
            yield f"Error: Could not parse stream response as JSON"
                    
    except requests.exceptions.Timeout:
        logging.error("The streaming request timed out.")
        yield "Error: The request timed out."
    except requests.exceptions.RequestException as e:
        logging.error(f"An HTTP request error occurred during streaming: {e}")
        yield f"Error: {str(e)}"
    except Exception as e:
        logging.error(f"An unexpected error occurred during streaming: {e}")
        yield f"Error: {str(e)}"

# --- Example Usage ---
if __name__ == "__main__":
    # Set the environment variable before running
    # export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service_account_key.json"
    # Or set it in your IDE's run configuration

    # Display current configuration for debugging
    print(f"Configuration:")
    print(f"  PROJECT_ID: {PROJECT_ID}")
    print(f"  LOCATION_ID: {LOCATION_ID}")
    print(f"  MODEL_ID: {MODEL_ID}")
    print(f"  GENERATE_ENDPOINT: {GENERATE_ENDPOINT}")
    print(f"  STREAM_ENDPOINT: {STREAM_ENDPOINT}")
    print()

    prompt1 = "Explain the concept of zero-shot learning in simple terms."
    print(f"\n--- Request 1 ---")
    response1 = get_gemini_response(prompt1)
    if response1:
        print("\nModel Response:")
        print(response1)
    else:
        print("\nFailed to get response for prompt 1.")

    prompt2 = "What is the capital of France?"
    print(f"\n--- Request 2 ---")
    response2 = get_gemini_response(prompt2)
    if response2:
        print("\nModel Response:")
        print(response2)
    else:
        print("\nFailed to get response for prompt 2.")

    # Example of using the streaming response
    prompt3 = "Write a short paragraph about artificial intelligence."
    print(f"\n--- Streaming Request ---")
    print("\nModel Stream Response:")
    for chunk in get_gemini_stream_response(prompt3):
        print(chunk, end="", flush=True)
    print("\n\nStreaming complete.")