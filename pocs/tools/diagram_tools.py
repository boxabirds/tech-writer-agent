"""
Diagram Tools for the Tech Writer multi-agent system.

This module provides tools for creating diagrams based on code analysis.
"""

from typing import Dict, List, Any, Optional
import os
import re
from pathlib import Path
import json

def create_architecture_diagram(components: List[Dict[str, Any]]) -> str:
    """Create a Mermaid architecture diagram from components."""
    diagram = "```mermaid\nflowchart TD\n"
    
    # Add nodes
    for i, component in enumerate(components):
        node_id = f"C{i}"
        node_label = component.get("name", f"Component {i}")
        diagram += f"    {node_id}[{node_label}]\n"
    
    # Add connections
    for i, component in enumerate(components):
        node_id = f"C{i}"
        
        if "dependencies" in component:
            for dep in component["dependencies"]:
                # Find the index of the dependency
                dep_index = next((j for j, c in enumerate(components) 
                                 if c.get("name") == dep), None)
                
                if dep_index is not None:
                    dep_id = f"C{dep_index}"
                    diagram += f"    {node_id} --> {dep_id}\n"
    
    diagram += "```"
    return diagram

def create_component_hierarchy(components: List[Dict[str, Any]]) -> str:
    """Create a Mermaid component hierarchy diagram."""
    diagram = "```mermaid\nflowchart TD\n"
    
    # Track processed components to avoid duplicates
    processed = set()
    
    # Helper function to add a component and its children
    def add_component(component, parent_id=None, prefix=""):
        if component["name"] in processed:
            return
        
        processed.add(component["name"])
        
        # Create a node ID from the component name
        node_id = f"{prefix}{re.sub(r'[^a-zA-Z0-9]', '', component['name'])}"
        
        # Add the node
        diagram_text = f"    {node_id}[{component['name']}]\n"
        
        # Connect to parent if exists
        if parent_id:
            diagram_text += f"    {parent_id} --> {node_id}\n"
        
        # Process children
        if "children" in component:
            for i, child in enumerate(component["children"]):
                child_prefix = f"{prefix}c{i}"
                diagram_text += add_component(child, node_id, child_prefix)
        
        return diagram_text
    
    # Add all top-level components
    for i, component in enumerate(components):
        if "parent" not in component:
            diagram += add_component(component, prefix=f"c{i}")
    
    diagram += "```"
    return diagram

def create_data_flow_diagram(flows: List[Dict[str, Any]]) -> str:
    """Create a Mermaid data flow diagram."""
    diagram = "```mermaid\nflowchart LR\n"
    
    # Add nodes for sources and destinations
    nodes = set()
    for flow in flows:
        source = flow.get("source")
        destination = flow.get("destination")
        
        if source and source not in nodes:
            source_id = re.sub(r'[^a-zA-Z0-9]', '', source)
            diagram += f"    {source_id}[{source}]\n"
            nodes.add(source)
        
        if destination and destination not in nodes:
            dest_id = re.sub(r'[^a-zA-Z0-9]', '', destination)
            diagram += f"    {dest_id}[{destination}]\n"
            nodes.add(destination)
    
    # Add flows
    for flow in flows:
        source = flow.get("source")
        destination = flow.get("destination")
        label = flow.get("label", "")
        
        if source and destination:
            source_id = re.sub(r'[^a-zA-Z0-9]', '', source)
            dest_id = re.sub(r'[^a-zA-Z0-9]', '', destination)
            
            if label:
                diagram += f"    {source_id} -->|{label}| {dest_id}\n"
            else:
                diagram += f"    {source_id} --> {dest_id}\n"
    
    diagram += "```"
    return diagram

