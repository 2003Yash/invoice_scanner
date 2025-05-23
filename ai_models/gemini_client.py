import os
import logging
from typing import Generator, Optional, Union
from dotenv import load_dotenv

# Import vertexai directly (not from google.cloud)
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from vertexai.preview.generative_models import HarmCategory, HarmBlockThreshold
from google.oauth2 import service_account

load_dotenv()

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration Constants ---
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "easework-projects")  # Default project ID
LOCATION_ID = os.environ.get("GCP_LOCATION", "us-central1")  # Default to us-central1 if not set
MODEL_ID = "publishers/google/models/gemini-2.5-flash-preview-05-20"
# MODEL_ID = "gemini-2.5-pro-preview-05-06"  # Updated model ID

# Validation for required parameters
if not LOCATION_ID:
    logging.warning("GCP_LOCATION not set in environment variables. Using default: us-central1")
if not PROJECT_ID:
    logging.warning("GCP_PROJECT_ID not set in environment variables. Using default from code.")

# --- Service Account Key File Path ---
SERVICE_ACCOUNT_KEY_FILE = "service_account_credentials.json"

# Gemini-specific parameters
TEMPERATURE = 0.0
# TOP_P = 0.8
# TOP_K = 1

# Global variables for client initialization
_initialized = False
_model = None

def _initialize_vertex_ai():
    """Initialize the Vertex AI SDK with the given service account credentials."""
    global _initialized, _model
    
    try:
        if not _initialized:
            # Set up authentication
            if SERVICE_ACCOUNT_KEY_FILE:
                credentials = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_KEY_FILE,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                # Initialize Vertex AI with the credentials
                vertexai.init(
                    project=PROJECT_ID,
                    location=LOCATION_ID,
                    credentials=credentials
                )
                logging.info(f"Using service account key file: {SERVICE_ACCOUNT_KEY_FILE}")
            else:
                # Use default credentials (e.g., from environment variable)
                vertexai.init(project=PROJECT_ID, location=LOCATION_ID)
                logging.info("Using default authentication from environment")
                
            # Initialize the Gemini model
            _model = GenerativeModel(MODEL_ID)
            _initialized = True
            logging.info(f"Successfully initialized Vertex AI client for {MODEL_ID}")
    except Exception as e:
        logging.error(f"Failed to initialize Vertex AI: {e}")
        return False
        
    return True

def get_gemini_response(prompt_text: str, stream: bool = False) -> Optional[str]:
    """
    Sends a prompt to the specified Gemini model via Vertex AI.

    Args:
        prompt_text: The user prompt string.
        stream: Whether to stream the response (default: False).

    Returns:
        The extracted text response from the model as a string,
        or None if an error occurs or the response is malformed.
    """
    # Initialize Vertex AI if not already done
    if not _initialize_vertex_ai():
        return None
        
    # Configure generation parameters
    generation_config = GenerationConfig(
        temperature=TEMPERATURE,
        # top_p=TOP_P,
        # top_k=TOP_K,
        # max_output_tokens=MAX_OUTPUT_TOKENS  # Uncomment if needed
    )
    
    # Configure safety settings
    safety_settings = {
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    }
    
    try:
        logging.info(f"Sending request to {MODEL_ID} at {LOCATION_ID}...")
        
        # Generate content with the model
        response = _model.generate_content(
            prompt_text,
            generation_config=generation_config,
            safety_settings=safety_settings,
            stream=stream
        )
        
        if stream:
            # For streaming, we'll return a generator which will be handled in get_gemini_stream_response
            return response
        else:
            # For non-streaming, extract the text
            if hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
                if response.candidates[0].content and response.candidates[0].content.parts:
                    full_text = ''.join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
                    logging.info(f"Successfully received response from {MODEL_ID}.")
                    print(full_text)  # Maintain the same behavior as original code
                    return full_text
                else:
                    logging.warning("No valid content parts found in response.")
            else:
                logging.warning("No candidates found in response.")
        
        return None
        
    except Exception as e:
        logging.error(f"Error generating content: {e}")
        return None

def get_gemini_stream_response(prompt_text: str) -> Generator[str, None, None]:
    """
    Sends a prompt to the Gemini model and returns a generator for streaming responses.
    
    Args:
        prompt_text: The user prompt string.
        
    Yields:
        Chunks of text from the model response.
    """
    try:
        # Get streaming response (returns a generator)
        stream_response = get_gemini_response(prompt_text, stream=True)
        
        if stream_response is None:
            yield "Error: Failed to initialize streaming response"
            return
            
        # Iterate through streaming chunks
        for chunk in stream_response:
            if hasattr(chunk, 'candidates') and chunk.candidates and len(chunk.candidates) > 0:
                candidate = chunk.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            yield part.text
        
    except Exception as e:
        logging.error(f"An error occurred during streaming: {e}")
        yield f"Error: {str(e)}"

# --- Example Usage ---
if __name__ == "__main__":
    # Display current configuration for debugging
    print(f"Configuration:")
    print(f"  PROJECT_ID: {PROJECT_ID}")
    print(f"  LOCATION_ID: {LOCATION_ID}")
    print(f"  MODEL_ID: {MODEL_ID}")
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