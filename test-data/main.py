#!/usr/bin/env python3
# Sample Python file for testing

def hello_world():
    """A simple function that returns a greeting."""
    return "Hello, World!"

class TestClass:
    """A sample class for testing."""
    
    def __init__(self, name):
        self.name = name
    
    def greet(self):
        """Return a personalized greeting."""
        return f"Hello, {self.name}!"

if __name__ == "__main__":
    print(hello_world())
    test = TestClass("Tester")
    print(test.greet())
