"""
Writer Agent for the Tech Writer system.

This agent is responsible for transforming research findings into
coherent documentation with a consistent narrative.
"""

from typing import Dict, List, Any, Tuple, Optional, TypedDict
import os
from datetime import datetime
import json

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

class WriterState(TypedDict):
    """State for the Writer agent."""
    findings: Dict[str, Any]
    diagrams: Dict[str, str]
    document: Optional[str]
    status: str
    error: Optional[str]

class WriterAgent:
    """Agent responsible for creating documentation from research findings."""
    
    def __init__(self, model_name: str = "gpt-4o"):
        """Initialize the writer agent with the specified model."""
        self.model = ChatOpenAI(model=model_name)
        self.prompt_path = "prompts/writer_prompt.txt"
        
    def run(self, state: WriterState) -> WriterState:
        """Run the writer agent on the current state."""
        try:
            if state["status"] == "in_progress" and not state["document"]:
                # Start writing the document
                print("✍️ Starting to write documentation...")
                
                # Load the writer prompt
                with open(self.prompt_path, "r") as f:
                    prompt_template = f.read()
                
                # Prepare the findings for the prompt
                findings_str = json.dumps(state["findings"], indent=2)
                diagrams_str = json.dumps(state["diagrams"], indent=2)
                
                # Create the prompt
                prompt = ChatPromptTemplate.from_messages([
                    ("system", prompt_template),
                    ("human", f"Here are the research findings:\n\n{findings_str}\n\nHere are the diagrams:\n\n{diagrams_str}\n\nPlease write a comprehensive documentation based on these findings.")
                ])
                
                # Generate the document
                response = self.model.invoke(prompt)
                document = response.content
                
                # Update the state
                state["document"] = document
                state["status"] = "complete"
                
                print("✅ Documentation written successfully!")
                return state
                
            elif state["status"] == "in_progress" and state["document"]:
                # Document is already written, mark as complete
                state["status"] = "complete"
                return state
                
            elif state["status"] == "complete":
                # Already complete
                return state
                
            else:
                # Unknown status
                raise ValueError(f"Unknown status: {state['status']}")
                
        except Exception as e:
            print(f"❌ Error in writer: {str(e)}")
            state["error"] = str(e)
            state["status"] = "error"
            return state
