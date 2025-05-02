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
    
    # Process all files first to extract content and metadata
    processed_files = []
    for i, file_path in enumerate(output_files):
        content = load_file_content(file_path)
        if not content:
            continue
        
        # Generate a readable agent name
        filename = os.path.basename(file_path)
        readable_name = generate_readable_agent_name(filename)
        
        # Extract model and agent info
        model_name, agent_type = extract_metadata(file_path)
        
        # Store info for this file
        file_info.append({
            'file': file_path,
            'model': model_name,
            'agent': agent_type,
            'readable_name': readable_name,
            'index': i
        })
        
        # Store output for comparative assessment
        outputs_for_comparison.append({
            'file': file_path,
            'model': model_name,
            'agent': agent_type,
            'readable_name': readable_name,
            'content': content,
            'index': i
        })
        
        processed_files.append({
            'file': file_path,
            'model': model_name,
            'agent': agent_type,
            'readable_name': readable_name,
            'content': content,
            'index': i
        })
    
    # Modified LLM-as-judge prompt to handle multiple agents
    multi_agent_prompt = modify_judge_prompt_for_multiple_agents(eval_prompt, processed_files, original_prompt)
    
    try:
        response = model.generate_content(multi_agent_prompt)
        evaluations = [{
            'evaluation': response.text,
            'files': [file['file'] for file in processed_files],
            'indices': [file['index'] for file in processed_files]
        }]
    except Exception as e:
        print(f"Error evaluating agents: {e}")
    
    # Generate the comparative assessment
    comparative_assessment = None
    if len(outputs_for_comparison) > 1:
        comparative_assessment = generate_comparative_assessment(original_prompt, outputs_for_comparison)
    
    return evaluations, file_info, comparative_assessment, original_prompt