def create_deployment_diagram(components: List[Dict[str, Any]]) -> str:
    """Create a Mermaid deployment diagram."""
    diagram = "```mermaid\nflowchart TB\n"
    
    # Define subgraphs for environments
    environments = {}
    
    for component in components:
        env = component.get("environment", "Production")
        if env not in environments:
            environments[env] = []
        environments[env].append(component)
    
    # Add subgraphs for each environment
    for env_name, env_components in environments.items():
        env_id = re.sub(r'[^a-zA-Z0-9]', '', env_name)
        diagram += f"    subgraph {env_id}[{env_name}]\n"
        
        # Add components in this environment
        for i, component in enumerate(env_components):
            component_id = f"{env_id}_{i}"
            component_name = component.get("name", f"Component {i}")
            component_type = component.get("type", "service")
            
            # Use different shapes based on component type
            if component_type == "database":
                diagram += f"        {component_id}[(Database: {component_name})]\n"
            elif component_type == "storage":
                diagram += f"        {component_id}[({component_name})]\n"
            elif component_type == "queue":
                diagram += f"        {component_id}[({component_name})]\n"
            else:
                diagram += f"        {component_id}[{component_name}]\n"
        
        diagram += "    end\n"
    
    # Add connections between components
    for component in components:
        if "connections" in component:
            source_env = component.get("environment", "Production")
            source_env_id = re.sub(r'[^a-zA-Z0-9]', '', source_env)
            source_idx = environments[source_env].index(component)
            source_id = f"{source_env_id}_{source_idx}"
            
            for connection in component["connections"]:
                target_name = connection.get("target")
                target_env = connection.get("environment", source_env)
                target_env_id = re.sub(r'[^a-zA-Z0-9]', '', target_env)
                
                # Find the target component
                target_idx = next((i for i, c in enumerate(environments[target_env]) 
                                 if c.get("name") == target_name), None)
                
                if target_idx is not None:
                    target_id = f"{target_env_id}_{target_idx}"
                    label = connection.get("label", "")
                    
                    if label:
                        diagram += f"    {source_id} -->|{label}| {target_id}\n"
                    else:
                        diagram += f"    {source_id} --> {target_id}\n"
    
    diagram += "```"
    return diagram

def create_entity_relationship_diagram(entities: List[Dict[str, Any]]) -> str:
    """Create a Mermaid entity-relationship diagram."""
    diagram = "```mermaid\nerDiagram\n"
    
    # Add entities
    for entity in entities:
        entity_name = entity.get("name", "")
        if entity_name:
            diagram += f"    {entity_name} {{\n"
            
            # Add attributes
            if "attributes" in entity:
                for attr in entity["attributes"]:
                    attr_name = attr.get("name", "")
                    attr_type = attr.get("type", "string")
                    attr_key = attr.get("key", "")
                    
                    if attr_key == "primary":
                        diagram += f"        {attr_type} {attr_name} PK\n"
                    elif attr_key == "foreign":
                        diagram += f"        {attr_type} {attr_name} FK\n"
                    else:
                        diagram += f"        {attr_type} {attr_name}\n"
            
            diagram += "    }\n"
    
    # Add relationships
    for entity in entities:
        entity_name = entity.get("name", "")
        
        if "relationships" in entity:
            for rel in entity["relationships"]:
                target = rel.get("target", "")
                cardinality = rel.get("cardinality", "1--1")
                label = rel.get("label", "")
                
                if entity_name and target:
                    diagram += f"    {entity_name} {cardinality} {target} : {label}\n"
    
    diagram += "```"
    return diagram

def create_class_diagram(classes: List[Dict[str, Any]]) -> str:
    """Create a Mermaid class diagram."""
    diagram = "```mermaid\nclassDiagram\n"
    
    # Add classes
    for cls in classes:
        class_name = cls.get("name", "")
        
        # Add class definition
        if "extends" in cls and cls["extends"]:
            diagram += f"    class {class_name}\n"
            diagram += f"    {cls['extends']} <|-- {class_name}\n"
        else:
            diagram += f"    class {class_name}\n"
        
        # Add attributes
        if "attributes" in cls:
            for attr in cls["attributes"]:
                attr_name = attr.get("name", "")
                attr_type = attr.get("type", "")
                visibility = attr.get("visibility", "+")
                
                if attr_name:
                    if attr_type:
                        diagram += f"    {class_name} : {visibility}{attr_name} {attr_type}\n"
                    else:
                        diagram += f"    {class_name} : {visibility}{attr_name}\n"
        
        # Add methods
        if "methods" in cls:
            for method in cls["methods"]:
                method_name = method.get("name", "")
                return_type = method.get("return", "")
                visibility = method.get("visibility", "+")
                
                if method_name:
                    if return_type:
                        diagram += f"    {class_name} : {visibility}{method_name}() {return_type}\n"
                    else:
                        diagram += f"    {class_name} : {visibility}{method_name}()\n"
    
    # Add relationships
    for cls in classes:
        class_name = cls.get("name", "")
        
        if "relationships" in cls:
            for rel in cls["relationships"]:
                target = rel.get("target", "")
                type_rel = rel.get("type", "-->")
                label = rel.get("label", "")
                
                if class_name and target:
                    if label:
                        diagram += f"    {class_name} {type_rel} {target} : {label}\n"
                    else:
                        diagram += f"    {class_name} {type_rel} {target}\n"
    
    diagram += "```"
    return diagram

