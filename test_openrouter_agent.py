"""
Test and Benchmark Script for TechWriterAgent (OpenRouter)
=========================================================
Runs the OpenRouter agent on a sample prompt/codebase, records runtime, token usage, and cost, and outputs a summary table.
"""
import subprocess
import time
import os
import sys
import json
from pathlib import Path

# Configuration
def get_test_cases():
    # Add more test cases as needed
    return [
        {
            "directory": "test-data/test-tools",
            "prompt_file": "test-data/prompts/count-python-files.prompt.txt",
            "model": "openai/gpt-4o"
        },
        {
            "directory": "test-data/test-tools",
            "prompt_file": "test-data/prompts/count-python-files.prompt.txt",
            "model": "google/gemini-pro"
        }
    ]

def run_agent(directory, prompt_file, model):
    script = "tech-writer-from-scratch-openrouter.py"
    cmd = [sys.executable, script, directory, prompt_file, "--model", model, "--json"]
    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    end = time.time()
    out = proc.stdout
    try:
        result_json = json.loads(out)
        return {
            "model": model,
            "tokens": result_json.get("tokens"),
            "cost": result_json.get("cost_usd"),
            "runtime": result_json.get("runtime"),
            "success": result_json.get("success"),
            "stdout": out,
            "stderr": proc.stderr
        }
    except Exception as e:
        return {
            "model": model,
            "tokens": None,
            "cost": None,
            "runtime": end - start,
            "success": False,
            "stdout": out,
            "stderr": proc.stderr + f"\nJSON parse error: {str(e)}"
        }

def main():
    cases = get_test_cases()
    results = []
    print("Running OpenRouter agent benchmark...\n")
    for case in cases:
        print(f"Model: {case['model']} | Directory: {case['directory']} | Prompt: {case['prompt_file']}")
        result = run_agent(case['directory'], case['prompt_file'], case['model'])
        results.append(result)
        print(f"  Tokens: {result['tokens']} | Cost: ${result['cost']:.6f} | Runtime: {result['runtime']:.2f}s | Success: {result['success']}")
        print()
    print("\nSummary Table:\n")
    print(f"{'Model':<20} {'Tokens':>10} {'Cost (USD)':>12} {'Runtime (s)':>12} {'Success':>8}")
    print("-" * 65)
    for r in results:
        print(f"{r['model']:<20} {r['tokens'] or '-':>10} {r['cost'] if r['cost'] is not None else '-':>12} {r['runtime']:>12.2f} {str(r['success']):>8}")

if __name__ == "__main__":
    main()
