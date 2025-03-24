# Utility functions for testing

import os
from pathlib import Path
import json

def get_file_info(file_path):
    """Get basic information about a file."""
    path = Path(file_path)
    return {
        "name": path.name,
        "extension": path.suffix,
        "size": path.stat().st_size,
        "is_directory": path.is_dir()
    }

def list_directory(directory):
    """List all files in a directory."""
    path = Path(directory)
    return [item.name for item in path.iterdir()]

def save_json(data, file_path):
    """Save data as JSON to a file."""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