def create_sequence_diagram(interactions: List[Dict[str, Any]]) -> str:
    """Create a Mermaid sequence diagram."""
    diagram = "```mermaid\nsequenceDiagram\n"
    
    # Add participants
    participants = set()
    for interaction in interactions:
        source = interaction.get("source", "")
        target = interaction.get("target", "")
        
        if source and source not in participants:
            diagram += f"    participant {source}\n"
            participants.add(source)
        
        if target and target not in participants:
            diagram += f"    participant {target}\n"
            participants.add(target)
    
    # Add interactions
    for interaction in interactions:
        source = interaction.get("source", "")
        target = interaction.get("target", "")
        message = interaction.get("message", "")
        type_arrow = interaction.get("type", "->")
        
        if source and target and message:
            diagram += f"    {source}{type_arrow}{target}: {message}\n"
    
    diagram += "```"
    return diagram

def create_state_diagram(states: List[Dict[str, Any]]) -> str:
    """Create a Mermaid state diagram."""
    diagram = "```mermaid\nstateDiagram-v2\n"
    
    # Add states
    for state in states:
        state_name = state.get("name", "")
        
        if state_name:
            # Check if it's a composite state
            if "substates" in state and state["substates"]:
                diagram += f"    state {state_name} {{\n"
                
                # Add substates
                for substate in state["substates"]:
                    substate_name = substate.get("name", "")
                    if substate_name:
                        diagram += f"        {substate_name}\n"
                
                # Add transitions between substates
                for substate in state["substates"]:
                    substate_name = substate.get("name", "")
                    
                    if "transitions" in substate:
                        for transition in substate["transitions"]:
                            target = transition.get("target", "")
                            event = transition.get("event", "")
                            
                            if target:
                                if event:
                                    diagram += f"        {substate_name} --> {target}: {event}\n"
                                else:
                                    diagram += f"        {substate_name} --> {target}\n"
                
                diagram += "    }\n"
            else:
                diagram += f"    {state_name}\n"
    
    # Add transitions
    for state in states:
        state_name = state.get("name", "")
        
        if "transitions" in state:
            for transition in state["transitions"]:
                target = transition.get("target", "")
                event = transition.get("event", "")
                
                if target:
                    if event:
                        diagram += f"    {state_name} --> {target}: {event}\n"
                    else:
                        diagram += f"    {state_name} --> {target}\n"
    
    diagram += "```"
    return diagram

def create_gantt_chart(tasks: List[Dict[str, Any]]) -> str:
    """Create a Mermaid Gantt chart."""
    diagram = "```mermaid\ngantt\n"
    diagram += "    title Project Timeline\n"
    diagram += "    dateFormat YYYY-MM-DD\n"
    
    # Add sections
    sections = {}
    for task in tasks:
        section = task.get("section", "Default")
        if section not in sections:
            sections[section] = []
        sections[section].append(task)
    
    # Add tasks by section
    for section_name, section_tasks in sections.items():
        diagram += f"    section {section_name}\n"
        
        for task in section_tasks:
            task_name = task.get("name", "")
            start_date = task.get("start", "")
            end_date = task.get("end", "")
            dependencies = task.get("dependencies", [])
            
            if task_name and start_date and end_date:
                task_line = f"    {task_name}: {start_date}, {end_date}"
                
                if dependencies:
                    task_line += f", after {', '.join(dependencies)}"
                
                diagram += task_line + "\n"
    
    diagram += "```"
    return diagram

def create_pie_chart(data: Dict[str, int]) -> str:
    """Create a Mermaid pie chart."""
    diagram = "```mermaid\npie\n"
    diagram += "    title Distribution\n"
    
    for label, value in data.items():
        diagram += f"    \"{label}\" : {value}\n"
    
    diagram += "```"
    return diagram
