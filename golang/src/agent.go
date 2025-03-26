package main

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/sashabaranov/go-openai"
)

// Message represents a message in the conversation
type Message struct {
	Role    string                 `json:"role"`
	Content string                 `json:"content,omitempty"`
	ToolCalls []openai.ToolCall    `json:"tool_calls,omitempty"`
	ToolCallID string              `json:"tool_call_id,omitempty"`
	Name    string                 `json:"name,omitempty"`
}

// Agent defines the interface for all agents
type Agent interface {
	Run(prompt string, directory string) (string, error)
	InitializeMemory(prompt string, directory string) error
	CallLLM() (*openai.ChatCompletionResponse, error)
	ExecuteTool(toolCall openai.ToolCall) (string, error)
	CreateOpenAIToolDefinitions() []openai.Tool
}

// BaseAgent implements common functionality for all agents
type BaseAgent struct {
	ModelName    string
	BaseURL      string
	Memory       []Message
	FinalAnswer  string
	SystemPrompt string
	Client       *openai.Client
	Directory    string
}

// NewBaseAgent creates a new base agent
func NewBaseAgent(modelName string, baseURL string, systemPrompt string) *BaseAgent {
	config := openai.DefaultConfig(getEnv("OPENAI_API_KEY", ""))
	if baseURL != "" {
		config.BaseURL = baseURL
	}
	
	client := openai.NewClientWithConfig(config)
	
	return &BaseAgent{
		ModelName:    modelName,
		BaseURL:      baseURL,
		Memory:       []Message{},
		FinalAnswer:  "",
		SystemPrompt: systemPrompt,
		Client:       client,
	}
}

// InitializeMemory initializes the agent's memory with the system prompt and user prompt
func (a *BaseAgent) InitializeMemory(prompt string, directory string) error {
	a.Directory = directory
	a.Memory = []Message{
		{
			Role:    "system",
			Content: a.SystemPrompt,
		},
		{
			Role:    "user",
			Content: prompt,
		},
	}
	return nil
}

// CallLLM sends the current memory to the LLM and gets a response
func (a *BaseAgent) CallLLM() (*openai.ChatCompletionResponse, error) {
	messages := []openai.ChatCompletionMessage{}
	
	for _, msg := range a.Memory {
		chatMsg := openai.ChatCompletionMessage{
			Role:    msg.Role,
			Content: msg.Content,
		}
		
		if len(msg.ToolCalls) > 0 {
			chatMsg.ToolCalls = msg.ToolCalls
		}
		
		if msg.ToolCallID != "" {
			chatMsg.ToolCallID = msg.ToolCallID
			chatMsg.Name = msg.Name
		}
		
		messages = append(messages, chatMsg)
	}
	
	tools := a.CreateOpenAIToolDefinitions()
	
	resp, err := a.Client.CreateChatCompletion(
		context.Background(),
		openai.ChatCompletionRequest{
			Model:    a.ModelName,
			Messages: messages,
			Tools:    tools,
		},
	)
	
	if err != nil {
		return nil, fmt.Errorf("error calling LLM: %v", err)
	}
	
	// Add the assistant's response to memory
	assistantMsg := Message{
		Role:    "assistant",
		Content: resp.Choices[0].Message.Content,
	}
	
	if len(resp.Choices[0].Message.ToolCalls) > 0 {
		assistantMsg.ToolCalls = resp.Choices[0].Message.ToolCalls
	}
	
	a.Memory = append(a.Memory, assistantMsg)
	
	return &resp, nil
}

