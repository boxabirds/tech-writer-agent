package main

import (
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/joho/godotenv"
	gitignore "github.com/sabhiram/go-gitignore"
)

// getEnv retrieves an environment variable or returns a default value
func getEnv(key, defaultValue string) string {
	// Load .env file if it exists
	_ = godotenv.Load()
	
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	return value
}

// listFiles lists all files in a directory, respecting .gitignore patterns
func listFiles(directory string) ([]string, error) {
	var files []string
	
	// Convert to absolute path to ensure we stay within bounds
	absDirectory, err := filepath.Abs(directory)
	if err != nil {
		return nil, fmt.Errorf("error getting absolute path: %v", err)
	}
	
	// Try to load .gitignore file
	gitignorePath := filepath.Join(absDirectory, ".gitignore")
	var ignore *gitignore.GitIgnore
	
	if _, err := os.Stat(gitignorePath); err == nil {
		ignore, err = gitignore.CompileIgnoreFile(gitignorePath)
		if err != nil {
			return nil, fmt.Errorf("error loading .gitignore: %v", err)
		}
		fmt.Printf("Added patterns from .gitignore\n")
	} else {
		// Create an empty ignore if no .gitignore file exists
		ignore = gitignore.CompileIgnoreLines([]string{}...)
	}
	
	// Walk the directory
	err = filepath.Walk(absDirectory, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil // Skip files with errors instead of failing the whole walk
		}
		
		// Ensure we don't traverse outside the specified directory
		if !strings.HasPrefix(path, absDirectory) {
			return filepath.SkipDir
		}
		
		// Skip symlinks to avoid permission issues
		if info.Mode()&os.ModeSymlink != 0 {
			return filepath.SkipDir
		}
		
		// Skip directories
		if info.IsDir() {
			// Skip .git directory and other hidden directories
			if strings.HasPrefix(info.Name(), ".") {
				return filepath.SkipDir
			}
			return nil
		}
		
		// Get relative path for checking against .gitignore
		relPath, err := filepath.Rel(absDirectory, path)
		if err != nil {
			return nil // Skip files with errors
		}
		
		// Skip files that match .gitignore patterns
		if ignore.MatchesPath(relPath) {
			return nil
		}
		
		files = append(files, path)
		return nil
	})
	
	if err != nil {
		return nil, fmt.Errorf("error walking directory: %v", err)
	}
	
	return files, nil
}

// readFile reads the content of a file
func readFile(path string) (string, error) {
	content, err := ioutil.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("error reading file: %v", err)
	}
	
	return string(content), nil
}

// writeFile writes content to a file
func writeFile(path string, content string) error {
	// Create directory if it doesn't exist
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("error creating directory: %v", err)
	}
	
	// Write the file
	if err := ioutil.WriteFile(path, []byte(content), 0644); err != nil {
		return fmt.Errorf("error writing file: %v", err)
	}
	
	return nil
}

// CodeMatch represents a match in the code search
type CodeMatch struct {
	File    string `json:"file"`
	Line    int    `json:"line"`
	Content string `json:"content"`
}

// searchCode searches for a pattern in the codebase
func searchCode(directory string, query string, filePattern string) ([]CodeMatch, error) {
	var matches []CodeMatch
	
	// Get all files
	files, err := listFiles(directory)
	if err != nil {
		return nil, err
	}
	
	// Compile regex for the query
	re, err := regexp.Compile(query)
	if err != nil {
		// If regex compilation fails, use simple string matching
		re = nil
	}
	
	// Filter files by pattern if provided
	if filePattern != "" {
		var filteredFiles []string
		for _, file := range files {
			matched, err := filepath.Match(filePattern, filepath.Base(file))
			if err != nil {
				return nil, fmt.Errorf("error matching file pattern: %v", err)
			}
			if matched {
				filteredFiles = append(filteredFiles, file)
			}
		}
		files = filteredFiles
	}
	
	// Search in each file
	for _, file := range files {
		content, err := readFile(file)
		if err != nil {
			continue
		}
		
		lines := strings.Split(content, "\n")
		for i, line := range lines {
			var matched bool
			if re != nil {
				matched = re.MatchString(line)
			} else {
				matched = strings.Contains(line, query)
			}
			
			if matched {
				matches = append(matches, CodeMatch{
					File:    file,
					Line:    i + 1, // 1-based line numbers
					Content: line,
				})
			}
		}
	}
	
	return matches, nil
}
