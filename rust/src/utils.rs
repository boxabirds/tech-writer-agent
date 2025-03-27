use anyhow::{Context, Result};
use ignore::{DirEntry, WalkBuilder};
use log::{debug, error, info, warn};
use std::fs;
use std::path::{Path, PathBuf};
use std::io::Read;

/// Read a file and return its contents as a string
pub fn read_file<P: AsRef<Path>>(path: P) -> Result<String> {
    let path = path.as_ref();
    
    // Try to read with UTF-8 encoding first
    match fs::read_to_string(path) {
        Ok(content) => Ok(content),
        Err(e) => {
            warn!("Failed to read file as UTF-8: {}, trying binary read", e);
            
            // If UTF-8 fails, try reading as binary and converting to Latin-1
            let mut file = fs::File::open(path)
                .with_context(|| format!("Failed to open file: {}", path.display()))?;
            
            let mut buffer = Vec::new();
            file.read_to_end(&mut buffer)
                .with_context(|| format!("Failed to read file: {}", path.display()))?;
            
            // Convert binary to Latin-1 (ISO-8859-1) string
            let content = buffer.iter()
                .map(|&c| c as char)
                .collect::<String>();
            
            Ok(content)
        }
    }
}

/// Read a prompt file and return its contents
pub fn read_prompt_file<P: AsRef<Path>>(path: P) -> Result<String> {
    let path = path.as_ref();
    
    if !path.exists() {
        return Err(anyhow::anyhow!("Prompt file not found: {}", path.display()));
    }
    
    read_file(path).map(|content| content.trim().to_string())
}

/// Get an ignore instance from a .gitignore file
pub fn get_gitignore_spec<P: AsRef<Path>>(directory: P) -> ignore::gitignore::Gitignore {
    let directory = directory.as_ref();
    let gitignore_path = directory.join(".gitignore");
    
    if gitignore_path.exists() {
        let (gitignore, error_opt) = ignore::gitignore::Gitignore::new(&gitignore_path);
        
        if let Some(e) = error_opt {
            error!("Error reading .gitignore: {}", e);
        } else {
            let pattern_count = gitignore.len();
            info!("Added {} patterns from .gitignore", pattern_count);
        }
        
        gitignore
    } else {
        ignore::gitignore::Gitignore::empty()
    }
}

/// Check if a path is ignored by .gitignore
fn is_ignored(entry: &DirEntry, gitignore: &ignore::gitignore::Gitignore) -> bool {
    if let Some(path) = entry.path().to_str() {
        let is_ignored = gitignore.matched(path, entry.path().is_dir()).is_ignore();
        if is_ignored {
            debug!("Ignoring path: {}", path);
        }
        is_ignored
    } else {
        warn!("Path contains invalid UTF-8: {:?}", entry.path());
        true // Ignore paths with invalid UTF-8
    }
}

/// List all files in a directory respecting .gitignore
pub fn list_files<P: AsRef<Path>>(directory: P) -> Result<Vec<PathBuf>> {
    let directory = directory.as_ref();
    
    // Convert to absolute path to ensure we stay within bounds
    let abs_directory = fs::canonicalize(directory)
        .with_context(|| format!("Failed to canonicalize directory: {}", directory.display()))?;
    
    let gitignore = get_gitignore_spec(&abs_directory);
    let mut files = Vec::new();
    
    let walker = WalkBuilder::new(&abs_directory)
        .hidden(false) // Don't skip hidden files
        .git_ignore(true) // Use .gitignore
        .build();
    
    for result in walker {
        match result {
            Ok(entry) => {
                let path = entry.path();
                
                // Skip directories and ignored files
                if path.is_dir() || is_ignored(&entry, &gitignore) {
                    continue;
                }
                
                // Skip symlinks to avoid permission issues
                if path.symlink_metadata().map(|m| m.file_type().is_symlink()).unwrap_or(false) {
                    debug!("Skipping symlink: {}", path.display());
                    continue;
                }
                
                // Ensure the path is within the specified directory
                if let Ok(rel_path) = path.strip_prefix(&abs_directory) {
                    files.push(rel_path.to_path_buf());
                } else {
                    warn!("Path outside directory: {}", path.display());
                }
            },
            Err(e) => {
                warn!("Error walking directory: {}", e);
            }
        }
    }
    
    Ok(files)
}

/// Check if a file is likely binary
pub fn is_binary_file<P: AsRef<Path>>(path: P) -> bool {
    let path = path.as_ref();
    
    // Use the is_executable crate to check for executable files
    if is_executable::is_executable(path) {
        return true;
    }
    
    // Check file extension
    if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
        let binary_extensions = [
            "exe", "dll", "so", "dylib", "bin", "obj", "o", 
            "a", "lib", "png", "jpg", "jpeg", "gif", "bmp", 
            "ico", "tif", "tiff", "webp", "mp3", "mp4", "avi", 
            "mov", "wmv", "flv", "zip", "tar", "gz", "7z", 
            "rar", "jar", "war", "class", "pyc", "pyd", "pyo",
        ];
        
        if binary_extensions.contains(&ext.to_lowercase().as_str()) {
            return true;
        }
    }
    
    // Read the first few bytes to check for binary content
    if let Ok(file) = fs::File::open(path) {
        let mut buffer = [0; 512];
        if let Ok(n) = file.take(512).read(&mut buffer) {
            // Check for null bytes or other binary indicators
            for i in 0..n {
                if buffer[i] == 0 {
                    return true;
                }
            }
        }
    }
    
    false
}

/// Create the output directory if it doesn't exist
pub fn ensure_output_directory<P: AsRef<Path>>(directory: P) -> Result<PathBuf> {
    let output_dir = directory.as_ref().join("output");
    
    if !output_dir.exists() {
        fs::create_dir_all(&output_dir)
            .with_context(|| format!("Failed to create output directory: {}", output_dir.display()))?;
    }
    
    Ok(output_dir)
}

/// Save analysis results to a file
pub fn save_results<P: AsRef<Path>>(
    output_dir: P, 
    analysis_result: &str, 
    model_name: &str, 
    agent_type: &str
) -> Result<PathBuf> {
    let output_dir = output_dir.as_ref();
    let timestamp = chrono::Local::now().format("%Y-%m-%dT%H%M");
    let filename = format!("{}-{}-{}.md", timestamp, agent_type, model_name);
    let output_path = output_dir.join(filename);
    
    fs::write(&output_path, analysis_result)
        .with_context(|| format!("Failed to write results to file: {}", output_path.display()))?;
    
    Ok(output_path)
}
