import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { Command } from 'commander';
import * as dotenv from 'dotenv';
import ignore from 'ignore';
import isBinaryPath from 'is-binary-path';
import OpenAI from 'openai';
import { promisify } from 'util';
import { prompts } from './prompts';

// Load environment variables
dotenv.config();

// Configure logging
const logger = {
  info: (message: string) => console.log(`INFO: ${message}`),
  warning: (message: string) => console.warn(`WARNING: ${message}`),
  error: (message: string) => console.error(`ERROR: ${message}`)
};

// Check for API keys
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

// Warn if neither API key is set
if (!GEMINI_API_KEY && !OPENAI_API_KEY) {
  logger.warning("Neither GEMINI_API_KEY nor OPENAI_API_KEY environment variables are set.");
  logger.warning("Please set at least one of these environment variables to use the respective API.");
  logger.warning("You can get a Gemini API key from https://aistudio.google.com");
  logger.warning("You can get an OpenAI API key from https://platform.openai.com");
}

// Define model providers
const GEMINI_MODELS = ["gemini-2.0-flash"];
const OPENAI_MODELS = ["gpt-4o-mini", "gpt-4o"];

/**
 * Get a PathSpec object from .gitignore in the specified directory.
 * 
 * @param directory - The directory containing .gitignore
 * @returns An ignore instance for matching against .gitignore patterns
 */
function getGitignoreSpec(directory: string) {
  const ig = ignore();
  
  // Try to read .gitignore file
  const gitignorePath = path.join(directory, ".gitignore");
  if (fs.existsSync(gitignorePath)) {
    try {
      const content = fs.readFileSync(gitignorePath, 'utf8');
      const ignorePatterns = content
        .split('\n')
        .map(line => line.trim())
        .filter(line => line && !line.startsWith('#'));
      
      ig.add(ignorePatterns);
      logger.info(`Added ${ignorePatterns.length} patterns from .gitignore`);
    } catch (e) {
      logger.error(`Error reading .gitignore: ${e}`);
    }
  }
  
  return ig;
}

/**
 * Read a prompt from an external file.
 * 
 * @param filePath - Path to the prompt file
 * @returns The content of the prompt file
 */
function readPromptFile(filePath: string): string {
  try {
    const path = filePath;
    if (!fs.existsSync(path)) {
      throw new Error(`Prompt file not found: ${filePath}`);
    }
    
    try {
      return fs.readFileSync(path, 'utf-8').trim();
    } catch (e) {
      try {
        return fs.readFileSync(path, 'latin1').trim();
      } catch (e) {
        throw new Error(`Error reading prompt file with latin-1 encoding: ${e}`);
      }
    }
  } catch (e) {
    throw new Error(`Error reading prompt file: ${e}`);
  }
}

// Tool functions
interface FileInfo {
  path: string;
  isDirectory: boolean;
  size?: number;
}

/**
 * Find files matching a pattern while respecting .gitignore.
 * 
 * @param directory - Directory to search in
 * @param pattern - File pattern to match (glob format)
 * @param respectGitignore - Whether to respect .gitignore patterns
 * @param includeHidden - Whether to include hidden files and directories
 * @param includeSubdirs - Whether to include files in subdirectories
 * @returns List of matching file paths
 */