def modify_judge_prompt_for_multiple_agents(eval_prompt, processed_files, original_prompt):
    """Modify the LLM-as-judge prompt to handle any number of agents."""
    # Start with the base prompt structure but modify for multiple agents
    prompt = """You are an impartial judge tasked with evaluating the relative performance of multiple agent outputs for a specific task. Your goal is to compare the outputs based on predefined criteria and determine which is best, or if they are equal, while providing a clear rationale for your decision.

Task Description:
{original_prompt}

Input Provided to Agents:
The architecture analysis prompt

"""
    
    # Add each agent's output to the prompt
    for i, file in enumerate(processed_files):
        agent_label = file['readable_name']
        prompt += f"Agent {i+1} ({agent_label}) Output:\n{file['content']}\n\n"
    
    # Add the evaluation criteria
    prompt += """
Evaluation Criteria:
Evaluate each output based on the following criteria, weighted equally:
Accuracy: How correct and factually accurate is the output relative to the task requirements and input?
Relevance: How well does the output address the input and fulfill the task's objectives?
Completeness: Does the output include all necessary information or components as required by the task?
Clarity: How clear, concise, and well-structured is the output?

Scoring Instructions:
For each agent, score each criterion on a scale of 1-5, where:
1: Poor - Significantly deficient or inappropriate
2: Fair - Below average quality or partially addresses requirements
3: Good - Average quality, meets basic requirements
4: Very Good - Above average quality, exceeds some requirements
5: Excellent - Exceptional quality, fully meets or exceeds all requirements

After scoring, calculate a total score for each agent and determine the winner.

Output Format:
Provide your evaluation as a JSON object with the following structure:
```json
{
  "evaluation": {
    "agents": [
      {
        "name": "[Agent 1 Name]",
        "scores": {
          "accuracy": 5,
          "relevance": 5,
          "completeness": 5,
          "clarity": 5,
          "total_score": 20
        }
      },
      {
        "name": "[Agent 2 Name]",
        "scores": {
          "accuracy": 4,
          "relevance": 4,
          "completeness": 4,
          "clarity": 4,
          "total_score": 16
        }
      }
      // Add entries for all agents
    ],
    "winner": "[Name of winning agent or 'Tie' if equal]",
    "rationale": "[Detailed explanation of your evaluation and decision]"
  }
}
```

Remember to be fair, thorough, and specific in your evaluation, providing clear justifications for your scores and final decision. Your goal is to determine which agent produced the better output for this task, or if they were equally good.
"""
    
    # Replace placeholder with actual prompt
    prompt = prompt.replace("{original_prompt}", original_prompt)
    
    return prompt

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
    
    # Build mapping from indices to readable names
    index_to_name = {}
    for info in file_info:
        index = info.get('index', -1)
        readable_name = info.get('readable_name', f"Agent {len(index_to_name)}")
        index_to_name[index] = readable_name
    
    for eval_item in evaluations:
        try:
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
                        'files': eval_item.get('files', []),
                        'indices': eval_item.get('indices', [])
                    }
                    
                    # Extract agent scores from the agents array
                    if 'agents' in eval_data:
                        result['agent_scores'] = {}
                        
                        for agent_data in eval_data['agents']:
                            agent_name = agent_data.get('name', '')
                            # Find the agent index based on name
                            agent_index = -1
                            for idx, name in index_to_name.items():
                                if name in agent_name or f"Agent {idx+1}" in agent_name:
                                    agent_index = idx
                                    break
                            
                            if agent_index >= 0 and 'scores' in agent_data:
                                result['agent_scores'][agent_index] = agent_data['scores']
                    
                    # Extract winner
                    if 'winner' in eval_data:
                        winner = eval_data['winner']
                        winner_index = -1
                        
                        # Try to map the winner string to an agent index
                        if winner != 'Tie':
                            for idx, name in index_to_name.items():
                                if name in winner:
                                    winner_index = idx
                                    break
                            
                            # If couldn't map by name, check for Agent 1, Agent 2, etc.
                            if winner_index < 0:
                                for idx in range(len(file_info)):
                                    if f"Agent {idx+1}" in winner:
                                        winner_index = idx
                                        break
                        
                        result['winner'] = winner_index if winner_index >= 0 else 'Tie'
                    
                    # Extract rationale
                    if 'rationale' in eval_data:
                        rationale = eval_data['rationale']
                        
                        # Replace generic agent references with readable names
                        for idx, name in index_to_name.items():
                            rationale = rationale.replace(f"Agent {idx+1}", name)
                        
                        result['rationale'] = rationale
                    
                    evaluation_results.append(result)
                
            except Exception as e:
                print(f"Failed to parse JSON response from judge: {e}")
                
                # Fallback regex approach for extracting scores
                try:
                    # Create a result with extracted info
                    result = {
                        'files': eval_item.get('files', []),
                        'indices': eval_item.get('indices', []),
                        'agent_scores': {}
                    }
                    
                    # Try to extract scores for all agents using regex
                    for idx, name in index_to_name.items():
                        agent_scores = {}
                        
                        # Look for either Agent 1, Agent 2, etc. or the actual agent name
                        agent_patterns = [
                            f"Agent {idx+1}",
                            re.escape(name)
                        ]
                        
                        for agent_pattern in agent_patterns:
                            # Try each criteria
                            for criterion in ['accuracy', 'relevance', 'completeness', 'clarity', 'total_score']:
                                # Look for score pattern
                                pattern = fr'{agent_pattern}.*?{criterion}.*?(\d+)'
                                match = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
                                if match:
                                    agent_scores[criterion] = int(match.group(1))
                        
                        if agent_scores:
                            result['agent_scores'][idx] = agent_scores
                    
                    # Extract winner
                    winner_match = re.search(r'winner.*?[:="\']+([^"\']+)["\']', raw_text, re.IGNORECASE)
                    winner = winner_match.group(1) if winner_match else "Tie"
                    
                    # Try to match winner to an agent
                    winner_index = -1
                    if winner != 'Tie':
                        for idx, name in index_to_name.items():
                            if name in winner:
                                winner_index = idx
                                break
                    
                    result['winner'] = winner_index if winner_index >= 0 else 'Tie'
                    
                    # Extract rationale
                    rationale_match = re.search(r'rationale.*?[:="\']+([^"\']+)["\']', raw_text, re.IGNORECASE)
                    rationale = rationale_match.group(1) if rationale_match else "No rationale provided"
                    
                    # Replace agent references in rationale
                    for idx, name in index_to_name.items():
                        rationale = rationale.replace(f"Agent {idx+1}", name)
                    
                    result['rationale'] = rationale
                    
                    evaluation_results.append(result)
                
                except Exception as e:
                    print(f"Failed to extract scores with regex: {e}")
                    
                    # Add raw text as last resort
                    raw_text_clean = raw_text
                    for idx, name in index_to_name.items():
                        raw_text_clean = raw_text_clean.replace(f"Agent {idx+1}", name)
                    
                    evaluation_results.append({
                        'files': eval_item.get('files', []),
                        'indices': eval_item.get('indices', []),
                        'raw_text': raw_text_clean
                    })
                    
        except Exception as e:
            print(f"Error parsing evaluation: {e}")
    
    # Generate the markdown report
    title = ' vs '.join([info.get('readable_name', f"Agent {i}") for i, info in enumerate(file_info)])
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    
    markdown = [
        f"# Architecture Analysis Comparison: {title}",
        "",
        "## Evaluation Summary",
        f"- **Date**: {datetime.datetime.now().strftime('%Y-%m-%d')}",
        f"- **Models Compared**: {title}",
        f"- **Prompt Used**: [architecture.prompt.txt](../prompts/architecture.prompt.txt)",
        f"- **Evaluation Criteria**: [llm-as-judge.txt](../prompts/llm-as-judge.txt)",
        "",
        "## Judge Scores",
        ""
    ]
    
    # Create table header with proper pipe formatting
    header = "| Criteria |"
    for info in file_info:
        readable_name = info.get('readable_name', "Unknown")
        header += f" {readable_name} |"
    markdown.append(header)
    
    # Create separator row with proper number of columns
    separator = "|:--------|"
    for _ in file_info:
        separator += ":--------|"
    markdown.append(separator)
        
    # Add scores for each criterion
    for criterion in ['accuracy', 'relevance', 'completeness', 'clarity', 'total_score']:
        row = f"| **{criterion.title()}** |"
        
        # Get scores from all evaluations for each agent
        for info in file_info:
            index = info.get('index', -1)
            score = "N/A"
            
            for result in evaluation_results:
                if 'agent_scores' in result and index in result['agent_scores'] and criterion in result['agent_scores'][index]:
                    score = result['agent_scores'][index][criterion]
                    break
            
            row += f" {score} |"
        
        markdown.append(row)
    
    # Add winner row
    winner_row = "| **Winner** |"
    
    # Map winners to readable names
    has_winner = False
    for info in file_info:
        index = info.get('index', -1)
        is_winner = False
        
        for result in evaluation_results:
            if 'winner' in result:
                if result['winner'] == index:
                    winner_row += f" {info.get('readable_name', 'Winner')} |"
                    is_winner = True
                    has_winner = True
                    break
                elif result['winner'] == 'Tie' and not has_winner:
                    winner_row += " Tie |"
                    is_winner = True
                    break
        
        if not is_winner:
            winner_row += " N/A |"
    
    markdown.append(winner_row)
    
    # Add judge's rationale
    markdown.append("")
    markdown.append("## Qualitative Assessment")
    markdown.append("")
    
    for result in evaluation_results:
        if 'rationale' in result:
            markdown.append(result['rationale'])
            break
        elif 'raw_text' in result:
            markdown.append(result['raw_text'])
            break
    
    # Add the winner declaration
    for result in evaluation_results:
        if 'winner' in result:
            winner = result.get('winner', 'Tie')
            if winner != 'Tie':
                markdown.append(f"\n\n**Overall Winner: {index_to_name.get(winner, 'Unknown')}**")
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
