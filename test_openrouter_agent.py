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
    # Use explicit supported models from the agent's list
    return [
        {
            "directory": "test-data/test-tools",
            "prompt_file": "test-data/prompts/count-python-files.prompt.txt",
            "model": "gpt-4o-mini"
        },
        {
            "directory": "test-data/test-tools",
            "prompt_file": "test-data/prompts/count-python-files.prompt.txt",
            "model": "gemini-2.0-flash"
        }
    ]

def run_agent(directory, prompt_file, model):
    script = "tech-writer-from-scratch-openrouter.py"
    cmd = [sys.executable, script, directory, prompt_file, "--model", model, "--json"]
    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    end = time.time()
    out = proc.stdout
    # Check agent exit code and print error if nonzero
    if proc.returncode != 0:
        print(f"Agent failed with exit code {proc.returncode}.")
        print("STDOUT:\n" + out)
        print("STDERR:\n" + proc.stderr)
        sys.exit(proc.returncode)
    try:
        result_json = json.loads(out)
        assert "cost_usd" in result_json and isinstance(result_json["cost_usd"], (float, int)), "cost_usd missing or not numeric in agent output"
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
        print("Failed to parse agent output as JSON or assertion failed.")
        print("Raw output:\n" + out)
        print("STDERR:\n" + proc.stderr)
        raise

def main():
    cases = get_test_cases()
    results = []
    print("Running OpenRouter agent benchmark...\n")
    for case in cases:
        print(f"\nModel: {case['model']} | Directory: {case['directory']} | Prompt: {case['prompt_file']}")
        result = run_agent(case['directory'], case['prompt_file'], case['model'])
        if not result.get('success', True):
            print("Agent run failed. Full output:")
            print(json.dumps(result, indent=2))
        results.append(result)
        print(f"  Tokens: {result.get('tokens', '-') } | Cost: ${result.get('cost', 0.0):.6f} | Runtime: {result.get('runtime', 0.0):.2f}s | Success: {result.get('success', False)}")
        print()
    print("\nSummary Table:\n")
    print(f"{'Model':<20} {'Tokens':>10} {'Cost (USD)':>12} {'Runtime (s)':>12} {'Success':>8}")
    print("-" * 65)
    for r in results:
        print(f"{r['model']:<20} {r['tokens'] or '-':>10} {r['cost'] if r['cost'] is not None else '-':>12} {r['runtime']:>12.2f} {str(r['success']):>8}")

if __name__ == "__main__":
    main()
