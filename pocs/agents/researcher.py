"""
Researcher Agent for the Tech Writer system.

This agent is responsible for exploring and analyzing the codebase,
collecting evidence, and organizing findings.
"""

from typing import Dict, List, Any, Tuple, Optional, TypedDict, Callable
import os
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from binaryornot.check import is_binary

def is_text_file(file_path: str) -> bool:
    """Check if a file is a text file, handling special cases like TypeScript files."""
    # Check extension first - these are definitely text files
    ext = os.path.splitext(file_path)[1].lower()
    text_extensions = [
        '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.json', '.md', 
        '.yml', '.yaml', '.toml', '.txt', '.csv', '.sql', '.sh', '.bat', '.ps1',
        '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rb', '.php', '.swift'
    ]
    
    if ext in text_extensions:
        return True
    
    # Use binaryornot as a fallback
    return not is_binary(file_path)

class ResearchState(TypedDict):
    """State for the Researcher agent."""
    codebase_path: str
    current_file: Optional[str]
    explored_files: List[str]
    findings: Dict[str, Any]
    task_queue: List[str]
    current_task: Optional[str]
    diagrams: Dict[str, str]
    status: str
    total_files: int
    files_analyzed: int
    error: Optional[str]

class ResearcherAgent:
    """Agent responsible for exploring and analyzing the codebase."""
    
    def __init__(self, model_name: str = "gpt-4o"):
        """Initialize the researcher agent with the specified model."""
        self.model = ChatOpenAI(model=model_name)
        self.prompt_path = "prompts/researcher_prompt.txt"
        self.prompt = self._load_prompt()
        
    def _load_prompt(self) -> str:
        """Load the researcher prompt from file."""
        with open(self.prompt_path, "r") as f:
            return f.read()
    
    def initialize_state(self, codebase_path: str) -> ResearchState:
        """Initialize the researcher state."""
        return {
            "codebase_path": codebase_path,
            "current_file": None,
            "explored_files": [],
            "findings": {},
            "task_queue": ["explore_directory_structure"],
            "current_task": None,
            "diagrams": {},
            "status": "in_progress",
            "total_files": 0,
            "files_analyzed": 0,
            "error": None
        }
    
    @tool
    def list_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        """List contents of a directory with metadata."""
        results = []
        try:
            for item in os.listdir(directory_path):
                item_path = os.path.join(directory_path, item)
                is_dir = os.path.isdir(item_path)
                
                if is_dir:
                    size = None
                    type_str = "directory"
                else:
                    size = os.path.getsize(item_path)
                    type_str = "file"
                    
                results.append({
                    "name": item,
                    "path": item_path,
                    "type": type_str,
                    "size": size,
                    "is_binary": not is_dir and not is_text_file(item_path)
                })
            return results
        except Exception as e:
            return [{"error": str(e)}]
    
    @tool
    def read_file(self, file_path: str) -> str:
        """Read the contents of a file if it's not binary."""
        try:
            if not is_text_file(file_path):
                return f"[Binary file: {file_path}]"
            
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"
    
    @tool
    def analyze_file_type(self, file_path: str) -> Dict[str, Any]:
        """Analyze a file to determine its type and role in the codebase."""
        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)
        
        file_type_info = {
            ".py": "Python source code",
            ".js": "JavaScript source code",
            ".jsx": "React JavaScript component",
            ".ts": "TypeScript source code",
            ".tsx": "React TypeScript component",
            ".html": "HTML document",
            ".css": "CSS stylesheet",
            ".json": "JSON data file",
            ".md": "Markdown documentation",
            ".sql": "SQL database script",
            ".yml": "YAML configuration file",
            ".yaml": "YAML configuration file",
            ".toml": "TOML configuration file",
            ".ini": "INI configuration file",
            ".env": "Environment variables file",
            ".gitignore": "Git ignore rules",
            ".dockerignore": "Docker ignore rules",
            "dockerfile": "Docker build instructions",
            "package.json": "Node.js package configuration",
            "requirements.txt": "Python package requirements",
            "setup.py": "Python package setup script"
        }
        
        if filename.lower() in file_type_info:
            file_type = file_type_info[filename.lower()]
        elif ext in file_type_info:
            file_type = file_type_info[ext]
        else:
            file_type = "Unknown file type"
            
        return {
            "path": file_path,
            "type": file_type,
            "extension": ext,
            "is_binary": not is_text_file(file_path)
        }
    
    def get_language_for_extension(self, ext: str) -> Optional[str]:
        """Get the programming language for a file extension."""
        language_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".jsx": "JavaScript (React)",
            ".ts": "TypeScript",
            ".tsx": "TypeScript (React)",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "SCSS",
            ".sass": "Sass",
            ".less": "Less",
            ".json": "JSON",
            ".md": "Markdown",
            ".sql": "SQL",
            ".java": "Java",
            ".c": "C",
            ".cpp": "C++",
            ".h": "C/C++ Header",
            ".cs": "C#",
            ".go": "Go",
            ".rb": "Ruby",
            ".php": "PHP",
            ".swift": "Swift",
            ".kt": "Kotlin",
            ".rs": "Rust",
            ".sh": "Shell",
            ".bat": "Batch",
            ".ps1": "PowerShell"
        }
        return language_map.get(ext)

    def is_key_file(self, file_path: str) -> bool:
        """Determine if a file is a key file in the codebase."""
        key_patterns = [
            "main", "index", "app", "server", "config", "settings",
            "requirements", "package.json", "setup", "build", "docker",
            "dockerfile", "makefile", "readme", "license"
        ]
        
        filename = os.path.basename(file_path).lower()
        return any(pattern in filename for pattern in key_patterns)

    def determine_file_purpose(self, file_path: str, content: str) -> str:
        """Determine the purpose of a file based on its content and name."""
        filename = os.path.basename(file_path).lower()
        
        if "readme" in filename:
            return "Documentation"
        elif "test" in filename:
            return "Testing"
        elif "config" in filename or "settings" in filename:
            return "Configuration"
        elif "main" in filename or "index" in filename:
            return "Entry point"
        elif "utils" in filename or "helpers" in filename:
            return "Utility functions"
        elif "model" in filename:
            return "Data model"
        elif "view" in filename:
            return "View component"
        elif "controller" in filename:
            return "Controller"
        elif "api" in filename:
            return "API endpoint"
        elif "middleware" in filename:
            return "Middleware"
        elif "component" in filename:
            return "UI Component"
        elif "service" in filename:
            return "Service"
        else:
            return "Support file"

    def identify_component(self, file_path: str, content: str) -> Optional[str]:
        """Identify which component a file belongs to."""
        # Extract directory structure
        parts = os.path.normpath(file_path).split(os.sep)
        
        # Check for common component directories
        component_dirs = ["components", "services", "models", "views", "controllers", "api", "utils", "helpers", "lib", "core"]
        
        for i, part in enumerate(parts):
            if part.lower() in component_dirs and i + 1 < len(parts):
                return parts[i + 1]
        
        # If no component directory found, use the parent directory
        if len(parts) > 1:
            return parts[-2]
        
        return None

    def determine_component_purpose(self, component: str, file_path: str, content: str) -> str:
        """Determine the purpose of a component based on its name and files."""
        component_lower = component.lower()
        
        if "api" in component_lower:
            return "API interface"
        elif "model" in component_lower or "data" in component_lower:
            return "Data model"
        elif "view" in component_lower or "ui" in component_lower or "component" in component_lower:
            return "User interface"
        elif "controller" in component_lower:
            return "Business logic"
        elif "service" in component_lower:
            return "Service layer"
        elif "util" in component_lower or "helper" in component_lower:
            return "Utility functions"
        elif "test" in component_lower:
            return "Testing"
        elif "config" in component_lower or "setting" in component_lower:
            return "Configuration"
        elif "middleware" in component_lower:
            return "Middleware"
        elif "auth" in component_lower:
            return "Authentication/Authorization"
        else:
            return "Core functionality"

    def detect_frameworks_in_file(self, file_path: str, content: str) -> List[str]:
        """Detect frameworks and libraries used in a file."""
        frameworks = []
        
        # Check for Python frameworks
        if file_path.endswith(".py"):
            if "import flask" in content.lower() or "from flask" in content.lower():
                frameworks.append("Flask")
            if "import django" in content.lower() or "from django" in content.lower():
                frameworks.append("Django")
            if "import fastapi" in content.lower() or "from fastapi" in content.lower():
                frameworks.append("FastAPI")
            if "import langchain" in content.lower() or "from langchain" in content.lower():
                frameworks.append("LangChain")
            if "import openai" in content.lower() or "from openai" in content.lower():
                frameworks.append("OpenAI")
        
        # Check for JavaScript/TypeScript frameworks
        elif file_path.endswith((".js", ".jsx", ".ts", ".tsx")):
            if "import React" in content or "from 'react'" in content or "from \"react\"" in content:
                frameworks.append("React")
            if "import { Component } from '@angular/core'" in content:
                frameworks.append("Angular")
            if "import Vue from 'vue'" in content:
                frameworks.append("Vue.js")
            if "import express from 'express'" in content:
                frameworks.append("Express.js")
        
        return frameworks

    def detect_design_patterns(self, file_path: str, content: str) -> List[str]:
        """Detect design patterns used in a file."""
        patterns = []
        
        # Check for singleton pattern
        if "getInstance" in content or "instance = None" in content:
            patterns.append("Singleton")
        
        # Check for factory pattern
        if "factory" in file_path.lower() or "create" in content:
            patterns.append("Factory")
        
        # Check for observer pattern
        if "addEventListener" in content or "on(" in content or "subscribe" in content:
            patterns.append("Observer")
        
        # Check for MVC pattern
        if "model" in file_path.lower() or "view" in file_path.lower() or "controller" in file_path.lower():
            patterns.append("MVC")
        
        return patterns

    def analyze_file(self, file_path: str, file_content: str, findings: Dict[str, Any]) -> None:
        """Analyze a file and update findings."""
        file_type_info = self.analyze_file_type(file_path)
        language = self.get_language_for_extension(file_type_info["extension"])
        purpose = self.determine_file_purpose(file_path, file_content)
        is_key = self.is_key_file(file_path)
        component = self.identify_component(file_path, file_content)
        component_purpose = self.determine_component_purpose(component, file_path, file_content) if component else None
        
        findings["components"].append({
            "name": component,
            "purpose": component_purpose,
            "files": [file_path]
        })
        
        findings["technologies"]["languages"][language] = findings["technologies"]["languages"].get(language, 0) + 1
        
        if is_key:
            findings["file_structure"]["key_files"].append(file_path)
        
        findings["code_patterns"]["file_purposes"][purpose] = findings["code_patterns"]["file_purposes"].get(purpose, 0) + 1
        
        frameworks = self.detect_frameworks_in_file(file_path, file_content)
        for framework in frameworks:
            findings["technologies"]["frameworks"][framework] = findings["technologies"]["frameworks"].get(framework, 0) + 1
        
        patterns = self.detect_design_patterns(file_path, file_content)
        for pattern in patterns:
            findings["code_patterns"]["design_patterns"].append(pattern)
    
    def generate_diagrams(self, findings: Dict[str, Any]) -> Dict[str, str]:
        """Generate diagrams based on research findings."""
        diagrams = {}
        
        # Generate architecture diagram
        components = findings.get("components", [])
        if components:
            architecture_diagram = "```mermaid\ngraph TD\n"
            
            # Add components
            for component in components:
                component_name = component.get("name", "")
                component_purpose = component.get("purpose", "")
                if component_name:
                    safe_name = component_name.replace(" ", "_").replace("-", "_")
                    architecture_diagram += f"    {safe_name}[{component_name}\\n{component_purpose}]\n"
        
            # Add relationships (simplified)
            for i, component in enumerate(components):
                if i + 1 < len(components):
                    source = component.get("name", "").replace(" ", "_").replace("-", "_")
                    target = components[i+1].get("name", "").replace(" ", "_").replace("-", "_")
                    if source and target:
                        architecture_diagram += f"    {source} --> {target}\n"
        
            architecture_diagram += "```"
            diagrams["architecture"] = architecture_diagram
        
        # Generate component hierarchy diagram
        if components:
            hierarchy_diagram = "```mermaid\ngraph TD\n"
            hierarchy_diagram += "    App[Application]\n"
            
            for component in components:
                component_name = component.get("name", "")
                if component_name:
                    safe_name = component_name.replace(" ", "_").replace("-", "_")
                    hierarchy_diagram += f"    App --> {safe_name}\n"
                    
                    # Add key files as children
                    files = component.get("files", [])
                    if files:
                        for i, file_path in enumerate(files[:3]):  # Limit to 3 files per component
                            file_name = os.path.basename(file_path)
                            safe_file = f"{safe_name}_file_{i}".replace(" ", "_").replace("-", "_")
                            hierarchy_diagram += f"    {safe_name} --> {safe_file}[{file_name}]\n"
        
            hierarchy_diagram += "```"
            diagrams["component_hierarchy"] = hierarchy_diagram
        
        # Generate data flow diagram (simplified)
        if components:
            data_flow_diagram = "```mermaid\ngraph LR\n"
            
            # Identify potential data sources and sinks
            data_sources = [c for c in components if c.get("name") and c.get("purpose") and "data" in c.get("purpose", "").lower()]
            api_components = [c for c in components if c.get("name") and c.get("purpose") and "api" in c.get("purpose", "").lower()]
            ui_components = [c for c in components if c.get("name") and c.get("purpose") and "interface" in c.get("purpose", "").lower()]
            
            # If we don't have enough categorized components, use naming patterns
            if not data_sources:
                data_sources = [c for c in components if c.get("name") and ("model" in c.get("name", "").lower() or "data" in c.get("name", "").lower())]
            if not api_components:
                api_components = [c for c in components if c.get("name") and "api" in c.get("name", "").lower()]
            if not ui_components:
                ui_components = [c for c in components if c.get("name") and ("ui" in c.get("name", "").lower() or "view" in c.get("name", "").lower())]
            
            # If we still don't have enough components, create a simplified flow
            if not (data_sources and api_components and ui_components):
                # Create a simplified flow with available components
                available_components = components[:min(5, len(components))]
                for i, component in enumerate(available_components):
                    if i + 1 < len(available_components):
                        source = component.get("name", "").replace(" ", "_").replace("-", "_")
                        target = available_components[i+1].get("name", "").replace(" ", "_").replace("-", "_")
                        if source and target:
                            data_flow_diagram += f"    {source} --> {target}\n"
            else:
                # Add data flow with categorized components
                for source in data_sources:
                    source_name = source.get("name", "").replace(" ", "_").replace("-", "_")
                    if source_name:
                        data_flow_diagram += f"    {source_name}[(Data: {source.get('name', '')})]\n"
                        
                        # Connect to API components
                        for api in api_components:
                            api_name = api.get("name", "").replace(" ", "_").replace("-", "_")
                            if api_name:
                                data_flow_diagram += f"    {source_name} --> {api_name}[API: {api.get('name', '')}]\n"
                                
                                # Connect API to UI
                                for ui in ui_components:
                                    ui_name = ui.get("name", "").replace(" ", "_").replace("-", "_")
                                    if ui_name:
                                        data_flow_diagram += f"    {api_name} --> {ui_name}[UI: {ui.get('name', '')}]\n"
        
        data_flow_diagram += "```"
        diagrams["data_flow"] = data_flow_diagram
    
    # Generate deployment diagram (simplified)
    deployment_diagram = "```mermaid\ngraph TB\n"
    deployment_diagram += "    User[User] --> Frontend[Frontend]\n"
    deployment_diagram += "    Frontend --> Backend[Backend]\n"
    deployment_diagram += "    Backend --> Database[(Database)]\n"
    deployment_diagram += "```"
    diagrams["deployment"] = deployment_diagram
    
    # Generate ERD diagram (simplified)
    # Only generate if we have identified data models
    data_models = [c for c in components if c.get("purpose") == "Data model"]
    if data_models:
        erd_diagram = "```mermaid\nerDiagram\n"
        
        # Add entities
        for model in data_models:
            model_name = model.get("name", "")
            if model_name:
                safe_name = model_name.replace(" ", "_").replace("-", "_")
                erd_diagram += f"    {safe_name} {{\n"
                erd_diagram += f"        string id PK\n"
                erd_diagram += f"        string name\n"
                erd_diagram += f"        datetime created_at\n"
                erd_diagram += f"    }}\n"
        
        # Add relationships (simplified)
        for i, model in enumerate(data_models):
            if i + 1 < len(data_models):
                source = model.get("name", "").replace(" ", "_").replace("-", "_")
                target = data_models[i+1].get("name", "").replace(" ", "_").replace("-", "_")
                if source and target:
                    erd_diagram += f"    {source} ||--o{{ {target} : has\n"
        
        erd_diagram += "```"
        diagrams["erd"] = erd_diagram
    
    return diagrams

    def run(self, state: ResearchState) -> ResearchState:
        """Run the researcher agent on the current state."""
        try:
            if state["status"] == "in_progress" and state["total_files"] == 0:
                # First run, initialize by listing all files
                print("🔍 Initializing research by listing files...")
                
                # List all files in the codebase
                all_files = self.list_directory(state["codebase_path"])
                
                # Count total files
                text_files = [f for f in all_files if not f["is_binary"] and f["type"] == "file"]
                state["total_files"] = len(text_files)
                
                # Initialize findings structure
                state["findings"] = {
                    "components": [],
                    "architecture": {
                        "pattern": "",
                        "layers": [],
                        "communication": []
                    },
                    "technologies": {
                        "languages": {},
                        "frameworks": {},
                        "databases": {},
                        "third_party": []
                    },
                    "code_patterns": {
                        "design_patterns": [],
                        "conventions": [],
                        "error_handling": [],
                        "testing": [],
                        "file_purposes": {}
                    },
                    "file_structure": {
                        "directories": [],
                        "key_files": []
                    }
                }
                
                # Initialize diagrams
                state["diagrams"] = {}
                
                print(f"📊 Found {state['total_files']} text files to analyze")
                return state
                
            elif state["status"] == "in_progress" and state["files_analyzed"] < state["total_files"]:
                # Continue analyzing files
                print(f"🔍 Analyzing files... ({state['files_analyzed']}/{state['total_files']})")
                
                # Get a list of all files
                all_files = self.list_directory(state["codebase_path"])
                text_files = [f for f in all_files if not f["is_binary"] and f["type"] == "file"]
                
                # Analyze files in batches
                batch_size = min(10, state["total_files"] - state["files_analyzed"])
                files_to_analyze = text_files[state["files_analyzed"]:state["files_analyzed"] + batch_size]
                
                # Analyze each file in the batch
                for file_info in files_to_analyze:
                    file_path = file_info["path"]
                    file_content = self.read_file(file_path)
                    
                    # Analyze the file and update findings
                    self.analyze_file(file_path, file_content, state["findings"])
                    
                    # Increment the counter
                    state["files_analyzed"] += 1
                
                # Check if we've analyzed enough files to generate diagrams
                if state["files_analyzed"] >= state["total_files"] * 0.5 and not state["diagrams"]:
                    # Generate diagrams based on findings
                    state["diagrams"] = self.generate_diagrams(state["findings"])
                
                # Check if we've analyzed enough files to complete the research
                if state["files_analyzed"] >= state["total_files"]:
                    state["status"] = "complete"
                    print("✅ Research complete!")
                
                return state
                
            elif state["status"] == "complete":
                # Research is already complete
                return state
                
            else:
                # Unknown status
                raise ValueError(f"Unknown status: {state['status']}")
                
        except Exception as e:
            print(f"❌ Error in researcher: {str(e)}")
            state["error"] = str(e)
            state["status"] = "error"
            return state
