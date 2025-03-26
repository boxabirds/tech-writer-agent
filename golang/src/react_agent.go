package main

import (
	"fmt"
	"log"
)

// ReActAgent implements the ReAct pattern for codebase analysis
type ReActAgent struct {
	*BaseAgent
}

// NewReActAgent creates a new ReAct agent
func NewReActAgent(modelName string, baseURL string) *ReActAgent {
	baseAgent := NewBaseAgent(modelName, baseURL, ReActSystemPrompt)
	return &ReActAgent{
		BaseAgent: baseAgent,
	}
}

// Run executes the ReAct agent to analyze the codebase
func (r *ReActAgent) Run(prompt string, directory string) (string, error) {
	// Initialize memory with the system prompt and user prompt
	if err := r.InitializeMemory(prompt, directory); err != nil {
		return "", fmt.Errorf("error initializing memory: %v", err)
	}
	
	// Main loop
	maxSteps := 15
	for step := 1; step <= maxSteps; step++ {
		log.Printf("\n--- Step %d ---\n", step)
		
		// Call the LLM
		_, err := r.CallLLM()
		if err != nil {
			return "", fmt.Errorf("error in step %d: %v", step, err)
		}
		
		// Check if we have a final answer
		if r.FinalAnswer != "" {
			break
		}
		
		// Check if we have tool calls
		if len(r.Memory[len(r.Memory)-1].ToolCalls) == 0 {
			log.Println("No tool calls received")
			continue
		}
		
		// Execute each tool call
		for _, toolCall := range r.Memory[len(r.Memory)-1].ToolCalls {
			log.Printf("Executing tool: %s\n", toolCall.Function.Name)
			
			_, err := r.ExecuteTool(toolCall)
			if err != nil {
				return "", fmt.Errorf("error executing tool: %v", err)
			}
			
			// Check if final answer was set
			if r.FinalAnswer != "" {
				break
			}
		}
		
		// Break if we have a final answer
		if r.FinalAnswer != "" {
			break
		}
	}
	
	// Save the final answer
	if r.FinalAnswer == "" {
		return "", fmt.Errorf("no final answer after maximum steps")
	}
	
	outputFile, err := r.SaveFinalAnswer()
	if err != nil {
		return "", fmt.Errorf("error saving final answer: %v", err)
	}
	
	return outputFile, nil
}
