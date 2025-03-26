package main

import (
	"fmt"
	"log"
)

// ReflexionAgent implements the Reflexion pattern for codebase analysis
type ReflexionAgent struct {
	*BaseAgent
	memoryRestorationNeeded bool
	originalSystemMessage   *Message
}

// NewReflexionAgent creates a new Reflexion agent
func NewReflexionAgent(modelName string, baseURL string) *ReflexionAgent {
	return &ReflexionAgent{
		BaseAgent:               NewBaseAgent(modelName, baseURL, ReflexionSystemPrompt),
		memoryRestorationNeeded: false,
		originalSystemMessage:   nil,
	}
}

// Run executes the Reflexion agent's analysis process
func (a *ReflexionAgent) Run(prompt string, directory string) (string, error) {
	if err := a.InitializeMemory(prompt, directory); err != nil {
		return "", fmt.Errorf("error initializing memory: %v", err)
	}

	maxSteps := 15
	for step := 1; step <= maxSteps; step++ {
		log.Printf("\n--- Step %d ---\n", step)
		
		// Check if we need to restore the system message
		if a.memoryRestorationNeeded && a.originalSystemMessage != nil {
			// Restore original system message
			for i := range a.Memory {
				if a.Memory[i].Role == "system" {
					a.Memory[i] = *a.originalSystemMessage
					break
				}
			}
			a.memoryRestorationNeeded = false
		}
		
		// Call the LLM
		_, err := a.CallLLM()
		if err != nil {
			return "", fmt.Errorf("error in step %d: %v", step, err)
		}
		
		// Check if we have a final answer
		if a.FinalAnswer != "" {
			log.Println("Final answer received")
			break
		}
		
		// Check if we have tool calls
		if len(a.Memory[len(a.Memory)-1].ToolCalls) == 0 {
			log.Println("No tool calls received")
			continue
		}
		
		// Execute each tool call
		for _, toolCall := range a.Memory[len(a.Memory)-1].ToolCalls {
			log.Printf("Executing tool: %s\n", toolCall.Function.Name)
			
			_, err := a.ExecuteTool(toolCall)
			if err != nil {
				return "", fmt.Errorf("error executing tool %s: %v", toolCall.Function.Name, err)
			}
			
			// Check if we have a final answer after executing the tool
			if a.FinalAnswer != "" && toolCall.Function.Name == "final_answer" {
				log.Println("Final answer received from tool execution")
				break
			}
		}
		
		// Check if we have a final answer after this step
		if a.FinalAnswer != "" {
			break
		}
		
		// Add reflection step after each iteration (except the last one)
		if step < maxSteps && a.FinalAnswer == "" {
			if err := a.AddReflection(); err != nil {
				return "", fmt.Errorf("error adding reflection: %v", err)
			}
			
			// Schedule restoration for next iteration
			if step+1 < maxSteps {
				a.memoryRestorationNeeded = true
			}
		}
		
		log.Printf("Memory length: %d messages\n", len(a.Memory))
	}
	
	// Save the final answer
	if a.FinalAnswer == "" {
		return "", fmt.Errorf("no final answer generated after maximum steps")
	}
	
	outputFile, err := a.SaveFinalAnswer()
	if err != nil {
		return "", fmt.Errorf("error saving final answer: %v", err)
	}
	
	log.Printf("Analysis complete. Results saved to %s\n", outputFile)
	
	return outputFile, nil
}

// AddReflection adds a reflection step to the agent's memory
func (a *ReflexionAgent) AddReflection() error {
	// Find the system message in memory and update it
	for i := range a.Memory {
		if a.Memory[i].Role == "system" {
			// Store original system message if not already stored
			if a.originalSystemMessage == nil {
				originalMsg := a.Memory[i]
				a.originalSystemMessage = &originalMsg
			}
			
			// Add reflection instruction to system message
			reflectionInstruction := "\n\nBefore responding, reflect on your previous actions. Were they effective? How can you improve your approach? Incorporate these reflections into your response."
			a.Memory[i].Content += reflectionInstruction
			break
		}
	}
	
	log.Println("Added reflection to memory")
	
	return nil
}
