#!/usr/bin/env python3
import argparse
import json
import os
import re
import datetime
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

def extract_metadata(filename):
    """Extract model and agent type from filename."""
    parts = Path(filename).stem.split('-')
    model = parts[-2] if len(parts) > 2 else 'unknown'
    agent = parts[-1] if len(parts) > 1 else 'unknown'
    return model, agent

def evaluate_outputs(eval_prompt, original_prompt, output_files):
    """Evaluate multiple output files against the original prompt."""
    configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = GenerativeModel('gemini-2.0-flash')
    
    evaluations = []
    file_info = []
    outputs_for_comparison = []
    
    for file_path in output_files:
        content = load_file_content(file_path)
        if not content:
            continue
        
        # Extract model and agent
        model_name, agent_type = extract_metadata(file_path)
        
        # Store basic file info
        file_info.append({
            'file': file_path,
            'model': model_name,
            'agent': agent_type
        })
        
        # Store output for comparative assessment
        outputs_for_comparison.append({
            'file': file_path,
            'model': model_name,
            'agent': agent_type,
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
        outputs: List of dicts with 'file', 'model', 'agent', and 'content' keys
    
    Returns:
        String containing the comparative assessment
    """
    configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = GenerativeModel('gemini-2.0-flash')
    
    # Construct a prompt for the comparative assessment
    comparison_prompt = f"""Given the input prompt and the results produced by different agent configurations, perform an in-depth qualitative assessment of the relative merits of each.

FORMAT YOUR RESPONSE IN MARKDOWN with proper headings and subheadings.

For each agent output:
1. Create a section with the agent's name
2. Break down your assessment by the major architecture components (similar to the prompt sections)
3. Highlight specific strengths and weaknesses
4. Compare directly with other agent outputs where relevant

End with a summary section that ranks the outputs and explains the reasoning behind the ranking.

Original Prompt:
{original_prompt}

"""
    
    # Add each agent's output to the prompt with clear separation
    for i, output in enumerate(outputs):
        agent_label = f"{output['model']} ({output['agent']})"
        comparison_prompt += f"\n\n{'='*80}\nAGENT OUTPUT #{i+1}: {agent_label}\n{'='*80}\n\n{output['content']}\n\n"
    
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
                    evaluation_results.append({
                        'file': file_path,
                        'model': model,
                        'agent': agent,
                        'raw_text': raw_text
                    })
        except Exception as e:
            print(f"Error processing evaluation: {e}")
    
    # Get agent types
    agents_info = []
    for info in file_info:
        agents_info.append(f"{info['agent']}")
    
    # Generate markdown output
    markdown = [
        f"# Architecture Analysis Comparison: {' vs '.join(agents_info)}",
        "\n## Evaluation Summary",
        f"- **Date**: {datetime.datetime.now().strftime('%Y-%m-%d')}",
        f"- **Models Compared**: {' vs '.join([f'{info['model']} ({info['agent']})' for info in file_info])}",
        "- **Prompt Used**: [architecture.prompt.txt](../prompts/architecture.prompt.txt)",
        "- **Evaluation Criteria**: [llm-as-judge.txt](../prompts/llm-as-judge.txt)",
        "\n## Judge Scores\n"
    ]
    
    # Create score table
    if evaluation_results:
        # Set up table headers
        markdown.append("| Criteria | Agent A | Agent B |")
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
            winner = result.get('winner', 'Unknown')
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
