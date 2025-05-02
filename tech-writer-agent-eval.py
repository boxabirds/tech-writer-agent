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
    
    return evaluations, file_info, comparative_assessment

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

def generate_comparison(evaluations, file_info, comparative_assessment):
    """Generate comparison report from evaluations and file info."""
    # Parse evaluation results
    evaluation_results = []
    
    # Map for agent references
    agent_name_map = {}
    if len(file_info) >= 2:
        agent_name_map = {
            'agent_a': file_info[0].get('readable_name', 'Agent A'),
            'agent_b': file_info[1].get('readable_name', 'Agent B'),
            'Agent A': file_info[0].get('readable_name', 'Agent A'),
            'Agent B': file_info[1].get('readable_name', 'Agent B')
        }
    
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
                        
                    # Extract agent scores and winner info
                    agent_a = eval_data.get('agent_a', {})
                    agent_b = eval_data.get('agent_b', {})
                    winner = eval_data.get('winner', 'Unknown')
                    rationale = eval_data.get('rationale', 'No rationale provided')
                    
                    # Replace agent references in rationale text
                    for agent_ref, agent_name in agent_name_map.items():
                        rationale = rationale.replace(agent_ref, agent_name)
                        # Also handle lowercase matches
                        rationale = rationale.replace(agent_ref.lower(), agent_name)
                    
                    # Map winner to readable name
                    if winner in agent_name_map:
                        winner = agent_name_map[winner]
                    
                    evaluation_results.append({
                        'file': file_path,
                        'model': model,
                        'agent': agent,
                        'agent_a': agent_a,
                        'agent_b': agent_b,
                        'winner': winner,
                        'rationale': rationale
                    })
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                print(f"Error parsing evaluation JSON: {e}")
                # Extract scores manually using regex
                try:
                    # Try to extract scores using regex patterns
                    agent_a = {}
                    agent_b = {}
                    
                    # Extract accuracy scores
                    accuracy_a = re.search(r'"agent_a".*?"accuracy"[:\s]+(\d+)', raw_text)
                    accuracy_b = re.search(r'"agent_b".*?"accuracy"[:\s]+(\d+)', raw_text)
                    if accuracy_a: agent_a['accuracy'] = int(accuracy_a.group(1))
                    if accuracy_b: agent_b['accuracy'] = int(accuracy_b.group(1))
                    
                    # Extract relevance scores
                    relevance_a = re.search(r'"agent_a".*?"relevance"[:\s]+(\d+)', raw_text)
                    relevance_b = re.search(r'"agent_b".*?"relevance"[:\s]+(\d+)', raw_text)
                    if relevance_a: agent_a['relevance'] = int(relevance_a.group(1))
                    if relevance_b: agent_b['relevance'] = int(relevance_b.group(1))
                    
                    # Extract completeness scores
                    completeness_a = re.search(r'"agent_a".*?"completeness"[:\s]+(\d+)', raw_text)
                    completeness_b = re.search(r'"agent_b".*?"completeness"[:\s]+(\d+)', raw_text)
                    if completeness_a: agent_a['completeness'] = int(completeness_a.group(1))
                    if completeness_b: agent_b['completeness'] = int(completeness_b.group(1))
                    
                    # Extract clarity scores
                    clarity_a = re.search(r'"agent_a".*?"clarity"[:\s]+(\d+)', raw_text)
                    clarity_b = re.search(r'"agent_b".*?"clarity"[:\s]+(\d+)', raw_text)
                    if clarity_a: agent_a['clarity'] = int(clarity_a.group(1))
                    if clarity_b: agent_b['clarity'] = int(clarity_b.group(1))
                    
                    # Extract total scores
                    total_a = re.search(r'"agent_a".*?"total_score"[:\s]+(\d+)', raw_text)
                    total_b = re.search(r'"agent_b".*?"total_score"[:\s]+(\d+)', raw_text)
                    if total_a: agent_a['total_score'] = int(total_a.group(1))
                    if total_b: agent_b['total_score'] = int(total_b.group(1))
                    
                    # Extract winner
                    winner_match = re.search(r'"winner"[:\s]+"([^"]+)"', raw_text)
                    winner = winner_match.group(1) if winner_match else "Unknown"
                    
                    # Extract rationale
                    rationale_match = re.search(r'"rationale"[:\s]+"([^"]+)"', raw_text)
                    rationale = rationale_match.group(1) if rationale_match else "No rationale provided"
                    
                    # Replace agent references in rationale text
                    for agent_ref, agent_name in agent_name_map.items():
                        rationale = rationale.replace(agent_ref, agent_name)
                        # Also handle lowercase matches
                        rationale = rationale.replace(agent_ref.lower(), agent_name)
                    
                    # Map winner to readable name
                    if winner in agent_name_map:
                        winner = agent_name_map[winner]
                    
                    evaluation_results.append({
                        'file': file_path,
                        'model': model,
                        'agent': agent,
                        'agent_a': agent_a,
                        'agent_b': agent_b,
                        'winner': winner,
                        'rationale': rationale
                    })
                except Exception as regex_error:
                    print(f"Error extracting scores with regex: {regex_error}")
                    # Fall back to using the raw text
                    
                    # Replace agent references in raw text
                    for agent_ref, agent_name in agent_name_map.items():
                        raw_text = raw_text.replace(agent_ref, agent_name)
                        # Also handle lowercase matches
                        raw_text = raw_text.replace(agent_ref.lower(), agent_name)
                    
                    evaluation_results.append({
                        'file': file_path,
                        'model': model,
                        'agent': agent,
                        'raw_text': raw_text
                    })
        except Exception as e:
            print(f"Error processing evaluation: {e}")
    
    # Get human-readable agent names for the title
    agent_names = []
    for info in file_info:
        agent_names.append(info.get('readable_name', f"{info['agent']}"))
    
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
    
    # Create score table
    if evaluation_results:
        # Set up table headers with readable agent names
        agent_labels = [info.get('readable_name', f"Agent {chr(65+i)}") for i, info in enumerate(file_info[:2])]
        if len(agent_labels) >= 2:
            markdown.append(f"| Criteria | {agent_labels[0]} | {agent_labels[1]} |")
            markdown.append("|:--------|:--------|:--------|")
            
            # Add scores for each criterion
            for criterion in ['accuracy', 'relevance', 'completeness', 'clarity', 'total_score']:
                row = [f"| **{criterion.title()}** |"]
                
                # Get scores from all evaluations
                for result in evaluation_results:
                    if 'agent_a' in result and criterion in result['agent_a']:
                        row.append(f" {result['agent_a'][criterion]} |")
                    else:
                        row.append(" N/A |")
                        
                    if 'agent_b' in result and criterion in result['agent_b']:
                        row.append(f" {result['agent_b'][criterion]} |")
                    else:
                        row.append(" N/A |")
                
                markdown.append("".join(row[:3]))  # Limit to first 3 columns
            
            # Add winner row
            winner_row = ["| **Winner** |"]
            for result in evaluation_results:
                winner = result.get('winner', 'Tie')
                # Map the winner to readable name if needed
                if winner in ['agent_a', 'agent_b', 'Agent A', 'Agent B']:
                    mapped_winner = agent_name_map.get(winner, winner)
                    winner_row.append(f" {mapped_winner} |")
                else:
                    winner_row.append(f" {winner} |")
            markdown.append("".join(winner_row[:2]))  # Just one winner column
    
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
        winner_counts = {}
        for result in evaluation_results:
            winner = result.get('winner', 'Tie')
            # Map the winner to readable name if needed
            if winner in ['agent_a', 'agent_b', 'Agent A', 'Agent B']:
                winner = agent_name_map.get(winner, winner)
            winner_counts[winner] = winner_counts.get(winner, 0) + 1
        
        most_common_winner = max(winner_counts.items(), key=lambda x: x[1])[0]
        
        if most_common_winner != 'Tie':
            markdown.append(f"\n\n**Overall Winner: {most_common_winner}**")
        else:
            markdown.append("\n\n**Overall Result: Tie**")
    
    # Add comparative assessment
    if comparative_assessment:
        markdown.append("\n## Comparative Assessment\n")
        markdown.append(comparative_assessment)
    
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

    evaluations, file_info, comparative_assessment = evaluate_outputs(eval_prompt, original_prompt, args.outputs)
    comparison = generate_comparison(evaluations, file_info, comparative_assessment)
    
    output_path = Path('example-output') / f"comparison-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    with open(output_path, 'w') as f:
        f.write(comparison)
    
    print(f"Comparison saved to {output_path}")

if __name__ == '__main__':
    main()
