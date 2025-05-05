#!/usr/bin/env python3
import argparse
import json
import os
import re
import traceback
import datetime
from pathlib import Path
from google.generativeai import configure, GenerativeModel, GenerationConfig

def load_file_content(file_path):
    """Load content from a file."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        traceback.print_exc()
        return None

def extract_metadata(filename):
    """Extract model and agent type from filename."""
    parts = Path(filename).stem.split('-')
    model = parts[-2] if len(parts) > 2 else 'unknown'
    agent = parts[-1] if len(parts) > 1 else 'unknown'
    return model, agent

def generate_readable_agent_name(filename):
    """Generate a human-readable name for an agent based on its filename."""
    configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = GenerativeModel('gemini-2.0-flash-lite', generation_config=GenerationConfig(temperature=0.0))
    
    prompt = f"""Take this filename '{filename}' and return a 2-3 word human-readable name that describes the agent configuration based on the filename. Use UK English spelling.
    
Examples:
- "20250502-095806-react-gpt-4o-mini.md" → "ReAct GPT-4o Mini"
- "20250502-100426-reflexion-gpt-4o-mini.md" → "Reflexion GPT-4o Mini"
- "20250502-101522-react-gemini-2.md" → "ReAct Gemini 2"

Your response should only contain the name, nothing else."""
    
    try:
        response = model.generate_content(prompt)
        readable_name = response.text.strip()
        return readable_name
    except Exception as e:
        print(f"Error generating readable agent name: {e}")
        traceback.print_exc()
        # Fall back to basic extraction
        return extract_metadata(filename)[1].capitalize()

def evaluate_outputs(eval_prompt, original_prompt, output_files, original_prompt_file=None):
    """Evaluate multiple output files against the original prompt using the LLM-as-judge."""
    configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = GenerativeModel('gemini-2.0-flash', generation_config=GenerationConfig(temperature=0.0))
    
    # Prepare agent outputs for the prompt
    agent_outputs = {}
    file_info = []
    
    for i, file_path in enumerate(output_files):
        content = load_file_content(file_path)
        if not content:
            continue
            
        filename = os.path.basename(file_path)
        readable_name = generate_readable_agent_name(filename)
        model_name, agent_type = extract_metadata(filename)
        
        agent_outputs[f"agent_{i}"] = {
            "name": readable_name,
            "output": content,
            "model": model_name,
            "type": agent_type
        }
        
        file_info.append({
            'file': file_path,
            'model': model_name,
            'agent': agent_type,
            'readable_name': readable_name,
            'index': i
        })
    
    # Format the evaluation prompt with all agent outputs
    formatted_prompt = eval_prompt.replace('{task_description}', original_prompt)\
        .replace('{input}', "The original task prompt")\
        .replace('{agent_outputs}', json.dumps(agent_outputs, indent=2))
    
    try:
        response = model.generate_content(formatted_prompt)
        print(f"Raw LLM response: {response.text}")  # Debug logging
        
        # Parse the structured evaluation response
        response_text = response.text if hasattr(response, 'text') else str(response)
        try:
            # Extract JSON from response text
            json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', response_text, re.DOTALL)
            if json_match:
                print("Found JSON in code block")
                evaluation = json.loads(json_match.group(1))
            else:
                print("Parsing raw JSON response")
                evaluation = json.loads(response_text)
                
            if not isinstance(evaluation, dict) or 'evaluation' not in evaluation:
                raise ValueError(f"Invalid evaluation format: {type(evaluation)}")
                
            # Return the full evaluation structure
            return evaluation, file_info, None, original_prompt
        except (json.JSONDecodeError, ValueError) as e:
            print(f"ERROR DETAILS:\n{'-'*40}")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Response text: {response_text}")
            traceback.print_exc()
            print(f"{'='*40}")
            return None, file_info, None, original_prompt
            
    except Exception as e:
        print(f"FATAL ERROR:\n{'-'*40}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        traceback.print_exc()
        print(f"{'='*40}")
        return None, file_info, None, original_prompt

def generate_comparative_assessment(original_prompt, outputs):
    """Generate a qualitative comparative assessment of multiple outputs.
    
    Args:
        original_prompt: The original prompt used for all agents
        outputs: List of dicts with 'file', 'model', 'agent', 'readable_name', and 'content' keys
    
    Returns:
        String containing the comparative assessment
    """
    configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = GenerativeModel('gemini-2.0-flash', generation_config=GenerationConfig(temperature=0.0))
    
    # Get a list of agent names for reference
    agent_names = [output.get('readable_name', f"{output['model']} ({output['agent']})") for output in outputs]
    
    # Start with the exact prompt specified by the user, with additional naming instructions
    comparison_prompt = f"""Given the input prompt and the results produced by a series of different agent configurations, perform an in-depth qualitative assessment of the relative merits of each. Create a new section for each report describing in detail, with as many subsections as necessary, the assessment of that agent output with respect to all the other agent outputs.

