package main

import (
	"fmt"
	"log"
	"os"

	"github.com/urfave/cli/v2"
)

func main() {
	app := &cli.App{
		Name:  "tech-writer-agent",
		Usage: "Analyze a codebase and generate documentation",
		Flags: []cli.Flag{
			&cli.StringFlag{
				Name:    "directory",
				Aliases: []string{"d"},
				Value:   ".",
				Usage:   "Directory to analyze",
			},
			&cli.StringFlag{
				Name:     "prompt",
				Aliases:  []string{"p"},
				Required: true,
				Usage:    "Path to prompt file",
			},
			&cli.StringFlag{
				Name:    "model",
				Aliases: []string{"m"},
				Value:   "gpt-4o-mini",
				Usage:   "Model to use",
			},
			&cli.StringFlag{
				Name:    "agent-type",
				Aliases: []string{"a"},
				Value:   "react",
				Usage:   "Agent type to use (react or reflexion)",
			},
			&cli.StringFlag{
				Name:  "base-url",
				Value: "",
				Usage: "Base URL for the OpenAI API",
			},
		},
		Action: func(c *cli.Context) error {
			directory := c.String("directory")
			promptFile := c.String("prompt")
			model := c.String("model")
			agentType := c.String("agent-type")
			baseURL := c.String("base-url")
			
			// Read the prompt file
			prompt, err := readPromptFile(promptFile)
			if err != nil {
				return fmt.Errorf("error reading prompt file: %v", err)
			}
			
			// Create the appropriate agent
			var agent Agent
			switch agentType {
			case "react":
				log.Println("Using ReAct agent")
				agent = NewReActAgent(model, baseURL)
			case "reflexion":
				log.Println("Using Reflexion agent with reflection capabilities")
				agent = NewReflexionAgent(model, baseURL)
			default:
				return fmt.Errorf("unknown agent type: %s", agentType)
			}
			
			// Run the agent
			outputFile, err := agent.Run(prompt, directory)
			if err != nil {
				return fmt.Errorf("error running code analysis: %v", err)
			}
			
			log.Printf("Analysis complete. Results saved to %s\n", outputFile)
			
			return nil
		},
	}
	
	err := app.Run(os.Args)
	if err != nil {
		log.Fatalf("Error: %v", err)
	}
}

// readPromptFile reads the prompt from a file
func readPromptFile(path string) (string, error) {
	// Check if the file exists
	if _, err := os.Stat(path); os.IsNotExist(err) {
		return "", fmt.Errorf("prompt file not found: %s", path)
	}
	
	// Read the file
	content, err := readFile(path)
	if err != nil {
		return "", err
	}
	
	return content, nil
}
