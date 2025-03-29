from pathlib import Path
import os
import logging
from openai import OpenAI
import json
from typing import List, Dict, Any
import time
import boto3
import google.generativeai as genai
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check for API keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Configure Google Generative AI
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Define models to test
GEMINI_MODELS = ["models/gemini-2.0-flash-lite", "models/gemini-2.0-flash"]  # Testing both flash variants
OPENAI_MODELS = ["gpt-4o-mini", "gpt-4o"]
NOVA_MODELS = ["amazon.nova-micro-v1:0", "amazon.nova-lite-v1:0", "amazon.nova-pro-v1:0"]

def call_llm(model_name: str, prompt: str, base_url: str = None, seed: int = None, top_k: int = None, top_p: float = None) -> Dict[str, Any]:
    """
    Call the LLM with a prompt and return the response and metadata.
    
    Args:
        model_name: Name of the model to use
        prompt: The prompt to send
        base_url: Optional base URL for the API
        seed: Optional seed for deterministic output
        top_k: Optional top_k parameter to limit sampling
        top_p: Optional top_p parameter to limit sampling
        
    Returns:
        Dictionary containing response content and metadata
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
            return {
                "content": response["output"]["message"]["content"][0]["text"],
                "system_fingerprint": None  # AWS doesn't provide this
            }
            
        elif model_name in GEMINI_MODELS:
            # Use Google Generative AI API directly for Gemini
            logger.info(f"Initializing Gemini model: {model_name}")
            model = genai.GenerativeModel(model_name)
            
            # Prepare generation config
            generation_config = {
                "temperature": 0.0,
                "top_k": top_k if top_k is not None else 1,
                "top_p": top_p if top_p is not None else 0.1
            }
            logger.info(f"Generation config: {generation_config}")
            
            # Generate response
            logger.info("Calling Gemini API...")
            start_time = time.time()
            response = model.generate_content(prompt, generation_config=generation_config)
            end_time = time.time()
            logger.info(f"API call took {end_time - start_time:.2f} seconds")
            logger.info(f"Response length: {len(response.text)} chars")
            logger.info(f"Response preview: {response.text[:100]}...")
            
            return {
                "content": response.text,
                "system_fingerprint": None  # Gemini doesn't provide this
            }
            
        else:
            # Use OpenAI client for other models
            client = OpenAI(api_key=OPENAI_API_KEY, base_url=base_url)
            
            # Prepare the request
            request = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0
            }
            
            # Add seed if provided
            if seed is not None:
                request["seed"] = seed
                
            # Add top_p if provided
            if top_p is not None:
                request["top_p"] = top_p
            
            response = client.chat.completions.create(**request)
            return {
                "content": response.choices[0].message.content,
                "system_fingerprint": getattr(response, 'system_fingerprint', None)
            }
            
    except Exception as e:
        error_msg = f"Error calling API: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

def test_model_reproducibility(model_name: str, prompt: str, num_runs: int = 3, base_url: str = None, seed: int = None, top_k: int = None, top_p: float = None) -> Dict[str, Any]:
    """
    Test if a model produces the same output multiple times with temperature=0.0.
    
    Args:
        model_name: Name of the model to test
        prompt: The prompt to send
        num_runs: Number of times to run the test
        base_url: Optional base URL for the API
        seed: Optional seed for deterministic output
        top_k: Optional top_k parameter to limit sampling
        top_p: Optional top_p parameter to limit sampling
        
    Returns:
        Dictionary containing test results
    """
    logger.info(f"\nTesting reproducibility of {model_name}")
    if seed is not None:
        logger.info(f"Using fixed seed: {seed}")
    if top_k is not None:
        logger.info(f"Using top_k: {top_k}")
    if top_p is not None:
        logger.info(f"Using top_p: {top_p}")
    
    # Set appropriate base URL based on the model
    if base_url is None and model_name not in NOVA_MODELS:
        if model_name in GEMINI_MODELS:
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        else:
            base_url = None  # Use default OpenAI base URL for OpenAI models
    
    responses = []
    fingerprints = []
    start_time = time.time()
    
    for run in range(num_runs):
        logger.info(f"\nRun {run + 1}/{num_runs}")
        result = call_llm(model_name, prompt, base_url, seed, top_k, top_p)
        responses.append(result["content"])
        if result["system_fingerprint"] is not None:
            fingerprints.append(result["system_fingerprint"])
        # Add a small delay between calls to avoid rate limiting
        time.sleep(1)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Check if all responses are identical
    all_identical = all(response == responses[0] for response in responses)
    
    # Log full responses
    logger.info("\nFull responses:")
    for i, response in enumerate(responses, 1):
        logger.info(f"\nResponse {i}:\n{response}\n")
        logger.info("-" * 80)
    
    # For OpenAI models, check if fingerprints are identical
    fingerprint_identical = None
    if fingerprints:
        fingerprint_identical = all(fp == fingerprints[0] for fp in fingerprints)
        if not fingerprint_identical:
            logger.warning(f"System fingerprints differed across runs for {model_name}")
            logger.warning(f"Fingerprints: {fingerprints}")
    
    return {
        "model": model_name,
        "num_runs": num_runs,
        "duration": duration,
        "all_identical": all_identical,
        "responses": responses,
        "seed": seed,
        "top_k": top_k,
        "top_p": top_p,
        "system_fingerprints": fingerprints if fingerprints else None,
        "fingerprint_identical": fingerprint_identical
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
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test model reproducibility')
    parser.add_argument('--vendor', choices=['all', 'aws', 'openai', 'google'], default='all',
                      help='Which vendor to test (default: all)')
    args = parser.parse_args()
    
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
    
    # Filter models based on vendor selection
    if args.vendor != 'all':
        if args.vendor == 'aws':
            available_models = [m for m in available_models if m in NOVA_MODELS]
        elif args.vendor == 'openai':
            available_models = [m for m in available_models if m in OPENAI_MODELS]
        elif args.vendor == 'google':
            available_models = [m for m in available_models if m in GEMINI_MODELS]
        logger.info(f"Testing only {args.vendor} models: {available_models}")
    
    if not available_models:
        logger.error(f"No models available for vendor: {args.vendor}")
        return
    
    results = []
    
    # Test each model
    for model in available_models:
        try:
            # Base test without seed or top_k
            result = test_model_reproducibility(model, prompt)
            results.append(result)
            
            # Log summary
            logger.info(f"\nResults for {model}:")
            logger.info(f"All responses identical: {result['all_identical']}")
            if result['fingerprint_identical'] is not None:
                logger.info(f"All fingerprints identical: {result['fingerprint_identical']}")
            logger.info(f"Total duration: {result['duration']:.2f} seconds")
            logger.info(f"Average time per run: {result['duration']/result['num_runs']:.2f} seconds")
            
            # Additional tests for OpenAI and Gemini models
            if model in OPENAI_MODELS:
                # Test with fixed seed and tiny top_p
                seed_topp_result = test_model_reproducibility(model, prompt, seed=42, top_p=0.1)
                results.append(seed_topp_result)
                logger.info(f"\nResults for {model} with seed=42 and top_p=0.1:")
                logger.info(f"All responses identical: {seed_topp_result['all_identical']}")
                if seed_topp_result['fingerprint_identical'] is not None:
                    logger.info(f"All fingerprints identical: {seed_topp_result['fingerprint_identical']}")
            elif model in GEMINI_MODELS:
                # Test with top_k=1
                topk_result = test_model_reproducibility(model, prompt, top_k=1)
                results.append(topk_result)
                logger.info(f"\nResults for {model} with top_k=1:")
                logger.info(f"All responses identical: {topk_result['all_identical']}")
                
                # Test with seed=42
                seed_result = test_model_reproducibility(model, prompt, seed=42)
                results.append(seed_result)
                logger.info(f"\nResults for {model} with seed=42:")
                logger.info(f"All responses identical: {seed_result['all_identical']}")
                
                # Test with both seed=42 and top_k=1
                seed_topk_result = test_model_reproducibility(model, prompt, seed=42, top_k=1)
                results.append(seed_topk_result)
                logger.info(f"\nResults for {model} with seed=42 and top_k=1:")
                logger.info(f"All responses identical: {seed_topk_result['all_identical']}")
            
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