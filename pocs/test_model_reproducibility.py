from pathlib import Path
import os
import logging
from openai import OpenAI
import json
from typing import List, Dict, Any
import time
import boto3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check for API keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Define models to test
GEMINI_MODELS = ["gemini-2.0-flash"]
OPENAI_MODELS = ["gpt-4o-mini", "gpt-4o"]
NOVA_MODELS = ["amazon.nova-micro-v1:0", "amazon.nova-lite-v1:0", "amazon.nova-pro-v1:0"]

def call_llm(model_name: str, prompt: str, base_url: str = None, seed: int = None, system_fingerprint: str = None) -> str:
    """
    Call the LLM with a prompt and return the response.
    
    Args:
        model_name: Name of the model to use
        prompt: The prompt to send
        base_url: Optional base URL for the API
        seed: Optional seed for deterministic output
        system_fingerprint: Optional system fingerprint for OpenAI
        
    Returns:
        The model's response
    """
    try:
        if model_name in NOVA_MODELS:
            # Use AWS Bedrock for Nova models
            bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
            
            # Prepare the request body
            request_body = {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}]
                    }
                ],
                "inferenceConfig": {
                    "temperature": 0.0,
                    "topP": 0.9,
                    "maxTokens": 5000
                }
            }
            
            # Make the API call
            response = bedrock.converse(
                modelId=model_name,
                messages=request_body["messages"],
                inferenceConfig=request_body["inferenceConfig"]
            )
            
            # Extract the response text
            return response["output"]["message"]["content"][0]["text"]
            
        else:
            # Use OpenAI client for other models
            api_key = GEMINI_API_KEY if model_name in GEMINI_MODELS else OPENAI_API_KEY
            client = OpenAI(api_key=api_key, base_url=base_url)
            
            # Prepare the request
            request = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0
            }
            
            # Add seed if provided
            if seed is not None:
                request["seed"] = seed
            
            # Add system_fingerprint if provided (OpenAI only)
            if system_fingerprint is not None and model_name in OPENAI_MODELS:
                request["system_fingerprint"] = system_fingerprint
            
            response = client.chat.completions.create(**request)
            return response.choices[0].message.content
            
    except Exception as e:
        error_msg = f"Error calling API: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

def test_model_reproducibility(model_name: str, prompt: str, num_runs: int = 5, base_url: str = None, seed: int = None, system_fingerprint: str = None) -> Dict[str, Any]:
    """
    Test if a model produces the same output multiple times with temperature=0.0.
    
    Args:
        model_name: Name of the model to test
        prompt: The prompt to send
        num_runs: Number of times to run the test
        base_url: Optional base URL for the API
        seed: Optional seed for deterministic output
        system_fingerprint: Optional system fingerprint for OpenAI
        
    Returns:
        Dictionary containing test results
    """
    logger.info(f"Testing reproducibility of {model_name}")
    if seed is not None:
        logger.info(f"Using fixed seed: {seed}")
    if system_fingerprint is not None:
        logger.info(f"Using system fingerprint: {system_fingerprint}")
    
    # Set appropriate base URL based on the model
    if base_url is None and model_name not in NOVA_MODELS:
        if model_name in GEMINI_MODELS:
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        else:
            base_url = None  # Use default OpenAI base URL for OpenAI models
    
    responses = []
    start_time = time.time()
    
    for run in range(num_runs):
        logger.info(f"Run {run + 1}/{num_runs}")
        response = call_llm(model_name, prompt, base_url, seed, system_fingerprint)
        responses.append(response)
        # Add a small delay between calls to avoid rate limiting
        time.sleep(1)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Check if all responses are identical
    all_identical = all(response == responses[0] for response in responses)
    
    return {
        "model": model_name,
        "num_runs": num_runs,
        "duration": duration,
        "all_identical": all_identical,
        "responses": responses,
        "seed": seed,
        "system_fingerprint": system_fingerprint
    }

def save_results(results: List[Dict[str, Any]], output_dir: str = "output"):
    """
    Save test results to a JSON file.
    
    Args:
        results: List of test results
        output_dir: Directory to save results in
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"model_reproducibility_{timestamp}.json"
    filepath = output_path / filename
    
    # Save results
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results saved to {filepath}")

def main():
    # Test prompt - simple enough to be deterministic
    prompt = """What is the sum of the first 5 prime numbers? Show your work step by step."""
    
    # Get available models based on API keys and AWS credentials
    available_models = []
    
    # Check AWS credentials
    try:
        boto3.client('bedrock-runtime', region_name='us-east-1')
        available_models.extend(NOVA_MODELS)
        logger.info("AWS Bedrock credentials found, adding Nova models")
    except Exception as e:
        logger.warning(f"AWS Bedrock credentials not found: {e}")
    
    # Check OpenAI and Gemini credentials
    if OPENAI_API_KEY:
        available_models.extend(OPENAI_MODELS)
    if GEMINI_API_KEY:
        available_models.extend(GEMINI_MODELS)
    
    if not available_models:
        logger.error("No API keys or AWS credentials found. Please set up the necessary credentials.")
        return
    
    results = []
    
    # Test each model
    for model in available_models:
        try:
            # Base test without seed
            result = test_model_reproducibility(model, prompt)
            results.append(result)
            
            # Log summary
            logger.info(f"\nResults for {model}:")
            logger.info(f"All responses identical: {result['all_identical']}")
            logger.info(f"Total duration: {result['duration']:.2f} seconds")
            logger.info(f"Average time per run: {result['duration']/result['num_runs']:.2f} seconds")
            
            # Additional tests for OpenAI and Gemini models
            if model in OPENAI_MODELS or model in GEMINI_MODELS:
                # Test with fixed seed
                seed_result = test_model_reproducibility(model, prompt, seed=42)
                results.append(seed_result)
                logger.info(f"\nResults for {model} with seed=42:")
                logger.info(f"All responses identical: {seed_result['all_identical']}")
                
                # For OpenAI models, also test with system_fingerprint
                if model in OPENAI_MODELS:
                    # Get system_fingerprint from first run
                    client = OpenAI(api_key=OPENAI_API_KEY)
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0,
                        seed=
                    )
                    system_fingerprint = response.system_fingerprint
                    
                    # Test with both seed and system_fingerprint
                    fingerprint_result = test_model_reproducibility(
                        model, 
                        prompt, 
                        seed=42, 
                        system_fingerprint=system_fingerprint
                    )
                    results.append(fingerprint_result)
                    logger.info(f"\nResults for {model} with seed=42 and system_fingerprint:")
                    logger.info(f"All responses identical: {fingerprint_result['all_identical']}")
            
        except Exception as e:
            logger.error(f"Error testing {model}: {str(e)}")
            results.append({
                "model": model,
                "error": str(e)
            })
    
    # Save results
    save_results(results)

if __name__ == "__main__":
    main() 