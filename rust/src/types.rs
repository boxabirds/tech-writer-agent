use async_openai::types::{
    ChatCompletionRequestMessage,
    ChatCompletionRequestSystemMessageArgs,
    ChatCompletionRequestUserMessageArgs,
    ChatCompletionRequestAssistantMessageArgs,
    ChatCompletionRequestToolMessageArgs,
    ChatCompletionRequestMessageContentPart as ChatCompletionRequestMessageContentParts,
    ChatCompletionMessageToolCall,
    ChatCompletionToolType,
    FunctionObject,
    FunctionObjectArgs,
    FunctionCall,
    ChatCompletionTool,
    ChatCompletionToolArgs,
    Role as OpenAIRole,
};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Role enum for messages
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Role {
    #[serde(rename = "system")]
    System,
    #[serde(rename = "user")]
    User,
    #[serde(rename = "assistant")]
    Assistant,
    #[serde(rename = "tool")]
    Tool,
}

/// Message struct for agent memory
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: Role,
    pub content: String,
    pub tool_call_id: Option<String>,
    pub name: Option<String>,
    pub tool_calls: Vec<ToolCall>,
}

impl Message {
    /// Create a new system message
    pub fn system(content: &str) -> Self {
        Self {
            role: Role::System,
            content: content.to_string(),
            tool_call_id: None,
            name: None,
            tool_calls: Vec::new(),
        }
    }

    /// Create a new user message
    pub fn user(content: &str) -> Self {
        Self {
            role: Role::User,
            content: content.to_string(),
            tool_call_id: None,
            name: None,
            tool_calls: Vec::new(),
        }
    }

    /// Create a new assistant message
    pub fn assistant(content: &str) -> Self {
        Self {
            role: Role::Assistant,
            content: content.to_string(),
            tool_call_id: None,
            name: None,
            tool_calls: Vec::new(),
        }
    }

    /// Create a new tool message
    pub fn tool(tool_call_id: &str, name: &str, content: &str) -> Self {
        Self {
            role: Role::Tool,
            content: content.to_string(),
            tool_call_id: Some(tool_call_id.to_string()),
            name: Some(name.to_string()),
            tool_calls: Vec::new(),
        }
    }

    /// Convert to OpenAI API message format
    pub fn to_openai_message(&self) -> ChatCompletionRequestMessage {
        match self.role {
            Role::System => {
                let system_message = ChatCompletionRequestSystemMessageArgs::default()
                    .content(self.content.clone())
                    .name(self.name.clone())
                    .build()
                    .unwrap();
                ChatCompletionRequestMessage::System(system_message)
            },
            Role::User => {
                let user_message = ChatCompletionRequestUserMessageArgs::default()
                    .content(ChatCompletionRequestMessageContentParts::Text(self.content.clone()))
                    .name(self.name.clone())
                    .build()
                    .unwrap();
                ChatCompletionRequestMessage::User(user_message)
            },
            Role::Assistant => {
                let mut assistant_args = ChatCompletionRequestAssistantMessageArgs::default();
                
                if !self.content.is_empty() {
                    assistant_args = assistant_args.content(Some(self.content.clone()));
                }
                
                if let Some(name) = &self.name {
                    assistant_args = assistant_args.name(name.clone());
                }
                
                if !self.tool_calls.is_empty() {
                    let tool_calls = self.tool_calls.iter()
                        .map(|tc| tc.to_openai_tool_call())
                        .collect::<Vec<_>>();
                    assistant_args = assistant_args.tool_calls(tool_calls);
                }
                
                let assistant_message = assistant_args.build().unwrap();
                ChatCompletionRequestMessage::Assistant(assistant_message)
            },
            Role::Tool => {
                let tool_message = ChatCompletionRequestToolMessageArgs::default()
                    .content(self.content.clone())
                    .tool_call_id(self.tool_call_id.clone().unwrap_or_default())
                    .build()
                    .unwrap();
                ChatCompletionRequestMessage::Tool(tool_message)
            },
        }
    }
}

/// Tool call function struct
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCallFunction {
    pub name: String,
    pub arguments: String,
}

/// Tool call struct
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCall {
    pub id: String,
    pub r#type: String,
    pub function: ToolCallFunction,
}

impl ToolCall {
    /// Convert to OpenAI API tool call format
    pub fn to_openai_tool_call(&self) -> ChatCompletionMessageToolCall {
        ChatCompletionMessageToolCall {
            id: self.id.clone(),
            r#type: ChatCompletionToolType::Function,
            function: FunctionCall {
                name: self.function.name.clone(),
                arguments: self.function.arguments.clone(),
            }
        }
    }
}

/// Tool result for file operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileResult {
    pub file: Option<String>,
    pub content: Option<String>,
    pub error: Option<String>,
}

/// Tool result for file search operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileInfo {
    pub path: String,
    pub is_directory: bool,
    pub size: Option<u64>,
}

/// Tool result for code search operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodeMatch {
    pub file: String,
    pub line: usize,
    pub content: String,
}

/// Tool result for calculation operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CalculationResult {
    pub expression: String,
    pub result: Option<f64>,
    pub error: Option<String>,
}

/// Define the agent type enum
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AgentType {
    ReAct,
    Reflexion,
}

impl std::str::FromStr for AgentType {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "react" => Ok(AgentType::ReAct),
            "reflexion" => Ok(AgentType::Reflexion),
            _ => Err(format!("Unknown agent type: {}", s)),
        }
    }
}

impl std::fmt::Display for AgentType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AgentType::ReAct => write!(f, "react"),
            AgentType::Reflexion => write!(f, "reflexion"),
        }
    }
}
