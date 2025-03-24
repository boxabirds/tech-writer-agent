"""
Shared State for the Tech Writer multi-agent system.

This module provides a shared state mechanism for communication
between the Researcher, Writer, and Coordinator agents.
"""

from typing import Dict, List, Any, Optional, TypedDict
import os
import json
from datetime import datetime

class SharedState(TypedDict):
    """Shared state between agents."""
    codebase_path: str
    model_name: str
    research_findings: Dict[str, Any]
    diagrams: Dict[str, str]
    final_document: Optional[str]
    status: str
    output_path: str
    errors: List[str]

def initialize_shared_state(codebase_path: str, model_name: str) -> SharedState:
    """Initialize the shared state."""
    # Create a timestamped output directory
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    output_dir = f"analysis_results/{timestamp}-{model_name}"
    os.makedirs(output_dir, exist_ok=True)
    
    return {
        "codebase_path": codebase_path,
        "model_name": model_name,
        "research_findings": {},
        "diagrams": {},
        "final_document": None,
        "status": "initialized",
        "output_path": output_dir,
        "errors": []
    }

def save_state(state: SharedState, filepath: Optional[str] = None) -> str:
    """Save the shared state to a JSON file."""
    if filepath is None:
        filepath = os.path.join(state["output_path"], "state.json")
    
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            # Convert to a serializable dict
            serializable_state = {k: v for k, v in state.items()}
            json.dump(serializable_state, f, indent=2)
        return f"State saved to {filepath}"
    except Exception as e:
        return f"Error saving state: {str(e)}"

def load_state(filepath: str) -> SharedState:
    """Load the shared state from a JSON file."""
    try:
        with open(filepath, "r") as f:
            state = json.load(f)
        return state
    except Exception as e:
        raise ValueError(f"Error loading state: {str(e)}")

def update_state(state: SharedState, updates: Dict[str, Any]) -> SharedState:
    """Update the shared state with new values."""
    for key, value in updates.items():
        if key in state:
            state[key] = value
    return state
