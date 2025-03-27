use anyhow::{Context, Result};
use clap::Parser;
use dotenv::dotenv;
use log::{debug, error, info, warn};
use std::path::{Path, PathBuf};
use std::str::FromStr;

mod agents;
mod prompts;
mod tools;
mod types;
mod utils;

use agents::{Agent, ReActAgent, ReflexionAgent};
use types::AgentType;
use utils::{ensure_output_directory, read_prompt_file, save_results};

/// Tech Writer Agent - A tool for analyzing codebases and generating documentation
#[derive(Parser, Debug)]
#[clap(version, about, long_about = None)]
struct Args {
    /// Directory containing the codebase to analyze
    #[clap(short, long, value_parser)]
    directory: String,

    /// Path to a file containing the analysis prompt
    #[clap(short, long, value_parser)]
    prompt: String,

    /// Model to use for analysis (default: gpt-4o-mini)
    #[clap(short, long, default_value = "gpt-4o-mini")]
    model: String,

    /// Type of agent to use (react or reflexion)
    #[clap(short, long, default_value = "react")]
    agent_type: String,

    /// Base URL for the API (optional)
    #[clap(short, long)]
    base_url: Option<String>,
}

/// Analyze a codebase using the specified agent type
fn analyze_codebase(
    directory_path: &str,
    prompt_file_path: &str,
    model_name: &str,
    agent_type: AgentType,
    base_url: Option<&str>,
) -> Result<String> {
    // Read the prompt file
    let prompt = read_prompt_file(prompt_file_path)?;
    
    // Create the appropriate agent
    let mut agent: Box<dyn Agent> = match agent_type {
        AgentType::ReAct => {
            info!("Using ReAct agent with standard planning");
            Box::new(ReActAgent::new(model_name, base_url)?)
        }
        AgentType::Reflexion => {
            info!("Using Reflexion agent with reflection capabilities");
            Box::new(ReflexionAgent::new(model_name, base_url)?)
        }
    };
    
    // Run the agent
    let result = agent.run(&prompt, directory_path)?;
    
    Ok(result)
}

/// Save analysis results to a file
fn save_analysis_results(
    analysis_result: &str,
    model_name: &str,
    agent_type: AgentType,
) -> Result<PathBuf> {
    // Ensure the output directory exists
    let output_dir = ensure_output_directory(".")?;
    
    // Save the results
    let output_path = save_results(
        output_dir,
        analysis_result,
        model_name,
        &agent_type.to_string(),
    )?;
    
    info!("Analysis complete. Results saved to {}", output_path.display());
    
    Ok(output_path)
}

fn main() -> Result<()> {
    // Initialize environment
    dotenv().ok();
    env_logger::init();
    
    // Parse command-line arguments
    let args = Args::parse();
    
    // Validate the directory
    let directory_path = Path::new(&args.directory);
    if !directory_path.exists() || !directory_path.is_dir() {
        return Err(anyhow::anyhow!("Directory not found: {}", args.directory));
    }
    
    // Validate the prompt file
    let prompt_file_path = Path::new(&args.prompt);
    if !prompt_file_path.exists() || !prompt_file_path.is_file() {
        return Err(anyhow::anyhow!("Prompt file not found: {}", args.prompt));
    }
    
    // Parse agent type
    let agent_type = AgentType::from_str(&args.agent_type)
        .map_err(|e| anyhow::anyhow!("Invalid agent type: {}", e))?;
    
    // Analyze the codebase
    let analysis_result = analyze_codebase(
        &args.directory,
        &args.prompt,
        &args.model,
        agent_type,
        args.base_url.as_deref(),
    )?;
    
    // Save the results
    let output_path = save_analysis_results(
        &analysis_result,
        &args.model,
        agent_type,
    )?;
    
    info!("Analysis complete. Results saved to {}", output_path.display());
    
    Ok(())
}