function findAllMatchingFiles(
  directory: string,
  pattern: string = "*",
  respectGitignore: boolean = true,
  includeHidden: boolean = false,
  includeSubdirs: boolean = true
): FileInfo[] {
  try {
    const directoryPath = path.resolve(directory);
    if (!fs.existsSync(directoryPath)) {
      logger.warning(`Directory not found: ${directory}`);
      return [];
    }
    
    // Get gitignore spec if needed
    const ig = respectGitignore ? getGitignoreSpec(directoryPath) : null;
    
    const result: FileInfo[] = [];
    
    // Function to recursively search directories
    function searchDirectory(currentPath: string, isRoot: boolean = false) {
      const entries = fs.readdirSync(currentPath, { withFileTypes: true });
      
      for (const entry of entries) {
        const entryPath = path.join(currentPath, entry.name);
        
        // Skip hidden files if not explicitly included
        if (!includeHidden && entry.name.startsWith('.') && !isRoot) {
          continue;
        }
        
        // Skip if should be ignored
        if (respectGitignore && ig) {
          const relPath = path.relative(directoryPath, entryPath);
          if (ig.ignores(relPath)) {
            continue;
          }
        }
        
        if (entry.isDirectory()) {
          if (includeSubdirs) {
            searchDirectory(entryPath);
          }
        } else if (entry.isFile()) {
          // Simple pattern matching (can be enhanced with micromatch or similar)
          if (pattern === "*" || entry.name.includes(pattern) || entryPath.includes(pattern)) {
            const stats = fs.statSync(entryPath);
            result.push({
              path: entryPath,
              isDirectory: false,
              size: stats.size
            });
          }
        }
      }
    }
    
    searchDirectory(directoryPath, true);
    return result;
  } catch (e) {
    logger.error(`Error accessing files: ${e}`);
    return [];
  }
}

interface FileResult {
  file?: string;
  content?: string;
  error?: string;
}

/**
 * Read the contents of a file.
 * 
 * @param filePath - Path to the file to read
 * @returns Object containing the file path and content or an error
 */
function readFile(filePath: string): FileResult {
  try {
    const path = filePath;
    if (!fs.existsSync(path)) {
      return { error: `File not found: ${filePath}` };
    }
    
    if (isBinaryPath(filePath)) {
      return { error: `Cannot read binary file: ${filePath}` };
    }
    
    const content = fs.readFileSync(path, 'utf-8');
    
    return {
      file: filePath,
      content
    };
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === 'ENOENT') {
      return { error: `File not found: ${filePath}` };
    } else if (e instanceof SyntaxError) {
      return { error: `Cannot decode file as UTF-8: ${filePath}` };
    } else if ((e as NodeJS.ErrnoException).code === 'EACCES') {
      return { error: `Permission denied when reading file: ${filePath}` };
    } else {
      return { error: `Unexpected error reading file: ${e}` };
    }
  }
}

interface CalculationResult {
  expression: string;
  result?: number;
  error?: string;
}

/**
 * Evaluate a mathematical expression and return the result.
 * 
 * @param expression - Mathematical expression to evaluate
 * @returns Object containing the expression and its result or an error
 */
function calculate(expression: string): CalculationResult {
  try {
    // This is a simplified version - in production code you'd want to use
    // a proper math expression evaluator library with security features
    const sanitizedExpression = expression.replace(/[^0-9+\-*/().]/g, '');
    
    // Use Function constructor instead of eval for slightly better security
    // Still not recommended for production without proper sandboxing
    const result = Function(`"use strict"; return (${sanitizedExpression})`)();
    
    return {
      expression,
      result
    };
  } catch (e) {
    return {
      expression,
      error: `Error evaluating expression: ${e}`
    };
  }
}

// Dictionary mapping tool names to their functions
const TOOLS = {
  find_all_matching_files: findAllMatchingFiles,
  read_file: readFile,
  calculate: calculate
};

// Type definitions for OpenAI API
type Role = 'system' | 'user' | 'assistant' | 'tool';

interface Message {
  role: Role;
  content: string;
  tool_call_id?: string;
  name?: string;
}

interface ToolCall {
  id: string;
  type: string;
  function: {
    name: string;
    arguments: string;
  };
}

interface AssistantMessage {
  role: 'assistant';
  content: string | null;
  tool_calls?: ToolCall[];
}

/**
 * Abstract base class for codebase analysis agents.
 */
abstract class TechWriterAgent {
  protected model_name: string;
  protected base_url: string | null;
  protected memory: Message[];
  protected final_answer: string | null;
  protected system_prompt: string | null;
  protected client: OpenAI;
  
