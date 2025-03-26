import { analyzeCodebase, saveResults } from './index';
import * as path from 'path';
import * as fs from 'fs';
import * as dotenv from 'dotenv';

// Load environment variables
dotenv.config();

/**
 * Simple test function to verify the TypeScript port works correctly
 */
async function runTest() {
  // Check if we have the necessary API keys
  if (!process.env.OPENAI_API_KEY && !process.env.GEMINI_API_KEY) {
    console.error('No API keys found. Please set OPENAI_API_KEY or GEMINI_API_KEY in your .env file.');
    process.exit(1);
  }

  // Create a simple test prompt
  const testPrompt = 'Provide a brief overview of the codebase structure.';
  const testPromptFile = path.join(__dirname, 'test-prompt.txt');
  
  // Write test prompt to file
  fs.writeFileSync(testPromptFile, testPrompt);
  
  // Directory to analyze (the TypeScript port itself)
  const directoryToAnalyze = path.resolve(__dirname, '..');
  
  console.log('Running test analysis with ReAct agent...');
  try {
    // Run analysis with ReAct agent
    const reactResult = await analyzeCodebase(
      directoryToAnalyze,
      testPromptFile,
      'gpt-4o-mini',
      'react'
    );
    
    // Save results
    const reactOutputPath = saveResults(reactResult, 'gpt-4o-mini', 'react');
    console.log(`ReAct agent test completed. Results saved to: ${reactOutputPath}`);
    
    // Run analysis with Reflexion agent
    console.log('Running test analysis with Reflexion agent...');
    const reflexionResult = await analyzeCodebase(
      directoryToAnalyze,
      testPromptFile,
      'gpt-4o-mini',
      'reflexion'
    );
    
    // Save results
    const reflexionOutputPath = saveResults(reflexionResult, 'gpt-4o-mini', 'reflexion');
    console.log(`Reflexion agent test completed. Results saved to: ${reflexionOutputPath}`);
    
    console.log('All tests completed successfully!');
  } catch (error) {
    console.error('Test failed:', error);
    process.exit(1);
  } finally {
    // Clean up test prompt file
    if (fs.existsSync(testPromptFile)) {
      fs.unlinkSync(testPromptFile);
    }
  }
}

// Run the test if this file is executed directly
if (require.main === module) {
  runTest();
}

export { runTest };
