#!/usr/bin/env python3
import argparse
import json
import os
import re
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
        # Fall back to basic extraction
        return extract_metadata(filename)[1].capitalize()

def evaluate_outputs(eval_prompt, original_prompt, output_files):
    """Evaluate multiple output files against the original prompt."""
    configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = GenerativeModel('gemini-2.0-flash', generation_config=GenerationConfig(temperature=0.0))
    
    evaluations = []
    file_info = []
    outputs_for_comparison = []
    
    for file_path in output_files:
        content = load_file_content(file_path)
        if not content:
            continue
        
        # Generate a readable agent name
        filename = os.path.basename(file_path)
        readable_name = generate_readable_agent_name(filename)
        
        # Extract model and agent (still needed for backward compatibility)
        model_name, agent_type = extract_metadata(file_path)
        
        # Store basic file info with readable name
        file_info.append({
            'file': file_path,
            'model': model_name,
            'agent': agent_type,
            'readable_name': readable_name
        })
        
        # Store output for comparative assessment
        outputs_for_comparison.append({
            'file': file_path,
            'model': model_name,
            'agent': agent_type,
            'readable_name': readable_name,
            'content': content
        })
            
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
                'model': model_name,
                'agent': agent_type,
                'evaluation': response.text
            })
        except Exception as e:
            print(f"Error evaluating {file_path}: {e}")
    
    # Generate the comparative assessment
    comparative_assessment = None
    if len(outputs_for_comparison) > 1:
        comparative_assessment = generate_comparative_assessment(original_prompt, outputs_for_comparison)
    
    return evaluations, file_info, comparative_assessment, original_prompt

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
        return "Error: Unable to generate comparative assessment."