  constructor(model_name: string = "gpt-4o-mini", base_url: string | null = null) {
    this.model_name = model_name;
    this.base_url = base_url;
    this.memory = [];
    this.final_answer = null;
    this.system_prompt = null; // To be defined by subclasses
    
    // Initialize OpenAI client
    this.client = new OpenAI({
      apiKey: OPENAI_API_KEY as string,
      baseURL: base_url || undefined
    });
  }
  
  /**
   * Create tool definitions from a dictionary of functions.
   * 
   * @param tools_dict - Dictionary mapping tool names to functions
   * @returns List of tool definitions formatted for the OpenAI API
   */
  protected createOpenaiToolDefinitions(tools_dict: Record<string, Function>): any[] {
    const tools = [];
    
    for (const [name, func] of Object.entries(tools_dict)) {
      // Get function description from comments
      const funcStr = func.toString();
      const docComment = funcStr.match(/\/\*\*([\s\S]*?)\*\//);
      const description = docComment 
        ? docComment[1].replace(/\s*\*\s*/g, ' ').trim()
        : `Function ${name}`;
      
      // Extract parameter info
      const paramMatches = funcStr.match(/\(([^)]*)\)/);
      const params = paramMatches ? paramMatches[1].split(',') : [];
      
      // Build parameters object
      const parameters: any = {
        type: "object",
        properties: {},
        required: []
      };
      
      // Process each parameter
      for (const param of params) {
        if (!param.trim()) continue;
        
        // Extract parameter name and default value
        const [paramName, defaultValue] = param.split('=').map(p => p.trim());
        const cleanParamName = paramName.replace(/^.*?\s*:\s*.*$/, '').trim();
        
        if (cleanParamName === 'this') continue; // Skip 'this' parameter
        
        // Determine parameter type
        let paramType = "string";
        if (paramName.includes(': number') || paramName.includes(': boolean')) {
          paramType = paramName.includes(': number') ? "number" : "boolean";
        } else if (paramName.includes(': string')) {
          paramType = "string";
        } else if (paramName.includes('[]')) {
          paramType = "array";
        }
        
        // Extract parameter description from comments
        const paramPattern = new RegExp(`@param\\s+${cleanParamName}\\s+-\\s+([^\\n]+)`, 'i');
        const paramDescMatch = funcStr.match(paramPattern);
        const paramDesc = paramDescMatch ? paramDescMatch[1].trim() : '';
        
        // Add parameter to schema
        parameters.properties[cleanParamName] = {
          type: paramType,
          description: paramDesc
        };
        
        // Mark required parameters
        if (defaultValue === undefined) {
          parameters.required.push(cleanParamName);
        }
      }
      
      // Create tool definition
      const tool_def = {
        type: "function",
        function: {
          name,
          description,
          parameters
        }
      };
      
      tools.push(tool_def);
    }
    
    return tools;
  }
  
  /**
   * Initialize the agent's memory with the prompt and directory.
   * 
   * @param prompt - The analysis prompt
   * @param directory - The directory containing the codebase to analyze
   */
  protected initializeMemory(prompt: string, directory: string): void {
    if (!this.system_prompt) {
      throw new Error("System prompt must be defined by subclasses");
    }
    
    this.memory = [
      { role: "system", content: this.system_prompt },
      { role: "user", content: `Base directory: ${directory}\n\n${prompt}` }
    ];
    this.final_answer = null;
  }
  
  /**
   * Call the LLM with the current memory and tools.
   * 
   * @returns The assistant's message
   */
  protected async callLLM(): Promise<AssistantMessage> {
    try {
      const response = await this.client.chat.completions.create({
        model: this.model_name,
        messages: this.memory as any,
        tools: this.createOpenaiToolDefinitions(TOOLS),
        temperature: 0
      });
      
      return response.choices[0].message as AssistantMessage;
    } catch (e) {
      const error_msg = `Error calling API: ${e}`;
      logger.error(error_msg);
      throw new Error(error_msg);
    }
  }
  
