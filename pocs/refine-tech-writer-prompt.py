#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
import json
import logging
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PromptRefiner:
    def __init__(self, prompt_path: str, source_code_path: str, model: str):
        self.prompt_path = Path(prompt_path)
        self.source_code_path = Path(source_code_path)
        self.model = model
        self.prompt_stem = self.prompt_path.stem
        self.source_code_name = self.source_code_path.name
        
        # Create timestamp-based output directory
        timestamp = datetime.now().strftime("%y%m%d-%H%M%S")
        self.output_dir = Path(f"{timestamp}-{self.prompt_stem}-{self.source_code_name}")
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info(f"Created output directory: {self.output_dir}")

    def copy_prompt(self, version: int) -> Path:
        """Copy the prompt file to the output directory with version number."""
        new_prompt = self.output_dir / f"prompt-v{version}.txt"
        shutil.copy2(self.prompt_path, new_prompt)
        return new_prompt

    def run_tech_writer(self, prompt_file: Path, version: int) -> Path:
        """Run the tech writer agent and return the output file path."""
        output_file = self.output_dir / f"output-v{version}.md"
        cmd = [
            "source", ".venv/bin/activate", "&&",
            "python", "tech-writer-from-scratch-react-only.py",
            str(self.source_code_path),
            str(prompt_file),
            "--model", self.model,
            "--output_type", "output"
        ]
        
        logger.info(f"Running tech writer agent (version {version})...")
        result = subprocess.run(" ".join(cmd), shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            error_msg = result.stderr
            logger.error(f"Tech writer agent failed: {error_msg}")
            
            # Handle specific API errors
            if result.returncode == 2:
                logger.error("API quota exceeded. Stopping refinement process.")
                sys.exit(2)
            elif result.returncode == 3:
                logger.error("Rate limit exceeded. Stopping refinement process.")
                sys.exit(3)
            elif result.returncode == 4:
                logger.error("Authentication error. Stopping refinement process.")
                sys.exit(4)
            else:
                raise RuntimeError("Tech writer agent failed")
            
        # Find the most recent output file for this model
        output_pattern = f"output/*-react-{self.model}-output.md"
        output_files = sorted(Path().glob(output_pattern), key=lambda x: x.stat().st_mtime)
        if output_files:
            shutil.move(output_files[-1], output_file)
            logger.info(f"Moved output file to {output_file}")
        else:
            raise FileNotFoundError(f"No output file found matching {output_pattern}")
            
        return output_file

    def assess_output(self, output_file: Path, version: int) -> Path:
        """Use GPT-4 to assess the output and generate improvement suggestions."""
        assessment_file = self.output_dir / f"assessment-v{version}.md"
        
        # Read the output content
        with open(output_file, 'r') as f:
            output_content = f.read()
            
        # Read previous version's output if it exists
        prev_output_content = ""
        if version > 1:
            prev_output_file = self.output_dir / f"output-v{version-1}.md"
            if prev_output_file.exists():
                with open(prev_output_file, 'r') as f:
                    prev_output_content = f.read()
            
        # Create assessment prompt
        assessment_prompt = f"""Please analyze this technical writing output and compare it with the previous version (if available) to evaluate improvements and identify areas for further enhancement.

Current version output:
{output_content}

{f'Previous version output:\n{prev_output_content}' if prev_output_content else 'No previous version available for comparison.'}

Please provide:
1. Key improvements over the previous version (if applicable)
2. Areas that still need more evidence from the codebase
3. Specific suggestions for improving the prompt to get better results
4. Concrete examples of where the output could be more specific or evidence-based

Focus on:
- Evidence from the codebase: Are there more opportunities to cite specific code, configurations, or patterns?
- Clarity and organization: Has the structure improved? Are sections more logically organized?
- Completeness: Are there important aspects of the codebase that are still not covered?
- Specificity: Are there areas where the output is still too generic or could be more specific?

Provide specific examples and suggestions rather than general observations."""
        
        # Save assessment prompt to temporary file
        temp_prompt = self.output_dir / f"assessment-prompt-v{version}.txt"
        with open(temp_prompt, 'w') as f:
            f.write(assessment_prompt)
            
        # Run GPT-4 assessment
        cmd = [
            "source", ".venv/bin/activate", "&&",
            "python", "tech-writer-from-scratch-react-only.py",
            str(self.source_code_path),
            str(temp_prompt),
            "--model", "gpt-4o",
            "--output_type", "assessment"
        ]
        
        logger.info(f"Running assessment (version {version})...")
        result = subprocess.run(" ".join(cmd), shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            error_msg = result.stderr
            logger.error(f"Assessment failed: {error_msg}")
            
            # Handle specific API errors
            if result.returncode == 2:
                logger.error("API quota exceeded. Stopping refinement process.")
                sys.exit(2)
            elif result.returncode == 3:
                logger.error("Rate limit exceeded. Stopping refinement process.")
                sys.exit(3)
            elif result.returncode == 4:
                logger.error("Authentication error. Stopping refinement process.")
                sys.exit(4)
            else:
                raise RuntimeError("Assessment failed")
            
        # Find the most recent assessment output
        assessment_pattern = f"output/*-react-gpt-4o-assessment.md"
        assessment_files = sorted(Path().glob(assessment_pattern), key=lambda x: x.stat().st_mtime)
        if assessment_files:
            shutil.move(assessment_files[-1], assessment_file)
            logger.info(f"Moved assessment file to {assessment_file}")
        else:
            raise FileNotFoundError(f"No assessment file found matching {assessment_pattern}")
            
        # Clean up temporary prompt
        temp_prompt.unlink()
        
        return assessment_file

    def refine_prompt(self, current_prompt: Path, assessment_file: Path, version: int) -> Path:
        """Create an improved version of the prompt based on the assessment."""
        new_prompt = self.output_dir / f"prompt-v{version+1}.txt"
        
        # Read current prompt and assessment
        with open(current_prompt, 'r') as f:
            current_content = f.read()
            logger.info(f"Current prompt ({current_prompt}) length: {len(current_content)} chars")
            
        with open(assessment_file, 'r') as f:
            assessment_content = f.read()
            logger.info(f"Assessment ({assessment_file}) length: {len(assessment_content)} chars")
            
        # Create refinement prompt
        refinement_prompt = f"""Based on this assessment of the current output, please create an improved version of the prompt that addresses the identified issues.

Current prompt:
{current_content}

Assessment:
{assessment_content}

Please provide an improved version of the prompt that:
1. Addresses the weaknesses identified in the assessment
2. Adds specific requirements for evidence from the codebase
3. Maintains the strengths of the current prompt
4. Includes clear examples of what constitutes good evidence

Provide only the improved prompt text, no additional commentary."""
        
        # Save refinement prompt to temporary file
        temp_prompt = self.output_dir / f"refinement-prompt-v{version}.txt"
        with open(temp_prompt, 'w') as f:
            f.write(refinement_prompt)
            logger.info(f"Created refinement prompt ({temp_prompt}) length: {len(refinement_prompt)} chars")
            
        # Run GPT-4 refinement
        cmd = [
            "source", ".venv/bin/activate", "&&",
            "python", "tech-writer-from-scratch-react-only.py",
            str(self.source_code_path),
            str(temp_prompt),
            "--model", "gpt-4o",
            "--output_type", "refinement"
        ]
        
        logger.info(f"Running prompt refinement (version {version})...")
        result = subprocess.run(" ".join(cmd), shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            error_msg = result.stderr
            logger.error(f"Prompt refinement failed: {error_msg}")
            
            # Handle specific API errors
            if result.returncode == 2:
                logger.error("API quota exceeded. Stopping refinement process.")
                sys.exit(2)
            elif result.returncode == 3:
                logger.error("Rate limit exceeded. Stopping refinement process.")
                sys.exit(3)
            elif result.returncode == 4:
                logger.error("Authentication error. Stopping refinement process.")
                sys.exit(4)
            else:
                raise RuntimeError("Prompt refinement failed")
            
        # Find the most recent refinement output
        refinement_pattern = f"output/*-react-gpt-4o-refinement.md"
        refinement_files = sorted(Path().glob(refinement_pattern), key=lambda x: x.stat().st_mtime)
        if refinement_files:
            # Read the refinement output and extract just the prompt text
            refinement_output = refinement_files[-1].read_text()
            logger.info(f"Refinement output length: {len(refinement_output)} chars")
            
            # Compare with current prompt
            if refinement_output.strip() == current_content.strip():
                logger.info("New prompt is identical to current prompt. Stopping refinement process.")
                # Create a copy of the current prompt as the new version
                shutil.copy(current_prompt, new_prompt)
                return new_prompt
                
            # Write the refinement output directly as the new prompt
            with open(new_prompt, 'w') as f:
                f.write(refinement_output)
            logger.info(f"Created new prompt ({new_prompt}) length: {len(refinement_output)} chars")
        else:
            raise FileNotFoundError(f"No refinement file found matching {refinement_pattern}")
            
        # Clean up temporary prompt
        temp_prompt.unlink()
        
        return new_prompt

    def create_final_assessment(self):
        """Create a final assessment comparing all versions."""
        final_assessment = self.output_dir / "final-assessment.md"
        
        # Read all outputs and assessments
        outputs = []
        assessments = []
        for i in range(1, 7):
            output_file = self.output_dir / f"output-v{i}.md"
            assessment_file = self.output_dir / f"assessment-v{i}.md"
            if output_file.exists() and assessment_file.exists():
                outputs.append(output_file.read_text())
                assessments.append(assessment_file.read_text())
        
        # Create final assessment prompt
        final_prompt = f"""Please analyze the progression of improvements across these versions of the technical writing output and assessment.

Version 1 (Original):
{outputs[0]}

Assessment of Version 1:
{assessments[0]}

Version {len(outputs)} (Final):
{outputs[-1]}

Assessment of Version {len(outputs)}:
{assessments[-1]}

Please provide a comprehensive analysis that:
1. Identifies key improvements from version 1 to version {len(outputs)}
2. Evaluates the effectiveness of the prompt refinement process
3. Highlights the most significant changes in output quality
4. Suggests any remaining areas for potential improvement
5. Provides recommendations for future prompt refinement processes

Focus on concrete, specific improvements rather than general observations."""
        
        # Save final assessment prompt to temporary file
        temp_prompt = self.output_dir / "final-assessment-prompt.txt"
        with open(temp_prompt, 'w') as f:
            f.write(final_prompt)
            
        # Run final assessment
        cmd = [
            "source", ".venv/bin/activate", "&&",
            "python", "tech-writer-from-scratch-react-only.py",
            str(self.source_code_path),
            str(temp_prompt),
            "--model", "gpt-4o-mini",
            "--output_type", "final-assessment"
        ]
        
        logger.info("Running final assessment...")
        result = subprocess.run(" ".join(cmd), shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            error_msg = result.stderr
            logger.error(f"Final assessment failed: {error_msg}")
            
            # Handle specific API errors
            if result.returncode == 2:
                logger.error("API quota exceeded. Stopping refinement process.")
                sys.exit(2)
            elif result.returncode == 3:
                logger.error("Rate limit exceeded. Stopping refinement process.")
                sys.exit(3)
            elif result.returncode == 4:
                logger.error("Authentication error. Stopping refinement process.")
                sys.exit(4)
            else:
                raise RuntimeError("Final assessment failed")
            
        # Find the most recent final assessment output
        final_pattern = f"output/*-react-gpt-4o-final-assessment.md"
        final_files = sorted(Path().glob(final_pattern), key=lambda x: x.stat().st_mtime)
        if final_files:
            shutil.move(final_files[-1], final_assessment)
            logger.info(f"Moved final assessment to {final_assessment}")
        else:
            raise FileNotFoundError(f"No final assessment file found matching {final_pattern}")
            
        # Clean up temporary prompt
        temp_prompt.unlink()

    def run_refinement_process(self):
        """Run the complete refinement process."""
        current_prompt = self.copy_prompt(1)
        
        for version in range(1, 7):
            logger.info(f"Starting version {version}...")
            
            # Run tech writer
            output_file = self.run_tech_writer(current_prompt, version)
            
            # Assess output
            assessment_file = self.assess_output(output_file, version)
            
            # Refine prompt for next version
            if version < 6:
                current_prompt = self.refine_prompt(current_prompt, assessment_file, version)
                
        # Create final assessment
        self.create_final_assessment()
        
        logger.info(f"Refinement process complete. Results in {self.output_dir}")

def main():
    if len(sys.argv) != 4:
        print("Usage: refine-tech-writer-prompt.py <prompt.txt> <source_code_path> <model>")
        sys.exit(1)
        
    prompt_path = sys.argv[1]
    source_code_path = sys.argv[2]
    model = sys.argv[3]
    
    refiner = PromptRefiner(prompt_path, source_code_path, model)
    refiner.run_refinement_process()

if __name__ == "__main__":
    main() 