def generate_comparison(evaluations, file_info, comparative_assessment, original_prompt):
    """Generate comparison report from evaluations and file info."""
    # Parse evaluation results
    evaluation_results = []
    
    # Map for agent references - dynamically handle any number of agents
    agent_name_map = {}
    agent_index_map = {}  # Map agent_a -> 0, agent_b -> 1, etc.
    
    for i, info in enumerate(file_info):
        readable_name = info.get('readable_name', f"Agent {chr(65+i)}")
        agent_key = f"agent_{chr(97+i)}"  # agent_a, agent_b, agent_c, etc.
        agent_letter = f"Agent {chr(65+i)}"  # Agent A, Agent B, Agent C, etc.
        
        # Map both lowercase and uppercase agent references to readable names
        agent_name_map[agent_key] = readable_name
        agent_name_map[agent_letter] = readable_name
        agent_name_map[agent_key.upper()] = readable_name
        agent_name_map[agent_letter.lower()] = readable_name
        
        # Also store the index for each agent key
        agent_index_map[agent_key] = i
    
    for eval_item in evaluations:
        try:
            file_path = eval_item['file']
            model = eval_item['model']
            agent = eval_item['agent']
            raw_text = eval_item['evaluation']
            
            # Extract JSON from the response
            json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', raw_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = re.search(r'{.*}', raw_text, re.DOTALL)
                if json_str:
                    json_str = json_str.group(0)
                    
            # Try to parse the JSON
            try:
                if json_str:
                    # Replace invalid control characters
                    json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
                    data = json.loads(json_str)
                    
                    # Navigate through possible JSON structures
                    if 'evaluation' in data:
                        eval_data = data['evaluation']
                    else:
                        eval_data = data
                    
                    # Create a result with base information
                    result = {
                        'file': file_path,
                        'model': model,
                        'agent': agent
                    }
                    
                    # Extract agent scores dynamically
                    for key, value in eval_data.items():
                        if key.startswith('agent_'):
                            result[key] = value
                        elif key == 'winner':
                            # Map winner to readable name if it's an agent reference
                            winner = eval_data.get('winner', 'Tie')
                            if winner in agent_name_map:
                                result['winner'] = agent_name_map[winner]
                            else:
                                result['winner'] = winner
                        elif key == 'rationale':
                            # Replace agent references in rationale
                            rationale = eval_data.get('rationale', 'No rationale provided')
                            for agent_ref, agent_name in agent_name_map.items():
                                rationale = rationale.replace(agent_ref, agent_name)
                            result['rationale'] = rationale
                        else:
                            # Copy any other keys as-is
                            result[key] = value
                    
                    evaluation_results.append(result)
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                print(f"Error parsing evaluation JSON: {e}")
                # Extract scores manually using regex
                try:
                    # Create a result with extracted info
                    result = {
                        'file': file_path,
                        'model': model,
                        'agent': agent
                    }
                    
                    # Try to extract scores for all possible agents using regex
                    for i, info in enumerate(file_info):
                        agent_key = f"agent_{chr(97+i)}"  # agent_a, agent_b, agent_c, etc.
                        
                        agent_scores = {}
                        
                        # Extract scores for this agent using regex
                        for criterion in ['accuracy', 'relevance', 'completeness', 'clarity', 'total_score']:
                            # Try to match score for this criterion for this agent
                            pattern = fr'"?{agent_key}"?.*?"?{criterion}"?[:\s]+(\d+)'
                            match = re.search(pattern, raw_text)
                            if match:
                                agent_scores[criterion] = int(match.group(1))
                        
                        # Only add this agent's scores if we found any
                        if agent_scores:
                            result[agent_key] = agent_scores
                    
                    # Extract winner
                    winner_match = re.search(r'"winner"[:\s]+"([^"]+)"', raw_text)
                    winner = winner_match.group(1) if winner_match else "Tie"
                    
                    # Map winner to readable name if it's an agent reference
                    if winner in agent_name_map:
                        result['winner'] = agent_name_map[winner]
                    else:
                        result['winner'] = winner
                    
                    # Extract rationale
                    rationale_match = re.search(r'"rationale"[:\s]+"([^"]+)"', raw_text)
                    rationale = rationale_match.group(1) if rationale_match else "No rationale provided"
                    
                    # Replace agent references in rationale text
                    for agent_ref, agent_name in agent_name_map.items():
                        rationale = rationale.replace(agent_ref, agent_name)
                    
                    result['rationale'] = rationale
                    
                    evaluation_results.append(result)
                except Exception as regex_error:
                    print(f"Error extracting scores with regex: {regex_error}")
                    # Fall back to using the raw text
                    
                    # Replace agent references in raw text
                    raw_text_clean = raw_text
                    for agent_ref, agent_name in agent_name_map.items():
                        raw_text_clean = raw_text_clean.replace(agent_ref, agent_name)
                    
                    evaluation_results.append({
                        'file': file_path,
                        'model': model,
                        'agent': agent,
                        'raw_text': raw_text_clean
                    })
        except Exception as e:
            print(f"Error processing evaluation: {e}")
    
    # Get human-readable agent names for the title
    agent_names = []
    for info in file_info:
        agent_names.append(info.get('readable_name', f"Agent {chr(65+len(agent_names))}"))
    
    # Generate markdown output
    markdown = [
        f"# Architecture Analysis Comparison: {' vs '.join(agent_names)}",
        "\n## Evaluation Summary",
        f"- **Date**: {datetime.datetime.now().strftime('%Y-%m-%d')}",
        f"- **Models Compared**: {' vs '.join([info.get('readable_name', f'{info['model']} ({info['agent']})') for info in file_info])}",
        "- **Prompt Used**: [architecture.prompt.txt](../prompts/architecture.prompt.txt)",
        "- **Evaluation Criteria**: [llm-as-judge.txt](../prompts/llm-as-judge.txt)",
        "\n## Judge Scores\n"
    ]
    
    # Set up table headers with readable agent names
    agent_labels = [info.get('readable_name', f"Agent {chr(65+i)}") for i, info in enumerate(file_info)]
    
    # Create table header with proper pipe formatting
    header = "| Criteria |"
    for label in agent_labels:
        header += f" {label} |"
    markdown.append(header)
    
    # Create separator row with proper number of columns
    separator = "|:--------|"
    for _ in agent_labels:
        separator += ":--------|"
    markdown.append(separator)
        
    # Add scores for each criterion
    for criterion in ['accuracy', 'relevance', 'completeness', 'clarity', 'total_score']:
        row = f"| **{criterion.title()}** |"
        
        # Get scores from all evaluations for each agent
        for i, info in enumerate(file_info):
            agent_key = f"agent_{chr(97+i)}"  # agent_a, agent_b, agent_c, etc.
            score = "N/A"
            
            for result in evaluation_results:
                if agent_key in result and criterion in result[agent_key]:
                    score = result[agent_key][criterion]
                    break
            
            row += f" {score} |"
        
        markdown.append(row)
    
    # Add winner row
    winner_row = "| **Winner** |"
    
    # Just take the winner from the first evaluation_result if available
    if evaluation_results and 'winner' in evaluation_results[0]:
        winner = evaluation_results[0]['winner']
        for _ in file_info:
            winner_row += f" {winner} |"
    else:
        for _ in file_info:
            winner_row += " Tie |"
            
    markdown.append(winner_row)
    
    # Add judge's rationale
    markdown.append("\n## Qualitative Assessment\n")
    
    if evaluation_results:
        # Use the rationale from the first result
        if 'rationale' in evaluation_results[0]:
            markdown.append(evaluation_results[0]['rationale'])
        elif 'raw_text' in evaluation_results[0]:
            # Clean up raw text for display
            clean_text = re.sub(r'```json.*?```', '', evaluation_results[0]['raw_text'], flags=re.DOTALL)
            clean_text = re.sub(r'{.*}', '', clean_text, flags=re.DOTALL)
            markdown.append(clean_text.strip())
        
        # Add winner conclusion
        for result in evaluation_results:
            if 'winner' in result:
                winner = result.get('winner', 'Tie')
                if winner != 'Tie':
                    markdown.append(f"\n\n**Overall Winner: {winner}**")
                else:
                    markdown.append("\n\n**Overall Result: Tie**")
                break
    
    # Add comparative assessment
    if comparative_assessment:
        markdown.append("\n## Comparative Assessment\n")
        markdown.append(comparative_assessment)
    
    # Add appendix with original prompt and agent outputs
    markdown.append("\n# Appendix\n")
    
    # Add original prompt
    markdown.append("\n## Original Prompt\n")
    markdown.append("```\n" + original_prompt + "\n```")
    
    # Add each agent output
    markdown.append("\n## Agent Outputs\n")
    for info in file_info:
        readable_name = info.get('readable_name', f"{info['model']} ({info['agent']})")
        file_path = info.get('file', '')
        content = load_file_content(file_path)
        
        if content:
            markdown.append(f"\n### {readable_name}\n")
            markdown.append("```markdown\n" + content + "\n```")
    
    return "\n".join(markdown)

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

    evaluations, file_info, comparative_assessment, original_prompt = evaluate_outputs(eval_prompt, original_prompt, args.outputs)
    comparison = generate_comparison(evaluations, file_info, comparative_assessment, original_prompt)
    
    output_path = Path('example-output') / f"comparison-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    with open(output_path, 'w') as f:
        f.write(comparison)
    
    print(f"Comparison saved to {output_path}")

if __name__ == '__main__':
    main()