  /**
   * Check if the LLM result is a final answer or a tool call.
   * 
   * @param assistant_message - The message from the assistant
   * @returns Tuple containing the result type and data
   */
  protected checkLLMResult(assistant_message: AssistantMessage): [string, string | ToolCall[]] {
    this.memory.push(assistant_message as Message);
    
    if (assistant_message.tool_calls && assistant_message.tool_calls.length > 0) {
      return ["tool_calls", assistant_message.tool_calls];
    } else {
      return ["final_answer", assistant_message.content || ""];
    }
  }
  
  /**
   * Execute a tool call and return the result.
   * 
   * @param tool_call - The tool call object from the LLM
   * @returns The result of the tool execution as a string
   */
  protected executeTool(tool_call: ToolCall): string {
    const tool_name = tool_call.function.name;
    
    if (!(tool_name in TOOLS)) {
      return `Error: Unknown tool ${tool_name}`;
    }
    
    try {
      // Parse the arguments
      const args = JSON.parse(tool_call.function.arguments);
      
      // Call the tool function
      const result = (TOOLS as any)[tool_name](...Object.values(args));
      
      // Convert result to JSON string
      return JSON.stringify(result, null, 2);
    } catch (e) {
      if (e instanceof SyntaxError) {
        return `Error: Invalid JSON in tool arguments: ${e}`;
      } else if (e instanceof TypeError) {
        return `Error: Invalid argument types: ${e}`;
      } else {
        return `Error executing tool ${tool_name}: ${e}`;
      }
    }
  }
  
  /**
   * Run the agent to analyze a codebase.
   * 
   * This method must be implemented by subclasses.
   * 
   * @param prompt - The analysis prompt
   * @param directory - The directory containing the codebase to analyze
   * @returns The analysis result
   */
  abstract run(prompt: string, directory: string): Promise<string>;
}

/**
 * Agent that uses the ReAct pattern for codebase analysis.
 */
class ReActAgent extends TechWriterAgent {
  constructor(model_name: string = "gpt-4o-mini", base_url: string | null = null) {
    super(model_name, base_url);
    const REACT_SYSTEM_PROMPT = `${prompts.ROLE_AND_TASK}\n\n${prompts.GENERAL_ANALYSIS_GUIDELINES}\n\n${prompts.INPUT_PROCESSING_GUIDELINES}\n\n${prompts.CODE_ANALYSIS_STRATEGIES}\n\n${prompts.REACT_PLANNING_STRATEGY}\n\n${prompts.QUALITY_REQUIREMENTS}`;
    this.system_prompt = REACT_SYSTEM_PROMPT;
  }
  
  /**
   * Run the agent to analyze a codebase using the ReAct pattern.
   * 
   * @param prompt - The analysis prompt
   * @param directory - The directory containing the codebase to analyze
   * @returns The analysis result
   */
  async run(prompt: string, directory: string): Promise<string> {
    this.initializeMemory(prompt, directory);
    const max_steps = 15;
    
    for (let step = 0; step < max_steps; step++) {
      logger.info(`\n--- Step ${step + 1} ---`);
      
      // Call the LLM
      const assistant_message = await this.callLLM();
      
      // Check the result
      const [result_type, result_data] = this.checkLLMResult(assistant_message);
      
      if (result_type === "final_answer") {
        this.final_answer = result_data as string;
        break;
      } else if (result_type === "tool_calls") {
        // Execute each tool call
        for (const tool_call of result_data as ToolCall[]) {
          // Execute the tool
          const observation = this.executeTool(tool_call);
          
          // Add the observation to memory
          this.memory.push({
            role: "tool",
            tool_call_id: tool_call.id,
            name: tool_call.function.name,
            content: observation
          });
        }
      }
      
      logger.info(`Memory length: ${this.memory.length} messages`);
    }
    
    if (this.final_answer === null) {
      this.final_answer = "Failed to complete the analysis within the step limit.";
    }
    
    return this.final_answer;
  }
}

/**
 * Agent that uses the Reflexion pattern for codebase analysis.
 */
class ReflexionAgent extends TechWriterAgent {
  private memory_restoration_needed: boolean = false;
  private original_system_message: Message | null = null;
  
