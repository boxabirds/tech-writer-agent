"""
Coordinator Agent for the Tech Writer system.

This agent is responsible for orchestrating the workflow between
the Researcher and Writer agents, managing the overall process.
"""

import os
import json
import datetime
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, TypedDict, Union
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

from agents.researcher import ResearchState
from agents.writer import WriterState

class CoordinatorState(TypedDict):
    """State for the Coordinator agent."""
    codebase_path: str
    model_name: str
    research_complete: bool
    writing_complete: bool
    research_state: Optional[ResearchState]
    writer_state: Optional[WriterState]
    output_path: str
    final_document: Optional[str]
    status: str
    errors: List[str]
    researcher: Optional[Any]
    writer: Optional[Any]
    write_state: Optional[Dict[str, Any]]
    document: Optional[str]
    output_file: Optional[str]
    error: Optional[str]

class CoordinatorAgent:
    """Agent responsible for orchestrating the workflow between agents."""
    
    def __init__(self, model_name: str = "gpt-4o"):
        """Initialize the coordinator agent with the specified model."""
        self.model = ChatOpenAI(model=model_name)
        self.prompt_path = "prompts/coordinator_prompt.txt"
        self.prompt = self._load_prompt()
        
    def _load_prompt(self) -> str:
        """Load the coordinator prompt from file."""
        with open(self.prompt_path, "r") as f:
            return f.read()
    
    def initialize_state(self, codebase_path: str, model_name: str) -> CoordinatorState:
        """Initialize the coordinator state."""
        # Create a timestamped output directory
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        output_dir = f"analysis_results/{timestamp}-{model_name}"
        os.makedirs(output_dir, exist_ok=True)
        
        return {
            "codebase_path": codebase_path,
            "model_name": model_name,
            "research_complete": False,
            "writing_complete": False,
            "research_state": None,
            "writer_state": None,
            "output_path": output_dir,
            "final_document": None,
            "status": "initializing",
            "errors": [],
            "researcher": None,
            "writer": None,
            "write_state": None,
            "document": None,
            "output_file": None,
            "error": None
        }
    
    @tool
    def save_document(self, document: str, output_path: str, model_name: str) -> str:
        """Save the final document to a file."""
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}-{model_name}.md"
        filepath = os.path.join(output_path, filename)
        
        try:
            os.makedirs(output_path, exist_ok=True)
            with open(filepath, "w") as f:
                f.write(document)
            return f"Document saved to {filepath}"
        except Exception as e:
            return f"Error saving document: {str(e)}"
    
    @tool
    def save_research_findings(self, findings: Dict[str, Any], output_path: str) -> str:
        """Save the research findings to a JSON file."""
        filepath = os.path.join(output_path, "research_findings.json")
        
        try:
            with open(filepath, "w") as f:
                json.dump(findings, f, indent=2)
            return f"Research findings saved to {filepath}"
        except Exception as e:
            return f"Error saving research findings: {str(e)}"
    
    @tool
    def evaluate_research_completeness(self, research_state: ResearchState) -> Dict[str, Any]:
        """Evaluate if the research is complete enough to proceed to writing."""
        # This is a simplified evaluation - in a real implementation,
        # we would have more sophisticated criteria
        
        findings = research_state["findings"]
        explored_files = research_state["explored_files"]
        
        # Check if we have explored at least some files
        if len(explored_files) < 5:
            return {
                "complete": False,
                "reason": "Not enough files explored",
                "missing": "Need to explore more files"
            }
        
        # Check if we have identified components
        if not findings.get("components"):
            return {
                "complete": False,
                "reason": "No components identified",
                "missing": "Need to identify key components"
            }
        
        # Check if we have created diagrams
        if not research_state.get("diagrams"):
            return {
                "complete": False,
                "reason": "No diagrams created",
                "missing": "Need to create architectural diagrams"
            }
        
        return {
            "complete": True,
            "reason": "Research appears to be complete",
            "missing": None
        }
    
    def create_researcher(self, model: str):
        from agents.researcher import ResearcherAgent
        return ResearcherAgent(model_name=model)
    
    def create_writer(self, model: str):
        from agents.writer import WriterAgent
        return WriterAgent(model_name=model)
    
    def run(self, state: CoordinatorState) -> CoordinatorState:
        """Run the coordinator agent on the current state."""
        try:
            if state["status"] == "initializing":
                # Initialize the research process
                print(" Initializing research process...")
                state["researcher"] = self.create_researcher(state["model_name"])
                state["research_state"] = {
                    "codebase_path": state["codebase_path"],
                    "files_analyzed": 0,
                    "total_files": 0,
                    "findings": {},
                    "diagrams": {},
                    "status": "in_progress"
                }
                state["status"] = "researching"
                return state
                
            elif state["status"] == "researching":
                # Run the researcher agent
                print(f" Researching... (analyzed {state['research_state']['files_analyzed']} files so far)")
                state["research_state"] = state["researcher"].run(state["research_state"])
                
                # Check if research is complete
                if state["research_state"]["status"] == "complete":
                    print(" Research complete!")
                    state["status"] = "writing"
                    state["writer"] = self.create_writer(state["model_name"])
                    state["write_state"] = {
                        "findings": state["research_state"]["findings"],
                        "diagrams": state["research_state"]["diagrams"],
                        "document": "",
                        "status": "in_progress"
                    }
                return state
                
            elif state["status"] == "writing":
                # Run the writer agent
                print(" Writing documentation...")
                state["write_state"] = state["writer"].run(state["write_state"])
                
                # Check if writing is complete
                if state["write_state"]["status"] == "complete":
                    print(" Documentation complete!")
                    state["status"] = "finalizing"
                    state["document"] = state["write_state"]["document"]
                return state
                
            elif state["status"] == "finalizing":
                # Save the final document
                print(" Saving final document...")
                
                # Create output directory if it doesn't exist
                os.makedirs(state["output_path"], exist_ok=True)
                
                # Generate timestamp for filename
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                filename = f"{timestamp}-{state['model_name']}.md"
                
                # Save the document
                with open(os.path.join(state["output_path"], filename), "w") as f:
                    f.write(state["document"])
                    
                print(f" Document saved to {os.path.join(state['output_path'], filename)}")
                state["status"] = "complete"
                state["output_file"] = os.path.join(state["output_path"], filename)
                return state
                
            else:
                # Unknown status
                raise ValueError(f"Unknown status: {state['status']}")
                
        except Exception as e:
            print(f" Error in coordinator: {str(e)}")
            state["error"] = str(e)
            state["status"] = "error"
            return state
