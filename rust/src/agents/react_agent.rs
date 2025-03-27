use anyhow::{Context, Result};
use log::{debug, error, info, warn};
use serde_json::Value;
use std::path::Path;

use crate::agents::base_agent::{Agent, BaseAgent};
use crate::prompts;
use crate::types::{Message, Role, ToolCall};

/// Agent that uses the ReAct pattern for codebase analysis
pub struct ReActAgent {
    /// The base agent implementation
    pub base: BaseAgent,
}

impl ReActAgent {
    /// Create a new ReAct agent
    pub fn new(model_name: &str, base_url: Option<&str>) -> Result<Self> {
        let system_prompt = prompts::react_system_prompt();
        
        Ok(Self {
            base: BaseAgent::new(model_name, base_url, &system_prompt)?,
        })
    }
}

impl Agent for ReActAgent {
    fn run(&mut self, prompt: &str, directory: &str) -> Result<String> {
        info!("Using ReAct agent with standard planning");
        
        // Initialize memory with the prompt and directory
        self.initialize_memory(prompt, directory);
        
        let mut step = 1;
        
        // Main agent loop
        loop {
            info!("\n--- Step {} ---", step);
            step += 1;
            
            // Call the LLM
            let (content, tool_calls) = self.call_llm()?;
            
            // Add the assistant's message to memory
            let mut assistant_message = Message::assistant(&content);
            assistant_message.tool_calls = tool_calls.clone();
            self.base.memory.push(assistant_message);
            
            // If no tool calls, continue to the next iteration
            if tool_calls.is_empty() {
                info!("No tool calls received");
                continue;
            }
            
            // Process each tool call
            for tool_call in &tool_calls {
                let tool_name = &tool_call.function.name;
                info!("Executing tool: {}", tool_name);
                
                // Execute the tool
                let result = self.execute_tool(tool_call)?;
                
                // If the tool is final_answer, we're done
                if tool_name == "final_answer" {
                    info!("Final answer received from tool execution");
                    self.base.final_answer = Some(result.clone());
                    return Ok(result);
                }
                
                // Add the tool result to memory
                self.base.memory.push(Message::tool(
                    &tool_call.id,
                    tool_name,
                    &result,
                ));
            }
            
            // Check if we've exceeded the maximum number of steps
            if step > 20 {
                warn!("Exceeded maximum number of steps (20)");
                return Err(anyhow::anyhow!("Exceeded maximum number of steps"));
            }
        }
    }
    
    fn initialize_memory(&mut self, prompt: &str, directory: &str) {
        self.base.initialize_memory(prompt, directory);
    }
    
    fn call_llm(&self) -> Result<(String, Vec<ToolCall>)> {
        self.base.call_llm()
    }
    
    fn execute_tool(&self, tool_call: &ToolCall) -> Result<String> {
        self.base.execute_tool(tool_call)
    }
}
