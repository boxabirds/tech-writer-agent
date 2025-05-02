#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from google.generativeai import configure, GenerativeModel

def load_file_content(file_path):
    """Load content from a file."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def evaluate_outputs(eval_prompt, original_prompt, output_files):
    """Evaluate multiple output files against the original prompt."""
    configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = GenerativeModel('gemini-2.0-flash')
    
    evaluations = []
    for file_path in output_files:
        content = load_file_content(file_path)
        if not content:
            continue
            
        prompt = f"""
        {eval_prompt}
        Task Description:
        {original_prompt}
        Input Provided to Agents:
        The architecture analysis prompt
        Agent Output:
        {content}
        """
        
        try:
            response = model.generate_content(prompt)
            evaluations.append({
                'file': str(file_path),
                'evaluation': response.text
            })
        except Exception as e:
            print(f"Error evaluating {file_path}: {e}")
    
    return evaluations

def generate_comparison(evaluations):
    """Generate comparison report from multiple evaluations."""
    comparison = {
        'date': datetime.datetime.now().isoformat(),
        'model': 'gemini-2.0-flash',
        'evaluations': evaluations,
        'summary': {}
    }
    
    # Add comparison logic here
    return comparison

def main():
    parser = argparse.ArgumentParser(description='Evaluate tech writer agent outputs')
    parser.add_argument('--eval-prompt', default='prompts/llm-as-judge.txt',
                       help='Path to evaluation prompt')
    parser.add_argument('--prompt', required=True,
                       help='Path to original prompt used by agents')
    parser.add_argument('outputs', nargs='+',
                       help='List of output .md files to evaluate')
    args = parser.parse_args()

    eval_prompt = load_file_content(args.eval_prompt)
    original_prompt = load_file_content(args.prompt)
    
    if not all([eval_prompt, original_prompt]):
        return

    evaluations = evaluate_outputs(eval_prompt, original_prompt, args.outputs)
    comparison = generate_comparison(evaluations)
    
    output_path = Path('example-output') / f"comparison-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    with open(output_path, 'w') as f:
        json.dump(comparison, f, indent=2)
    
    print(f"Comparison saved to {output_path}")

if __name__ == '__main__':
    import datetime
    main()