  constructor(model_name: string = "gpt-4o-mini", base_url: string | null = null) {
    super(model_name, base_url);
    const REFLEXION_SYSTEM_PROMPT = `${prompts.ROLE_AND_TASK}\n\n${prompts.GENERAL_ANALYSIS_GUIDELINES}\n\n${prompts.INPUT_PROCESSING_GUIDELINES}\n\n${prompts.CODE_ANALYSIS_STRATEGIES}\n\n${prompts.REFLEXION_PLANNING_STRATEGY}\n\n${prompts.QUALITY_REQUIREMENTS}`;
    this.system_prompt = REFLEXION_SYSTEM_PROMPT;
  }
  
  /**
   * Run the agent to analyze a codebase with reflection.
   * 
   * @param prompt - The analysis prompt
   * @param directory - The directory containing the codebase to analyze
   * @returns The analysis result
   */
  async run(prompt: string, directory: string): Promise<string> {
    this.initializeMemory(prompt, directory);
    const max_steps = 15;
    let step_count = 0;
    
    while (step_count < max_steps) {
      step_count++;
      logger.info(`\n--- Step ${step_count} ---`);
      
      try {
        // Call the LLM
        const assistant_message = await this.callLLM();
        
        // Check the result
        const [result_type, result_data] = this.checkLLMResult(assistant_message);
        
        if (result_type === "final_answer") {
          this.final_answer = result_data as string;
          break;
        } else if (result_type === "tool_calls") {
          // Execute each tool call and add to memory
          for (const tool_call of result_data as ToolCall[]) {
            // Execute the tool
            const observation = this.executeTool(tool_call);
            
            // Add the observation to memory
            this.memory.push({
              role: "tool",
              tool_call_id: tool_call.id,
              name: tool_call.function.name,
              content: observation
            });
          }
          
          // Temporarily modify the system prompt to include a reflection instruction
          const reflection_instruction = "\n\nBefore responding, reflect on your previous actions. Were they effective? How can you improve your approach? Incorporate these reflections into your response.";
          
          // Find the system message in memory and update it
          for (let i = 0; i < this.memory.length; i++) {
            if (this.memory[i].role === "system") {
              // Store original system message
              this.original_system_message = { ...this.memory[i] };
              // Update with reflection instruction
              this.memory[i].content += reflection_instruction;
              break;
            }
          }
          
          // Schedule restoration for next iteration
          if (step_count + 1 < max_steps) {
            this.memory_restoration_needed = true;
          }
        }
      } catch (e) {
        logger.error(`Unexpected error: ${e}`);
        this.final_answer = `Error running code analysis: ${e}`;
        break;
      }
      
      // Check if we need to restore the system message
      if (this.memory_restoration_needed && this.original_system_message) {
        // Restore original system message
        for (let i = 0; i < this.memory.length; i++) {
          if (this.memory[i].role === "system") {
            this.memory[i] = this.original_system_message;
            break;
          }
        }
        this.memory_restoration_needed = false;
      }
      
      logger.info(`Memory length: ${this.memory.length} messages`);
    }
    
    if (this.final_answer === null) {
      this.final_answer = "Failed to complete the analysis within the step limit.";
    }
    
    return this.final_answer;
  }
}

/**
 * Get command line arguments.
 * 
 * @returns The parsed command line arguments
 */
function getCommandLineArgs() {
  const program = new Command();
  
  program
    .description("Analyse a codebase using an LLM agent.")
    .argument("<directory>", "Directory containing the codebase to analyse")
    .argument("<prompt_file>", "Path to a file containing the analysis prompt")
    .option("--model <model>", "Model to use for analysis", OPENAI_MODELS[0])
    .option("--base-url <url>", "Base URL for the API")
    .option("--agent-type <type>", "Type of agent to use for analysis", "react")
    .parse(process.argv);
  
  const options = program.opts();
  const [directory, promptFile] = program.args;
  
  // Define available models based on which API keys are set
  const availableModels: string[] = [];
  if (OPENAI_API_KEY) {
    availableModels.push(...OPENAI_MODELS);
  }
  if (GEMINI_API_KEY) {
    availableModels.push(...GEMINI_MODELS);
  }
  
  // Validate that we have a model available
  if (availableModels.length === 0) {
    console.error("No API keys set. Please set OPENAI_API_KEY or GEMINI_API_KEY environment variables.");
    process.exit(1);
  }
  
  // Validate agent type
  if (options.agentType !== "react" && options.agentType !== "reflexion") {
    console.error("Invalid agent type. Must be 'react' or 'reflexion'.");
    process.exit(1);
  }
  
  return {
    directory,
    promptFile,
    model: options.model || availableModels[0],
    baseUrl: options.baseUrl,
    agentType: options.agentType
  };
}

