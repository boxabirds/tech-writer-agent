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
    """Generate a human-readable name for an agent based on its filename.
    
    Examples:
    - "20250502-095806-LandscapeHub-react-gpt-4o-mini.md" → "LandscapeHub ReAct GPT-4o Mini"
    - "20250502-100426-LandscapeHub-reflexion-gpt-4o-mini.md" → "LandscapeHub Reflexion GPT-4o Mini"
    - "20250502-101522-LandscapeHub-react-gemini-2.md" → "LandscapeHub ReAct Gemini 2"
    """
    try:
        # Pattern matching date-time-[repo]-agent-model format
        # Group 1: Repository name (optional)
        # Group 2: Agent type
        # Group 3: Model name
        pattern = r'^\d{8}-\d{6}(?:-([^-]+))?-([^-]+)-(.+)\.md$'
        
        match = re.match(pattern, filename)
        if not match:
            return Path(filename).stem
            
        repo_name, agent_type, model_name = match.groups()
        
        # Format agent type (react -> ReAct)
        if agent_type.lower() == "react":
            agent_type = "ReAct"
        elif agent_type.lower() == "reflexion":
            agent_type = "Reflexion"
        else:
            agent_type = agent_type.capitalize()
            
        # Format model name
        model_parts = model_name.split('-')
        if len(model_parts) > 1:
            # For models like gpt-4o-mini or gemini-2.0-flash
            if model_parts[0] == "gpt" and model_parts[1][0].isdigit():
                # Handle GPT models
                formatted_model = f"GPT-{model_parts[1]}"
                if len(model_parts) > 2:
                    formatted_model += f" {' '.join(p.capitalize() for p in model_parts[2:])}"
            elif model_parts[0] == "gemini":
                # Handle Gemini models
                formatted_model = f"Gemini {'.'.join(model_parts[1:])}"
            else:
                # Generic handling
                formatted_model = ' '.join(p.capitalize() for p in model_parts)
        else:
            formatted_model = model_name.capitalize()
            
        # Build the final readable name
        if repo_name:
            return f"{repo_name} {agent_type} {formatted_model}"
        else:
            return f"{agent_type} {formatted_model}"
            
    except Exception as e:
        print(f"Error generating readable agent name: {e}")
        traceback.print_exc()
        return Path(filename).stem  # Fallback to filename stem

