use anyhow::{Context, Result};
use log::{debug, error, info, warn};
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

use crate::types::{CalculationResult, CodeMatch, FileInfo, FileResult};
use crate::utils::{is_binary_file, list_files, read_file};

/// Find all files matching a pattern in a directory
pub fn find_all_matching_files(directory: &str, pattern: Option<&str>) -> Result<Vec<FileInfo>> {
    let dir_path = Path::new(directory);
    if !dir_path.exists() || !dir_path.is_dir() {
        return Err(anyhow::anyhow!("Directory not found: {}", directory));
    }

    let files = list_files(dir_path)?;
    let pattern_regex = if let Some(pattern) = pattern {
        match Regex::new(pattern) {
            Ok(re) => Some(re),
            Err(e) => {
                warn!("Invalid regex pattern: {}, error: {}", pattern, e);
                None
            }
        }
    } else {
        None
    };

    let mut results = Vec::new();
    for file_path in files {
        let full_path = dir_path.join(&file_path);
        
        // Skip binary files
        if is_binary_file(&full_path) {
            debug!("Skipping binary file: {}", file_path.display());
            continue;
        }
        
        // Apply pattern filter if provided
        if let Some(ref re) = pattern_regex {
            if !re.is_match(&file_path.to_string_lossy()) {
                continue;
            }
        }
        
        // Get file metadata
        match fs::metadata(&full_path) {
            Ok(metadata) => {
                results.push(FileInfo {
                    path: file_path.to_string_lossy().to_string(),
                    is_directory: metadata.is_dir(),
                    size: if metadata.is_file() { Some(metadata.len()) } else { None },
                });
            }
            Err(e) => {
                warn!("Failed to get metadata for {}: {}", file_path.display(), e);
            }
        }
        
        // Limit results to avoid overwhelming the agent
        if results.len() >= 50 {
            info!("Limiting file search results to 50 files");
            break;
        }
    }

    Ok(results)
}

/// Read the contents of a file
pub fn read_file_tool(file_path: &str) -> FileResult {
    let path = Path::new(file_path);
    
    if !path.exists() {
        return FileResult {
            file: Some(file_path.to_string()),
            content: None,
            error: Some(format!("File not found: {}", file_path)),
        };
    }
    
    if path.is_dir() {
        return FileResult {
            file: Some(file_path.to_string()),
            content: None,
            error: Some(format!("Path is a directory, not a file: {}", file_path)),
        };
    }
    
    if is_binary_file(path) {
        return FileResult {
            file: Some(file_path.to_string()),
            content: None,
            error: Some(format!("Cannot read binary file: {}", file_path)),
        };
    }
    
    match read_file(path) {
        Ok(content) => FileResult {
            file: Some(file_path.to_string()),
            content: Some(content),
            error: None,
        },
        Err(e) => FileResult {
            file: Some(file_path.to_string()),
            content: None,
            error: Some(format!("Error reading file: {}", e)),
        },
    }
}

/// Search for code matching a query in a directory
pub fn search_code(directory: &str, query: &str) -> Result<Vec<CodeMatch>> {
    let dir_path = Path::new(directory);
    if !dir_path.exists() || !dir_path.is_dir() {
        return Err(anyhow::anyhow!("Directory not found: {}", directory));
    }
    
    let files = list_files(dir_path)?;
    let query_regex = match Regex::new(&regex::escape(query)) {
        Ok(re) => re,
        Err(e) => return Err(anyhow::anyhow!("Invalid search query: {}", e)),
    };
    
    let mut matches = Vec::new();
    
    for file_path in files {
        let full_path = dir_path.join(&file_path);
        
        // Skip binary files
        if is_binary_file(&full_path) {
            continue;
        }
        
        // Read and search file
        match read_file(&full_path) {
            Ok(content) => {
                for (i, line) in content.lines().enumerate() {
                    if query_regex.is_match(line) {
                        matches.push(CodeMatch {
                            file: file_path.to_string_lossy().to_string(),
                            line: i + 1, // 1-based line numbers
                            content: line.to_string(),
                        });
                        
                        // Limit matches per file
                        if matches.len() >= 50 {
                            info!("Limiting code search results to 50 matches");
                            return Ok(matches);
                        }
                    }
                }
            }
            Err(e) => {
                warn!("Failed to read file {}: {}", file_path.display(), e);
            }
        }
    }
    
    Ok(matches)
}

