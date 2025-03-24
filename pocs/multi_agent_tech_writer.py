#!/usr/bin/env python3
"""
Multi-Agent Tech Writer System

This script implements a multi-agent system for analyzing codebases and generating
comprehensive documentation. It separates responsibilities between a Researcher agent
that explores the codebase and a Writer agent that creates the documentation, with
a Coordinator agent orchestrating the workflow.
"""

import os
import argparse
import time
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, TypedDict, Union, Callable
import json

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from agents.coordinator import CoordinatorAgent, CoordinatorState
from agents.researcher import ResearcherAgent, ResearchState
from agents.writer import WriterAgent, WriterState

def create_prompts_if_needed():
    """Create default prompts if they don't exist."""
    os.makedirs("prompts", exist_ok=True)
    
    # Create researcher prompt
    researcher_prompt_path = "prompts/researcher_prompt.txt"
    if not os.path.exists(researcher_prompt_path):
        with open(researcher_prompt_path, "w") as f:
            f.write("""You are the Researcher agent in a multi-agent system for analyzing codebases.
Your job is to explore and analyze the codebase, collecting evidence and organizing findings.

INSTRUCTIONS:
1. Explore the directory structure to understand the overall organization
2. Identify key files and components in the codebase
3. Analyze code patterns, architecture, and technologies used
4. Collect concrete evidence with file paths and code snippets
5. Create diagrams based on the code structure
6. Organize your findings in a structured format

Focus on gathering factual information from the code, not making speculations.
Only include information that you can verify with concrete evidence.
""")
    
    # Create writer prompt
    writer_prompt_path = "prompts/writer_prompt.txt"
    if not os.path.exists(writer_prompt_path):
        with open(writer_prompt_path, "w") as f:
            f.write("""You are the Writer agent in a multi-agent system for analyzing codebases.
Your job is to transform research findings into coherent documentation with a consistent narrative.

INSTRUCTIONS:
1. Use the research findings to create comprehensive documentation
2. Organize the content into clear sections with appropriate headings
3. Include diagrams where relevant
4. Use concrete examples and code snippets from the research
5. Maintain a consistent tone and terminology
6. Focus on clarity and readability

Only include information that is backed by concrete evidence from the research.
Do not include speculation or placeholder content.
If information about a topic is not available, omit that section entirely.
""")
    
    # Create coordinator prompt
    coordinator_prompt_path = "prompts/coordinator_prompt.txt"
    if not os.path.exists(coordinator_prompt_path):
        with open(coordinator_prompt_path, "w") as f:
            f.write("""You are the Coordinator agent in a multi-agent system for analyzing codebases.
Your job is to orchestrate the workflow between the Researcher and Writer agents.

INSTRUCTIONS:
1. Initialize the research process
2. Monitor the progress of the Researcher agent
3. Evaluate when research is complete enough to proceed to writing
4. Initialize the writing process with the research findings
5. Monitor the progress of the Writer agent
6. Finalize and save the completed documentation

Ensure that the research is thorough before proceeding to writing.
Verify that all necessary components are analyzed and documented.
""")

def create_workflow(model_name: str = "gpt-4o") -> Callable:
    """Create the workflow for the multi-agent system."""
    # Create the agents
    coordinator = CoordinatorAgent(model_name=model_name)
    
    # Create the graph
    workflow = StateGraph(CoordinatorState)
    
    # Add the coordinator node
    workflow.add_node("coordinator", lambda state: coordinator.run(state))
    
    # Add conditional edges
    def router(state: CoordinatorState) -> str:
        """Route to the next state based on the current status."""
        if state["status"] == "complete":
            return END
        else:
            return "coordinator"
    
    workflow.add_conditional_edges("coordinator", router)
    
    # Compile the graph
    app = workflow.compile()
    
    return app

def main():
    """Main entry point for the multi-agent tech writer system."""
    parser = argparse.ArgumentParser(description="Analyze a codebase using a multi-agent system")
    parser.add_argument("--directory", required=True, help="Path to the codebase directory")
    parser.add_argument("--model", default="gpt-4o", help="Model to use for analysis")
    parser.add_argument("--prompt-file", default="prompts/prompt-checkpoint-v2.txt", help="Path to the file containing the analysis prompt")
    args = parser.parse_args()
    
    # Create default prompts if needed
    create_prompts_if_needed()
    
    # If a prompt file is provided, use it to override the writer prompt
    if args.prompt_file and os.path.exists(args.prompt_file):
        with open(args.prompt_file, "r") as f:
            prompt_content = f.read()
        
        with open("prompts/writer_prompt.txt", "w") as f:
            f.write(prompt_content)
    
    # Create the workflow
    app = create_workflow(model_name=args.model)
    
    # Create the output directory
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    output_dir = f"analysis_results/{timestamp}-{args.model}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize the coordinator state
    coordinator = CoordinatorAgent(model_name=args.model)
    initial_state = coordinator.initialize_state(args.directory, args.model)
    
    # Run the workflow
    print(f"Starting analysis of {args.directory} with model {args.model}")
    print(f"Results will be saved to {output_dir}")
    
    # Run the workflow with progress updates
    state = initial_state
    while state["status"] != "complete":
        print(f"Current status: {state['status']}")
        state = app.invoke(state)
        time.sleep(1)  # Small delay to avoid overwhelming the console
    
    print(f"Analysis complete. Results saved to {output_dir}")
    
    # Copy the final document to the output directory for easier access
    if state["final_document"]:
        output_path = os.path.join("analysis_results", f"{timestamp}-{args.model}.md")
        with open(output_path, "w") as f:
            f.write(state["final_document"])
        print(f"Final document saved to {output_path}")

if __name__ == "__main__":
    main()
