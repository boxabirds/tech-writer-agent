use anyhow::{Context, Result};
use async_openai::{
    types::{
        ChatCompletionRequestMessage, 
        ChatCompletionRequestSystemMessageArgs,
        ChatCompletionRequestUserMessageArgs,
        ChatCompletionRequestAssistantMessageArgs,
        ChatCompletionRequestToolMessageArgs,
        ChatCompletionTool, 
        FunctionObject,
        CreateChatCompletionRequestArgs, 
        ChatCompletionRequestMessageContentPart as ChatCompletionRequestMessageContentParts,
        ChatCompletionToolChoiceOption,
        Role as OpenAIRole,
    },
    Client,
};
use log::{debug, error, info, warn};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::Path;

use crate::types::{Message, Role, ToolCall};
use crate::tools::{create_tool_map, execute_tool};

/// Trait defining the interface for all agents
pub trait Agent {
    /// Run the agent to analyze a codebase
    fn run(&mut self, prompt: &str, directory: &str) -> Result<String>;
    
    /// Initialize the agent's memory with the prompt and directory
    fn initialize_memory(&mut self, prompt: &str, directory: &str);
    
    /// Call the LLM with the current memory and tools
    fn call_llm(&self) -> Result<(String, Vec<ToolCall>)>;
    
    /// Execute a tool call and return the result
    fn execute_tool(&self, tool_call: &ToolCall) -> Result<String>;
}

/// Base implementation for agents
pub struct BaseAgent {
    /// The model name to use for the LLM
    pub model_name: String,
    
    /// The base URL for the API
    pub base_url: Option<String>,
    
    /// The agent's memory (conversation history)
    pub memory: Vec<Message>,
    
    /// The final answer from the agent
    pub final_answer: Option<String>,
    
    /// The system prompt for the agent
    pub system_prompt: String,
    
    /// The OpenAI client
    pub client: Client,
}

impl BaseAgent {
    /// Create a new base agent
    pub fn new(model_name: &str, base_url: Option<&str>, system_prompt: &str) -> Result<Self> {
        // Initialize OpenAI client
        let client = if let Some(url) = base_url {
            Client::with_config(
                async_openai::config::Config::new()
                    .with_api_key(std::env::var("OPENAI_API_KEY")
                        .context("OPENAI_API_KEY environment variable not set")?)
                    .with_api_base(url)
            )
        } else {
            Client::new()
        };
        
        Ok(Self {
            model_name: model_name.to_string(),
            base_url: base_url.map(String::from),
            memory: Vec::new(),
            final_answer: None,
            system_prompt: system_prompt.to_string(),
            client,
        })
    }
    
    /// Create OpenAI tool definitions from the tool map
    pub fn create_openai_tool_definitions(&self) -> Vec<ChatCompletionTool> {
        let tool_map = create_tool_map();
        
        tool_map.iter()
            .map(|(name, definition)| {
                let function = FunctionObject::new()
                    .name(name.clone())
                    .description(definition["description"].as_str().map(String::from))
                    .parameters(serde_json::to_value(definition["parameters"].clone()).unwrap());
                
                ChatCompletionTool::function(function)
            })
            .collect()
    }
    