/// Evaluate a mathematical expression
pub fn calculate(expression: &str) -> CalculationResult {
    // This is a simple implementation that uses the eval crate
    // In a production environment, you might want to use a more robust solution
    
    // Remove any unsafe characters
    let sanitized = expression.chars()
        .filter(|c| c.is_ascii_digit() || ['+', '-', '*', '/', '.', '(', ')', ' '].contains(c))
        .collect::<String>();
    
    if sanitized != expression {
        return CalculationResult {
            expression: expression.to_string(),
            result: None,
            error: Some("Expression contains unsafe characters".to_string()),
        };
    }
    
    // Use a safe expression evaluator
    match meval::eval_str(&sanitized) {
        Ok(result) => CalculationResult {
            expression: expression.to_string(),
            result: Some(result),
            error: None,
        },
        Err(e) => CalculationResult {
            expression: expression.to_string(),
            result: None,
            error: Some(format!("Error evaluating expression: {}", e)),
        },
    }
}

/// Process a final answer from the agent
pub fn final_answer(answer: &str) -> String {
    answer.to_string()
}

/// Create a map of tool functions
pub fn create_tool_map() -> serde_json::Map<String, Value> {
    let mut tools = serde_json::Map::new();
    
    // find_all_matching_files
    tools.insert(
        "find_all_matching_files".to_string(),
        json!({
            "description": "Find files matching a pattern in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional regex pattern to match filenames"
                    }
                },
                "required": ["directory"]
            }
        }),
    );
    
    // read_file
    tools.insert(
        "read_file".to_string(),
        json!({
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["file_path"]
            }
        }),
    );
    
    // search_code
    tools.insert(
        "search_code".to_string(),
        json!({
            "description": "Search for code matching a query in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["directory", "query"]
            }
        }),
    );
    
    // calculate
    tools.insert(
        "calculate".to_string(),
        json!({
            "description": "Evaluate a mathematical expression",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate"
                    }
                },
                "required": ["expression"]
            }
        }),
    );
    
    // final_answer
    tools.insert(
        "final_answer".to_string(),
        json!({
            "description": "Provide the final answer for the analysis",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "The final analysis result"
                    }
                },
                "required": ["answer"]
            }
        }),
    );
    
    tools
}

/// Execute a tool call
pub fn execute_tool(tool_name: &str, args: &Value) -> Result<String> {
    match tool_name {
        "find_all_matching_files" => {
            let directory = args["directory"].as_str()
                .ok_or_else(|| anyhow::anyhow!("Missing directory parameter"))?;
            let pattern = args["pattern"].as_str();
            
            let results = find_all_matching_files(directory, pattern)?;
            serde_json::to_string_pretty(&results)
                .context("Failed to serialize file search results")
        },
        
        "read_file" => {
            let file_path = args["file_path"].as_str()
                .ok_or_else(|| anyhow::anyhow!("Missing file_path parameter"))?;
            
            let result = read_file_tool(file_path);
            serde_json::to_string_pretty(&result)
                .context("Failed to serialize file read result")
        },
        
        "search_code" => {
            let directory = args["directory"].as_str()
                .ok_or_else(|| anyhow::anyhow!("Missing directory parameter"))?;
            let query = args["query"].as_str()
                .ok_or_else(|| anyhow::anyhow!("Missing query parameter"))?;
            
            let results = search_code(directory, query)?;
            serde_json::to_string_pretty(&results)
                .context("Failed to serialize code search results")
        },
        
        "calculate" => {
            let expression = args["expression"].as_str()
                .ok_or_else(|| anyhow::anyhow!("Missing expression parameter"))?;
            
            let result = calculate(expression);
            serde_json::to_string_pretty(&result)
                .context("Failed to serialize calculation result")
        },
        
        "final_answer" => {
            let answer = args["answer"].as_str()
                .ok_or_else(|| anyhow::anyhow!("Missing answer parameter"))?;
            
            Ok(final_answer(answer))
        },
        
        _ => Err(anyhow::anyhow!("Unknown tool: {}", tool_name)),
    }
}