/**
 * Analyze a codebase using the specified agent type with a prompt from an external file.
 * 
 * @param directoryPath - Directory containing the codebase to analyze
 * @param promptFilePath - Path to a file containing the analysis prompt
 * @param modelName - Model to use for analysis
 * @param agentType - Type of agent to use for analysis
 * @param baseUrl - Base URL for the API
 * @returns The analysis result
 */
async function analyzeCodebase(
  directoryPath: string,
  promptFilePath: string,
  modelName: string,
  agentType: string = "react",
  baseUrl: string | null = null
): Promise<string> {
  try {
    const directory = path.resolve(directoryPath);
    if (!fs.existsSync(directory)) {
      throw new Error(`Directory not found: ${directoryPath}`);
    }
    
    // Read the prompt
    const prompt = readPromptFile(promptFilePath);
    
    // Set appropriate base URL based on the model
    if (baseUrl === null) {
      if (GEMINI_MODELS.includes(modelName)) {
        baseUrl = "https://generativelanguage.googleapis.com/v1beta/openai/";
      } else {
        baseUrl = null; // Use default OpenAI base URL for OpenAI models
      }
    }
    
    // Create and run the agent based on agentType
    let agent: TechWriterAgent;
    if (agentType === "reflexion") {
      agent = new ReflexionAgent(modelName, baseUrl);
      logger.info("Using Reflexion agent with reflection capabilities");
    } else {
      agent = new ReActAgent(modelName, baseUrl);
      logger.info("Using standard ReAct agent");
    }
    
    const result = await agent.run(prompt, directory);
    
    return result;
  } catch (e) {
    logger.error(`Error: ${e}`);
    return `Error running code analysis: ${e}`;
  }
}

/**
 * Save analysis results to a timestamped Markdown file in the output directory.
 * 
 * @param analysisResult - The analysis text to save
 * @param modelName - The name of the model used for analysis
 * @param agentType - The type of agent used (react or reflexion)
 * @returns Path to the saved file
 */
function saveResults(
  analysisResult: string,
  modelName: string,
  agentType: string
): string {
  // Create output directory if it doesn't exist
  const outputDir = path.join(process.cwd(), "output");
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }
  
  // Generate timestamp for filename
  const timestamp = new Date().toISOString().replace(/[:.]/g, '').slice(0, 15);
  const outputFilename = `${timestamp}-${agentType}-${modelName}.md`;
  const outputPath = path.join(outputDir, outputFilename);
  
  // Save results to markdown file
  try {
    fs.writeFileSync(outputPath, analysisResult, 'utf-8');
    logger.info(`Analysis complete. Results saved to ${outputPath}`);
    return outputPath;
  } catch (e) {
    logger.error(`Error saving results: ${e}`);
    throw new Error(`Failed to save results: ${e}`);
  }
}

/**
 * Main function to run the application.
 */
async function main() {
  try {
    const args = getCommandLineArgs();
    const analysisResult = await analyzeCodebase(
      args.directory,
      args.promptFile,
      args.model,
      args.agentType,
      args.baseUrl
    );
    saveResults(analysisResult, args.model, args.agentType);
  } catch (e) {
    logger.error(`Error: ${e}`);
    process.exit(1);
  }
}

// Run the main function if this file is executed directly
if (require.main === module) {
  main();
}

export {
  TechWriterAgent,
  ReActAgent,
  ReflexionAgent,
  analyzeCodebase,
  saveResults
};