// ExecuteTool executes a tool based on the tool call
func (a *BaseAgent) ExecuteTool(toolCall openai.ToolCall) (string, error) {
	var args map[string]interface{}
	if err := json.Unmarshal([]byte(toolCall.Function.Arguments), &args); err != nil {
		return "", fmt.Errorf("error parsing tool arguments: %v", err)
	}
	
	var result string
	
	switch toolCall.Function.Name {
	case "list_files":
		path, _ := args["path"].(string)
		if path == "" {
			path = a.Directory
		}
		files, err := listFiles(path)
		if err != nil {
			return "", err
		}
		resultBytes, err := json.Marshal(files)
		if err != nil {
			return "", err
		}
		result = string(resultBytes)
		
	case "read_file":
		path, _ := args["path"].(string)
		content, err := readFile(path)
		if err != nil {
			return "", err
		}
		result = content
		
	case "search_code":
		query, _ := args["query"].(string)
		filePattern, _ := args["file_pattern"].(string)
		matches, err := searchCode(a.Directory, query, filePattern)
		if err != nil {
			return "", err
		}
		resultBytes, err := json.Marshal(matches)
		if err != nil {
			return "", err
		}
		result = string(resultBytes)
		
	case "final_answer":
		answer, _ := args["answer"].(string)
		a.FinalAnswer = answer
		result = "Final answer recorded."
		
	default:
		return "", fmt.Errorf("unknown tool: %s", toolCall.Function.Name)
	}
	
	// Add the tool response to memory
	toolResponseMsg := Message{
		Role:       "tool",
		Content:    result,
		ToolCallID: toolCall.ID,
		Name:       toolCall.Function.Name,
	}
	
	a.Memory = append(a.Memory, toolResponseMsg)
	
	return result, nil
}

// CreateOpenAIToolDefinitions creates the tool definitions for the OpenAI API
func (a *BaseAgent) CreateOpenAIToolDefinitions() []openai.Tool {
	return []openai.Tool{
		{
			Type: "function",
			Function: &openai.FunctionDefinition{
				Name:        "list_files",
				Description: "Lists files in the codebase, respecting .gitignore patterns",
				Parameters: map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"path": map[string]interface{}{
							"type":        "string",
							"description": "The directory path to list files from",
						},
					},
					"required": []string{},
				},
			},
		},
		{
			Type: "function",
			Function: &openai.FunctionDefinition{
				Name:        "read_file",
				Description: "Reads the content of a file",
				Parameters: map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"path": map[string]interface{}{
							"type":        "string",
							"description": "The path to the file to read",
						},
					},
					"required": []string{"path"},
				},
			},
		},
		{
			Type: "function",
			Function: &openai.FunctionDefinition{
				Name:        "search_code",
				Description: "Searches for patterns in the codebase",
				Parameters: map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"query": map[string]interface{}{
							"type":        "string",
							"description": "The pattern to search for",
						},
						"file_pattern": map[string]interface{}{
							"type":        "string",
							"description": "A pattern to filter files (e.g., \"*.go\")",
						},
					},
					"required": []string{"query"},
				},
			},
		},
		{
			Type: "function",
			Function: &openai.FunctionDefinition{
				Name:        "final_answer",
				Description: "Submits your final documentation",
				Parameters: map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"answer": map[string]interface{}{
							"type":        "string",
							"description": "Your final documentation in markdown format",
						},
					},
					"required": []string{"answer"},
				},
			},
		},
	}
}

// SaveFinalAnswer saves the final answer to a file
func (a *BaseAgent) SaveFinalAnswer() (string, error) {
	if a.FinalAnswer == "" {
		return "", fmt.Errorf("no final answer to save")
	}
	
	timestamp := time.Now().Format("2006-01-02T1504")
	filename := fmt.Sprintf("output/%s-%s-%s.md", timestamp, getAgentTypeFromSystemPrompt(a.SystemPrompt), a.ModelName)
	
	if err := writeFile(filename, a.FinalAnswer); err != nil {
		return "", fmt.Errorf("error saving final answer: %v", err)
	}
	
	return filename, nil
}

// Helper function to determine agent type from system prompt
func getAgentTypeFromSystemPrompt(systemPrompt string) string {
	if systemPrompt == ReActSystemPrompt {
		return "react"
	} else if systemPrompt == ReflexionSystemPrompt {
		return "reflexion"
	}
	return "unknown"
}