def evaluate_outputs(eval_prompt, original_prompt, output_files, original_prompt_file=None):
    """Evaluate multiple output files against the original prompt using the LLM-as-judge."""
    configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = GenerativeModel('gemini-2.5-pro-exp-03-25', generation_config=GenerationConfig(temperature=0.0))
    
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
        
        # Use readable_name as the key instead of agent_i
        agent_outputs[readable_name] = {
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
        print(f"Raw LLM response: {response.text[:500]}...")  # Debug logging
        
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
    #model = GenerativeModel('gemini-2.0-flash', generation_config=GenerationConfig(temperature=0.0))
    model = GenerativeModel('gemini-2.5-pro-exp-03-25', generation_config=GenerationConfig(temperature=0.0))
    
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
    """Generate comparison report from evaluations."""
    try:
        # Validate input structure
        if not isinstance(evaluations, dict) or 'evaluation' not in evaluations:
            raise ValueError(f"Expected evaluation dict, got {type(evaluations)}")
            
        evaluation_data = evaluations['evaluation']
        
        # Get agent evaluations
        agent_evaluations = evaluation_data.get('agents', {})
        if not isinstance(agent_evaluations, dict):
            raise ValueError(f"Expected agents dict, got {type(agent_evaluations)}")
        
        # Build the report content
        report_lines = []
        
        # Write header
        report_lines.append("# Agent Comparison Report")
        report_lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Write scores summary table
        report_lines.append("## Scores Summary")
        report_lines.append("")
        report_lines.append("| Agent | Accuracy | Relevance | Completeness | Clarity | Total |")
        report_lines.append("|-------|----------|-----------|--------------|---------|-------|")
        
        for agent_name, scores in agent_evaluations.items():
            accuracy = scores.get('accuracy', 'N/A')
            relevance = scores.get('relevance', 'N/A')
            completeness = scores.get('completeness', 'N/A')
            clarity = scores.get('clarity', 'N/A')
            total = scores.get('total_score', 'N/A')
            
            report_lines.append(f"| {agent_name} | {accuracy} | {relevance} | {completeness} | {clarity} | {total} |")
        
        report_lines.append("")
        
        # Write individual evaluations with more details
        report_lines.append("## Individual Agent Evaluations")
        report_lines.append("")
        for agent_name, scores in agent_evaluations.items():
            report_lines.append(f"### {agent_name}")
            report_lines.append("")
            report_lines.append(f"- **Accuracy**: {scores.get('accuracy', 'N/A')}")
            report_lines.append(f"- **Relevance**: {scores.get('relevance', 'N/A')}")
            report_lines.append(f"- **Completeness**: {scores.get('completeness', 'N/A')}")
            report_lines.append(f"- **Clarity**: {scores.get('clarity', 'N/A')}")
            report_lines.append(f"- **Total Score**: {scores.get('total_score', 'N/A')}")
            
            # Add outliers if available
            outliers = scores.get('outliers', [])
            if outliers:
                report_lines.append("")
                report_lines.append("**Outliers/Issues**:")
                for outlier in outliers:
                    report_lines.append(f"- {outlier}")
            
            report_lines.append("")
        
        # Write consensus analysis
        if 'consensus_analysis' in evaluation_data:
            report_lines.append(f"## Consensus Analysis")
            report_lines.append("")
            report_lines.append(evaluation_data['consensus_analysis'])
            report_lines.append("")
        
        # Write hallucinations section if available
        if 'hallucinations' in evaluation_data and evaluation_data['hallucinations']:
            report_lines.append("## Hallucinations")
            report_lines.append("")
            
            for hallucination, details in evaluation_data['hallucinations'].items():
                report_lines.append(f"### {hallucination}")
                report_lines.append("")
                
                if 'agents' in details:
                    agent_list = ", ".join(details['agents'])
                    report_lines.append(f"**Found in**: {agent_list}")
                    report_lines.append("")
                
                if 'evidence' in details:
                    report_lines.append(f"**Evidence**: {details['evidence']}")
                    report_lines.append("")
        
        # Write recommendations
        if 'recommendations' in evaluation_data:
            report_lines.append(f"## Recommendations")
            report_lines.append("")
            report_lines.append(evaluation_data['recommendations'])
            report_lines.append("")
        
        # Add the revised prompt if available
        if 'revised_prompt' in evaluation_data:
            report_lines.append(f"## Revised Prompt")
            report_lines.append("")
            report_lines.append("Based on the evaluation findings, the following revised prompt is suggested to address the identified issues:")
            report_lines.append("")
            report_lines.append("```")
            revised_prompt = evaluation_data['revised_prompt']
            # Extract the revised prompt from the response text
            revised_prompt_match = re.search(r'```(?:markdown)?\s*(.*?)\s*```', revised_prompt, re.DOTALL)
            if revised_prompt_match:
                report_lines.append(revised_prompt_match.group(1))
            else:
                report_lines.append(revised_prompt)
            report_lines.append("```")
            report_lines.append("")
        
        # Return the full content
        return "\n".join(report_lines)
        
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
    parser = argparse.ArgumentParser(description='Evaluate multiple outputs against original prompt')
    parser.add_argument('--prompt', type=str, help='Path to evaluation prompt', required=True)
    parser.add_argument('--task-prompt', type=str, help='Path to the original task prompt', required=False)
    parser.add_argument('output_files', type=str, nargs='+', help='Paths to output files to evaluate')
    args = parser.parse_args()
    
    # Load the evaluation prompt
    eval_prompt = load_file_content(args.prompt)
    if not eval_prompt:
        print(f"Error loading evaluation prompt from {args.prompt}")
        return
    
    # Extract the original prompt from file or use the evaluation prompt
    original_prompt = None
    
    # Try to get original prompt from the --task-prompt argument if provided
    if args.task_prompt:
        original_prompt = load_file_content(args.task_prompt)
        if original_prompt:
            print(f"Loaded original task prompt from {args.task_prompt}")
    
    # If not specified, try to extract from the output files
    if not original_prompt:
        try:
            for file_path in args.output_files:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                    # Try multiple patterns to find the original prompt
                    patterns = [
                        r'# Original Prompt\s+```\s+(.*?)\s+```',
                        r'# Prompt\s+```\s+(.*?)\s+```',
                        r'## Prompt\s+```\s+(.*?)\s+```',
                        r'## Original Prompt\s+```\s+(.*?)\s+```',
                        r'# Architecture Prompt\s+```\s+(.*?)\s+```',
                        r'# Comprehensive Architecture Analysis\s+(.*?)(?=\n\n)',
                    ]
                    
                    for pattern in patterns:
                        prompt_match = re.search(pattern, content, re.DOTALL)
                        if prompt_match:
                            original_prompt = prompt_match.group(1)
                            print(f"Extracted original prompt from {file_path}")
                            break
                    
                    if original_prompt:
                        break
        except Exception as e:
            print(f"Error extracting original prompt: {e}")
            traceback.print_exc()
    
    # If we still don't have a prompt, try to get it from architecture.prompt.txt 
    if not original_prompt:
        architecture_prompt_path = os.path.join('prompts', 'architecture.prompt.txt')
        if os.path.exists(architecture_prompt_path):
            original_prompt = load_file_content(architecture_prompt_path)
            print(f"Loaded original prompt from default path: {architecture_prompt_path}")
    
    # If all else fails, use the evaluation prompt itself
    if not original_prompt:
        print("WARNING: Could not find original prompt, using evaluation prompt instead")
        original_prompt = eval_prompt
    
    # Log the original prompt that was used to generate the agent outputs
    print("\nORIGINAL PROMPT USED TO GENERATE REPORTS:")
    print("=" * 50)
    print(original_prompt[:500] + "..." if len(original_prompt) > 500 else original_prompt)
    print("=" * 50 + "\n")
    
    # Evaluate the outputs
    evaluations, file_info, comparative_assessment, original_prompt = evaluate_outputs(
        eval_prompt=eval_prompt,
        original_prompt=original_prompt,
        output_files=args.output_files,
        original_prompt_file=args.task_prompt
    )
    
    # Generate comparison and save to file
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_file = os.path.join('example-output', f'comparison-{timestamp}.md')
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    if evaluations:
        # Generate the comparison report
        comparison_content = generate_comparison(
            evaluations=evaluations,
            file_info=file_info,
            comparative_assessment=comparative_assessment,
            original_prompt=original_prompt,
            original_prompt_file=args.task_prompt
        )
        
        # Generate appendix with agent outputs
        appendix_content = generate_appendix(args.output_files, file_info, original_prompt)
        
        # Write the complete report to file
        with open(output_file, 'w') as f:
            f.write(comparison_content)
            f.write("\n\n")
            f.write(appendix_content)
            
        print(f"Comparison saved to {output_file}")
    else:
        print("Evaluation failed - not saving results")

if __name__ == '__main__':
    main()
