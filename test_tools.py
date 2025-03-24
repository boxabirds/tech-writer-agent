#!/usr/bin/env python3
"""
Tests for the tools in tech-writer-from-scratch.py.
"""

import os
import sys
import pytest
from pathlib import Path
import tempfile
import shutil

# Import the tools directly from the script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# We need to import differently since hyphens aren't allowed in Python module names
import importlib.util
spec = importlib.util.spec_from_file_location(
    "tech_writer_script", 
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tech-writer-from-scratch.py")
)
tech_writer_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tech_writer_script)

# Get the functions from the imported module
find_all_matching_files = tech_writer_script.find_all_matching_files
read_file = tech_writer_script.read_file
calculate = tech_writer_script.calculate
get_gitignore_spec = tech_writer_script.get_gitignore_spec

# Constants
TEST_DATA_DIR = Path(__file__).parent / "test-data"


class TestFindAllMatchingFiles:
    """Tests for the find_all_matching_files function."""

    def test_basic_file_finding(self):
        """Test basic file finding functionality."""
        # Find all Python files
        python_files = find_all_matching_files(str(TEST_DATA_DIR), "*.py")
        
        # Check that we found the expected Python files
        python_filenames = [p.name for p in python_files]
        assert "main.py" in python_filenames
        assert "utils.py" in python_filenames
        
        # Check that we didn't find non-Python files
        assert not any(p.name == "script.js" for p in python_files)
        assert not any(p.name == "README.md" for p in python_files)

    def test_recursive_file_finding(self):
        """Test recursive file finding."""
        # Find all JavaScript and JSX files recursively
        js_files = find_all_matching_files(str(TEST_DATA_DIR), "*.js*")
        
        # Check that we found files in subdirectories
        js_filenames = [p.name for p in js_files]
        assert "script.js" in js_filenames
        assert "Button.jsx" in js_filenames

    def test_non_recursive_file_finding(self):
        """Test non-recursive file finding."""
        # Find files in the root directory only
        root_files = find_all_matching_files(
            str(TEST_DATA_DIR), 
            "*.*", 
            include_subdirs=False
        )
        
        # Check that we only found files in the root directory
        root_filenames = [p.name for p in root_files]
        assert "main.py" in root_filenames
        assert "script.js" in root_filenames
        assert not any(p.name == "Button.jsx" for p in root_files)

    def test_hidden_files(self):
        """Test handling of hidden files."""
        # By default, hidden files should be excluded
        all_files = find_all_matching_files(str(TEST_DATA_DIR))
        hidden_files = [p for p in all_files if p.name.startswith('.')]
        assert len(hidden_files) == 0
        
        # When include_hidden is True, hidden files should be included
        all_files_with_hidden = find_all_matching_files(
            str(TEST_DATA_DIR), 
            include_hidden=True
        )
        hidden_files = [p for p in all_files_with_hidden if p.name.startswith('.')]
        assert len(hidden_files) > 0
        assert any(p.name == ".hidden_config.json" for p in hidden_files)

    def test_gitignore_respect(self):
        """Test that .gitignore patterns are respected."""
        # Create a temporary directory with a .gitignore file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a .gitignore file
            with open(temp_path / ".gitignore", "w") as f:
                f.write("*.log\n")
                f.write("ignored_dir/\n")
            
            # Create some files
            (temp_path / "test.py").touch()
            (temp_path / "test.log").touch()
            (temp_path / "ignored_dir").mkdir()
            (temp_path / "ignored_dir" / "file.txt").touch()
            
            # Find all files with respect_gitignore=True (default)
            files = find_all_matching_files(str(temp_path))
            filenames = [p.name for p in files]
            
            # Check that ignored files are not included
            assert "test.py" in filenames
            assert "test.log" not in filenames
            assert not any(p.name == "file.txt" for p in files)
            
            # Find all files with respect_gitignore=False
            files_no_ignore = find_all_matching_files(
                str(temp_path), 
                respect_gitignore=False
            )
            filenames_no_ignore = [p.name for p in files_no_ignore]
            
            # Check that ignored files are included
            assert "test.py" in filenames_no_ignore
            assert "test.log" in filenames_no_ignore


class TestReadFile:
    """Tests for the read_file function."""
    
    def test_read_existing_file(self):
        """Test reading an existing file."""
        # Read the README.md file
        content = read_file(str(TEST_DATA_DIR / "README.md"))
        
        # Check that the content is a string and contains expected text
        assert isinstance(content, str)
        assert "Test Data Directory" in content
        
    def test_read_nonexistent_file(self):
        """Test reading a nonexistent file."""
        # Try to read a file that doesn't exist
        content = read_file(str(TEST_DATA_DIR / "nonexistent.txt"))
        
        # Check that we get an error message
        assert "error" in content
        assert "File not found" in content


class TestCalculate:
    """Tests for the calculate function."""
    
    def test_basic_arithmetic(self):
        """Test basic arithmetic operations."""
        # Test addition
        result = calculate("2 + 2")
        assert "4" in result
        
        # Test subtraction
        result = calculate("10 - 5")
        assert "5" in result
        
        # Test multiplication
        result = calculate("3 * 4")
        assert "12" in result
        
        # Test division
        result = calculate("20 / 5")
        assert "4" in result
    
    def test_complex_expressions(self):
        """Test more complex expressions."""
        # Test a more complex expression
        result = calculate("(10 + 5) * 2 / 3")
        assert "10" in result
    
    def test_invalid_expressions(self):
        """Test invalid expressions."""
        # Test an expression with invalid syntax
        result = calculate("10 +* 5")
        assert "error" in result
        
        # Test an expression with a security risk
        result = calculate("__import__('os').system('ls')")
        assert "error" in result


if __name__ == "__main__":
    pytest.main(["-v", __file__])