IMPORTANT: Always refer to each agent by its full name: {', '.join(agent_names)}. DO NOT use generic labels like "Output #1" or "Agent A" anywhere in your response.

FORMAT YOUR RESPONSE IN MARKDOWN with proper headings and subheadings.

"""
    
    # Add the original prompt
    comparison_prompt += f"ORIGINAL PROMPT:\n{original_prompt}\n\n"
    
    # Add each agent's output with its readable name as a label
    for i, output in enumerate(outputs):
        agent_label = output.get('readable_name', f"{output['model']} ({output['agent']})")
        comparison_prompt += f"\n\n{'='*80}\n{agent_label}\n{'='*80}\n\n{output['content']}\n\n"
    
    try:
        response = model.generate_content(comparison_prompt)
        return response.text
    except Exception as e:
        print(f"Error generating comparative assessment: {e}")
        traceback.print_exc()
        return "Error: Unable to generate comparative assessment."

def generate_comparison(evaluations, file_info, comparative_assessment, original_prompt, original_prompt_file=None):
    try:
        # Validate input structure
        if not isinstance(evaluations, dict) or 'evaluation' not in evaluations:
            raise ValueError(f"Expected evaluation dict, got {type(evaluations)}")
            
        evaluation_data = evaluations['evaluation']
        
        # Process agent evaluations
        evaluation_results = []
        
        # Get agent evaluations
        agent_evaluations = evaluation_data.get('agents', {})
        if not isinstance(agent_evaluations, dict):
            raise ValueError(f"Expected agents dict, got {type(agent_evaluations)}")
        
        # Generate report
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        output_file = os.path.join('example-output', f'comparison-{timestamp}.md')
        
        with open(output_file, 'w') as f:
            # Write header
            f.write(f"# Agent Comparison Report\n")
            f.write(f"Generated: {timestamp}\n\n")
            
            # Write individual evaluations
            for agent_name, scores in agent_evaluations.items():
                f.write(f"## {agent_name}\n\n")
                f.write(f"- Accuracy: {scores.get('accuracy', 'N/A')}\n")
                f.write(f"- Relevance: {scores.get('relevance', 'N/A')}\n")
                f.write(f"- Completeness: {scores.get('completeness', 'N/A')}\n")
                f.write(f"- Clarity: {scores.get('clarity', 'N/A')}\n\n")
            
            # Write consensus analysis
            if 'consensus_analysis' in evaluation_data:
                f.write(f"## Consensus Analysis\n\n{evaluation_data['consensus_analysis']}\n\n")
            
            # Write recommendations
            if 'recommendations' in evaluation_data:
                f.write(f"## Recommendations\n\n{evaluation_data['recommendations']}\n")
        
        return output_file
        
    except Exception as e:
        print(f"FATAL COMPARISON ERROR:")
        traceback.print_exc()
        return None

def generate_appendix(outputs, file_info, original_prompt):
    appendix = []
    appendix.append("\n# Appendix\n")
    appendix.append("\n## Original Prompt\n")
    appendix.append("```\n" + original_prompt + "\n```")
    appendix.append("\n## Agent Outputs\n")
    for info in file_info:
        readable_name = info.get('readable_name', f"{info['model']} ({info['agent']})")
        file_path = info.get('file', '')
        content = load_file_content(file_path)
        
        if content:
            appendix.append(f"\n### {readable_name}\n")
            appendix.append("```markdown\n" + content + "\n```")
    return '\n'.join(appendix)

def main():
    parser = argparse.ArgumentParser(description='Compare different outputs using LLM-as-Judge.')
    parser.add_argument('--prompt', required=True, help='Prompt file to use for evaluation')
    parser.add_argument('--output', help='Output file for the comparison report')
    parser.add_argument('outputs', nargs='+', help='Output files to compare')
    
    args = parser.parse_args()
    
    # Load the prompt
    original_prompt = load_file_content(args.prompt)
    original_prompt_file = args.prompt
    if not original_prompt:
        print(f"Error loading prompt: {args.prompt}")
        return
    
    # Load the evaluation prompt
    eval_prompt = load_file_content("prompts/llm-as-judge.txt")
    if not eval_prompt:
        print("Error loading LLM-as-judge.txt")
        return
    
    # Evaluate outputs
    evaluations, file_info, comparative_assessment, original_prompt = evaluate_outputs(eval_prompt, original_prompt, args.outputs, original_prompt_file)
    
    if evaluations is None:
        print("Evaluation failed - not saving results")
        return
    
    # Generate comparison markdown
    markdown_content = generate_comparison(evaluations, file_info, comparative_assessment, original_prompt, original_prompt_file)
    if not markdown_content:
        print("Error generating comparison")
        return
    
    # Generate appendix with all agent outputs
    appendix_content = generate_appendix(args.outputs, file_info, original_prompt)
    full_content = markdown_content + appendix_content
    
    # Save to output file
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_file = args.output if args.output else f"example-output/comparison-{timestamp}.md"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write(full_content)
    
    print(f"Comparison saved to {output_file}")

if __name__ == '__main__':
    main()