    /// Convert memory to OpenAI messages
    pub fn memory_to_openai_messages(&self) -> Vec<ChatCompletionRequestMessage> {
        let mut messages = Vec::new();
        
        // Add system message first
        let system_message = ChatCompletionRequestSystemMessageArgs::default()
            .content(self.system_prompt.clone())
            .build()
            .unwrap();
        messages.push(ChatCompletionRequestMessage::System(system_message));
        
        // Add the rest of the memory
        for message in &self.memory {
            match message.role {
                Role::System => {
                    // Skip system messages as we've already added the system prompt
                },
                Role::User => {
                    let user_message = ChatCompletionRequestUserMessageArgs::default()
                        .content(ChatCompletionRequestMessageContentParts::Text(message.content.clone()))
                        .name(message.name.clone())
                        .build()
                        .unwrap();
                    messages.push(ChatCompletionRequestMessage::User(user_message));
                },
                Role::Assistant => {
                    let mut assistant_args = ChatCompletionRequestAssistantMessageArgs::default();
                    assistant_args = assistant_args.content(Some(message.content.clone()));
                    
                    if let Some(name) = &message.name {
                        assistant_args = assistant_args.name(name.clone());
                    }
                    
                    if !message.tool_calls.is_empty() {
                        let tool_calls = message.tool_calls.iter()
                            .map(|tc| tc.to_openai_tool_call())
                            .collect::<Vec<_>>();
                        assistant_args = assistant_args.tool_calls(tool_calls);
                    }
                    
                    let assistant_message = assistant_args.build().unwrap();
                    messages.push(ChatCompletionRequestMessage::Assistant(assistant_message));
                },
                Role::Tool => {
                    let tool_message = ChatCompletionRequestToolMessageArgs::default()
                        .content(message.content.clone())
                        .tool_call_id(message.tool_call_id.clone().unwrap_or_default())
                        .build()
                        .unwrap();
                    messages.push(ChatCompletionRequestMessage::Tool(tool_message));
                },
            }
        }
        
        messages
    }
}

impl Agent for BaseAgent {
    fn run(&mut self, _prompt: &str, _directory: &str) -> Result<String> {
        // This is a placeholder implementation that should be overridden by subclasses
        Err(anyhow::anyhow!("BaseAgent.run() is not implemented"))
    }
    
    fn initialize_memory(&mut self, prompt: &str, directory: &str) {
        // Add the user prompt to memory
        let user_prompt = format!(
            "Please analyze the codebase in the directory '{}' according to this prompt:\n\n{}",
            directory, prompt
        );
        
        self.memory.push(Message::user(&user_prompt));
    }
    
    fn call_llm(&self) -> Result<(String, Vec<ToolCall>)> {
        // Convert memory to OpenAI messages
        let messages = self.memory_to_openai_messages();
        
        // Create tool definitions
        let tools = self.create_openai_tool_definitions();
        
        // Create chat completion request
        let request = async_openai::types::CreateChatCompletionRequestArgs::default()
            .model(self.model_name.clone())
            .messages(messages)
            .temperature(0.0)
            .top_p(1.0)
            .frequency_penalty(0.0)
            .presence_penalty(0.0)
            .tools(tools)
            .tool_choice(ChatCompletionToolChoiceOption::Auto)
            .build()?;
        
        // Call the API
        let response = tokio::runtime::Runtime::new()
            .context("Failed to create tokio runtime")?
            .block_on(async {
                self.client.chat().create(request).await
            })
            .context("Failed to call OpenAI API")?;
        
        // Extract the assistant's message
        let choice = response.choices.first()
            .ok_or_else(|| anyhow::anyhow!("No choices in OpenAI response"))?;
        
        let content = choice.message.content.clone().unwrap_or_default();
        
        // Extract tool calls if any
        let tool_calls = if let Some(tc) = &choice.message.tool_calls {
            tc.iter()
                .map(|tc| ToolCall {
                    id: tc.id.clone(),
                    r#type: tc.r#type.to_string(),
                    function: crate::types::ToolCallFunction {
                        name: tc.function.name.clone(),
                        arguments: tc.function.arguments.clone(),
                    },
                })
                .collect()
        } else {
            Vec::new()
        };
        
        Ok((content, tool_calls))
    }
    
    fn execute_tool(&self, tool_call: &ToolCall) -> Result<String> {
        let tool_name = &tool_call.function.name;
        let args: Value = serde_json::from_str(&tool_call.function.arguments)
            .with_context(|| format!("Failed to parse tool arguments: {}", tool_call.function.arguments))?;
        
        info!("Executing tool: {}", tool_name);
        
        if tool_name == "final_answer" {
            let answer = args["answer"].as_str()
                .ok_or_else(|| anyhow::anyhow!("Missing answer parameter"))?;
            
            return Ok(answer.to_string());
        }
        
        execute_tool(tool_name, &args)
    }
}
