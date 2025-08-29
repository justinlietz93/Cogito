#!/usr/bin/env python3

"""
orchestrator.py

Refined orchestrator that:
1) Asks for an initial user vision
2) Optionally does a Q&A for clarifications
3) Proceeds through the Breakthrough-Idea Walkthrough Framework:
   - Each step guides the LLM through a process for developing breakthrough ideas
   - Feeds back prior steps' outputs for context
   - Prompts the user to proceed, skip, or repeat
   - Can read/write files in the "some_project/" directory
4) Stores each step's output and passes it forward to keep context.

This system walks an LLM through creating a set of blueprints for a breakthrough idea
by following a carefully structured 8-stage framework designed to maximize novelty
while still producing actionable or implementable ideas.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List
import datetime

# Try to load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed. Environment variables must be set manually.")

from ai_clients import AIOrchestrator

class ProjectFile:
    def __init__(self, path: str, content: str):
        self.path = path
        self.content = content

def read_project_files(project_root: str) -> Dict[str, "ProjectFile"]:
    """
    Reads text files from project_root, ignoring .git or obvious binaries.
    Returns a dict: { "relative/path": ProjectFile(...) }
    """
    file_map = {}
    root = Path(project_root)
    if not root.is_dir():
        print(f"Warning: {project_root} is not a directory.")
        return file_map

    for p in root.rglob("*"):
        if p.is_file():
            # Use Path's methods to get platform-independent relative path
            rel_path = str(p.relative_to(root))
            # skip .git or some binaries
            if ".git" in rel_path:
                continue
            if p.suffix in [".png", ".jpg", ".exe", ".dll"]:
                continue
            try:
                content = p.read_text(encoding="utf-8")
                file_map[rel_path] = ProjectFile(rel_path, content)
            except Exception as e:
                print(f"Skipping {rel_path}: {e}")
    return file_map

def write_project_file(project_root: str, pf: ProjectFile):
    """
    Ensures the parent directory exists and writes updated content.
    Added robust error handling and extra debugging.
    """
    # Use pathlib for cross-platform path handling
    target = Path(project_root) / pf.path
    print(f"DEBUG: Attempting to write to {target}")
    
    try:
        # Create all parent directories
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"DEBUG: Ensured parent directory exists: {target.parent}")
        
        # Write the file
        target.write_text(pf.content, encoding="utf-8")
        print(f"DEBUG: Successfully wrote {len(pf.content)} characters to {target}")
        
        # Verify file exists
        if target.exists():
            print(f"DEBUG: File exists verification passed for {target}")
            print(f"DEBUG: File size: {target.stat().st_size} bytes")
        else:
            print(f"ERROR: File should exist but doesn't: {target}")
            
    except Exception as e:
        print(f"ERROR writing to {target}: {str(e)}")
        import traceback
        traceback.print_exc()

def parse_ai_response_and_apply(ai_text: str, file_map: Dict[str, ProjectFile]):
    """
    Looks for lines of the form:
      === File: path/to/file ===
      (some content)

    Then we store that content in file_map[path].
    If path not in file_map, we create a new entry (new file).
    Makes sure to normalize paths for cross-platform compatibility.
    """
    lines = ai_text.splitlines()
    current_file = None
    content_buffer: List[str] = []

    def commit_file():
        nonlocal current_file, content_buffer
        if current_file:
            # Normalize path separators for cross-platform compatibility
            normalized_path = current_file.replace('/', os.path.sep)
            if normalized_path not in file_map:
                # Create a new entry if it doesn't exist
                file_map[normalized_path] = ProjectFile(normalized_path, "")
            file_map[normalized_path].content = "\n".join(content_buffer)
            print(f"DEBUG: Processed file {normalized_path}")

    for line in lines:
        if line.startswith("=== File: "):
            # commit previous file
            commit_file()
            current_file = line.replace("=== File: ", "").strip()
            content_buffer = []
        else:
            # accumulate lines for this file
            content_buffer.append(line)

    # commit last file
    commit_file()

def main():
    # Platform check
    if sys.platform == 'win32':
        print("INFO: Running on Windows. Using platform-compatible path handling.")
        print("NOTE: When viewing file paths in the AI's response, paths may use forward slashes,")
        print("      but they will be converted to Windows backslashes when saving files.\n")
    
    # Check for auto-yes flag
    auto_yes = False
    args = sys.argv.copy()
    if '--auto-yes' in args:
        auto_yes = True
        args.remove('--auto-yes')
    elif '-y' in args:
        auto_yes = True
        args.remove('-y')
    
    if len(args) < 2:
        print("Usage: python orchestrator.py [--auto-yes|-y] <claude37sonnet|deepseekr1> [domain_challenge_description]")
        print("  --auto-yes, -y : Automatically answer 'yes' to all prompts")
        sys.exit(1)

    model_name = args[1].lower()
    orchestrator = AIOrchestrator(model_name)
    
    # Check if domain/challenge was provided as a command line argument
    user_vision = " ".join(args[2:]) if len(args) > 2 else ""

    # Step 0) Check for user_prompt.txt and offer to use it
    prompt_file_path = "user_prompt.txt"
    if not user_vision and os.path.exists(prompt_file_path):
        try:
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                file_content = f.read().strip()
            
            if file_content:
                print("\n=== FOUND USER_PROMPT.TXT ===")
                print("Preview of user_prompt.txt:")
                print("---")
                # Show first 200 chars with ellipsis if longer
                preview = file_content[:200] + ("..." if len(file_content) > 200 else "")
                print(preview)
                print("---")
                
                if auto_yes:
                    print("Auto-yes enabled: Using user_prompt.txt as domain/challenge.")
                    user_vision = file_content
                else:
                    use_file = input("Use this content as your domain/challenge? (y/n): ").strip().lower()
                    if use_file == 'y':
                        user_vision = file_content
                        print("Using user_prompt.txt as domain/challenge.")
        except Exception as e:
            print(f"Error reading user_prompt.txt: {e}")
    
    # Step 0) Ask user for project vision if not already set
    if not user_vision:
        print("=== INITIAL DOMAIN OR CHALLENGE ===")
        user_vision = input("Describe the domain or challenge you want breakthrough ideas for (a line or paragraph): ")

    # Step 0.5) Offer to ask follow-up questions
    if auto_yes:
        print("Auto-yes enabled: Skipping follow-up questions.")
        ask_q = 'n'
    else:
        ask_q = input("Should the AI ask follow-up questions about your domain/challenge? (y/n): ").strip().lower()
    
    if ask_q == 'y':
        conversation = [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI that clarifies the user's domain or challenge. "
                    "Ask short follow-up questions to fully understand the user's needs."
                )
            },
            {"role": "user", "content": user_vision},
        ]
        while True:
            # let AI ask a question
            question = orchestrator.client.run(conversation, max_tokens=20000)
            print("\nAI asks:\n", question)
            user_ans = input("Your answer (type 'done' to finish Q&A): ")
            if user_ans.strip().lower() == 'done':
                break
            conversation.append({"role": "assistant", "content": question})
            conversation.append({"role": "user", "content": user_ans})

        # Combine the conversation into user_vision
        user_vision += "\n\nAdditional Clarifications:\n" + "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in conversation if msg['role'] == 'user']
        )

    # Prepare workspace folder under syncretic_catalyst - use pathlib for cross-platform compatibility
    PROJECT_DIR = "src/syncretic_catalyst/workspaces/some_project"
    
    # Pre-check to ensure we can create and write to the directories
    try:
        print("PRE-CHECK: Verifying we can create and write to directories...")
        Path(PROJECT_DIR).mkdir(exist_ok=True)
        doc_dir = Path(PROJECT_DIR) / "doc"
        doc_dir.mkdir(exist_ok=True)
        
        # Try writing a test file
        test_file = doc_dir / "test_write.txt"
        test_file.write_text("Test write permission - " + str(datetime.datetime.now()), encoding="utf-8")
        if test_file.exists():
            print(f"PRE-CHECK: Successfully created test file at {test_file}")
            print(f"PRE-CHECK: Directory permissions OK for writing files")
        
        # Try reading the test file
        test_content = test_file.read_text(encoding="utf-8")
        print(f"PRE-CHECK: Successfully read test file content: '{test_content[:20]}...'")
        
    except Exception as e:
        print(f"ERROR in pre-check: {str(e)}")
        print("The program may not be able to write files. Please check permissions.")
        print("Continuing anyway, but be aware files might not be created properly.")
        import traceback
        traceback.print_exc()
    
    # Continue with normal initialization
    Path(PROJECT_DIR).mkdir(exist_ok=True)
    Path(PROJECT_DIR).joinpath("doc").mkdir(exist_ok=True)
    file_map = read_project_files(PROJECT_DIR)

    # We'll store step outputs to feed them as context into subsequent steps
    step_outputs = {}

    # Define our 8-stage Breakthrough-Idea Walkthrough Framework
    STEPS = [
        {
            "phase_name": "1) Context & Constraints Clarification",
            "system_prompt": (
                "You are a specialized systems architect and implementation expert. The user will describe a domain or challenge.\n"
                "Step 1: Provide an EXTENSIVE and DETAILED summary of the user's domain, goals, and constraints. Your output should be AT LEAST 1000-1500 WORDS in length to ensure comprehensive coverage.\n"
                "Additionally, collect any unusual references or lesser-known methods you can recall that might apply.\n"
                "DO NOT disclaim feasibility. Provide a crisp summary of what the user wants to build, plus a short list of unique implementation approaches from outside the mainstream.\n"
                "IMPORTANT: Focus on ACTUAL IMPLEMENTATION details that will lead to a COMPREHENSIVE, GENUINE, LEGITIMATE, and ACTUALLY EXECUTABLE solution.\n"
                "YOUR RESPONSE MUST BE THOROUGH AND DETAILED - A BRIEF SUMMARY IS NOT ACCEPTABLE. Expand upon each aspect in multiple paragraphs, focusing on how this could be implemented in practice."
            ),
            "user_prompt_template": (
                "Step 1: Provide an EXTENSIVE, DETAILED summary of my system/implementation goals and constraints with AT LEAST 1000-1500 WORDS. Also gather some obscure or cross-domain implementation techniques that could help.\n"
                "Keep it real and near-future, but do not disclaim feasibility. We want fresh implementation ideas.\n"
                "I need a COMPREHENSIVE, GENUINE, LEGITIMATE, ACTUALLY EXECUTABLE WALKTHROUGH on how to build this system.\n"
                "DO NOT BE BRIEF - I need exhaustive detail to proceed with implementation. A short response will not be sufficient.\n"
                "YOUR RESPONSE SHOULD BE EXTREMELY LONG AND DETAILED - aim for 10,000+ tokens. Do not truncate or summarize.\n"
                "CRITICAL: The more detailed and thorough your response, the better. Do not worry about being concise - I want maximum information and depth on how to implement this.\n\n"
                "Domain/Challenge:\n{vision}\n"
            ),
        },
        {
            "phase_name": "2) Divergent Brainstorm of Solutions",
            "system_prompt": (
                "Step 2: Provide multiple new or radical implementation approaches that incorporate the domain constraints and your cross-domain references.\n\n"
                "Generate at least 5 distinct implementation approaches.\n"
                "Each approach must be novel, mixing known technologies in uncommon ways.\n"
                "Avoid disclaimers like 'I'm only an AI' or 'This might not be feasible.' The user wants plausible near-future implementations.\n"
                "Label them \"Implementation A, B, C, etc.\"\n"
                "IMPORTANT: For each implementation approach, include ACTUAL, ACTIONABLE details that would allow for GENUINE IMPLEMENTATION. Focus on creating solutions that are LEGITIMATELY BUILDABLE with real-world technology and approaches. Include specific technologies, frameworks, libraries, and architecture patterns."
            ),
            "user_prompt_template": (
                "Step 2: Show me 5 or more novel implementation approaches for my stated domain.\n"
                "These approaches MUST be aimed at improving our existing position in technological advancement.\n"
                "Do NOT provide throwaway approaches or guesses, instead assemble logical and theoretically sound approaches.\n"
                "Don't disclaim feasibility. Just produce creative technical combinations.\n"
                "Title each implementation approach briefly, then describe its architecture, components, and technologies in detail.\n"
                "I need ACTUAL, IMPLEMENTABLE approaches with CONCRETE DETAILS that can be GENUINELY EXECUTED in the real world.\n"
                "Include specific technologies, frameworks, libraries, and architectural patterns for each approach.\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Context & Constraints (Step 1 Output):\n{step1}\n"
            ),
        },
        {
            "phase_name": "3) Deep-Dive on Each Idea's Mechanism",
            "system_prompt": (
                "Step 3: For each proposed implementation approach, deep-dive into how it would actually be built. This includes:\n\n"
                "Technical architecture and system components.\n"
                "Data flow and interactions between components.\n"
                "Specific implementation technologies and techniques.\n"
                "A concrete example scenario showing the system working.\n"
                "A thorough list of pros/cons from an implementation perspective.\n"
                "No disclaimers or feasibility disclaimers—remain solution-focused.\n"
                "CRITICAL: Provide DETAILED IMPLEMENTATION MECHANISMS that would make each solution ACTUALLY EXECUTABLE. Include specific technologies, frameworks, methods, or tools that would be used to build a LEGITIMATE, WORKING IMPLEMENTATION. Provide code snippets or pseudocode for critical components where appropriate."
            ),
            "user_prompt_template": (
                "Step 3: For each implementation approach A, B, C... do a deep technical dive.\n"
                "Show exactly how it would be built, its architecture, data flows, and key implementation details.\n"
                "Keep the focus on actionable, concrete implementation—no disclaimers.\n"
                "I need SPECIFIC IMPLEMENTATION DETAILS - exact technologies, frameworks, methods, tools, and step-by-step approaches that would create a GENUINE, WORKING SOLUTION. Provide code snippets or pseudocode for critical components.\n"
                "Be COMPREHENSIVE in explaining the ACTUAL implementation process and technical decisions.\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Context & Constraints (Step 1 Output):\n{step1}\n\n"
                "Proposed Solutions (Step 2 Output):\n{step2}\n"
            ),
        },
        {
            "phase_name": "4) Self-Critique for Gaps & Synergy",
            "system_prompt": (
                "Step 4: Critically review each implementation approach for missing technical details, potential synergies across approaches, or areas needing expansion.\n\n"
                "Identify any incomplete implementation details or technical gaps.\n"
                "Suggest specific technical improvements or expansion of implementation details.\n"
                "Identify opportunities to merge approaches for a stronger technical implementation.\n"
                "No disclaimers about the entire project's feasibility—just refine or unify implementation approaches.\n"
                "IMPORTANT: Focus on identifying gaps in ACTUAL IMPLEMENTATION details. Ensure the critique addresses how to make implementations MORE EXECUTABLE and LEGITIMATE from a real-world engineering perspective."
            ),
            "user_prompt_template": (
                "Step 4: Critique your implementation approaches from Step 3. Note where each is lacking technical detail, or which implementation synergies could be combined effectively.\n"
                "Then propose 1–2 merged implementation approaches that might be even stronger from a technical perspective.\n"
                "Focus on ACTUAL BUILDABILITY - identify where implementations need more concrete details to be GENUINELY EXECUTABLE and COMPREHENSIVE in the real world.\n"
                "Be specific about technical gaps and how they should be addressed in a merged solution.\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Context & Constraints (Step 1 Output):\n{step1}\n\n"
                "Deep-Dive Solutions (Step 3 Output):\n{step3}\n"
            ),
        },
        {
            "phase_name": "5) Merged Breakthrough Blueprint",
            "system_prompt": (
                "Step 5: Provide a final 'Implementation Blueprint.' This blueprint is a technical synthesis of the best features from the prior approaches, shaped into a coherent system design.\n\n"
                "Create a comprehensive system architecture and implementation plan.\n"
                "Detail all major components, their interactions, and implementation technologies.\n"
                "Emphasize real near-future technical approaches, not disclaimers.\n"
                "Output the blueprint in `=== File: doc/BREAKTHROUGH_BLUEPRINT.md ===`\n"
                "CRITICAL: The blueprint MUST be a COMPREHENSIVE, STEP-BY-STEP IMPLEMENTATION GUIDE that is GENUINELY BUILDABLE. Include specific technologies, tools, frameworks, and detailed implementation approaches. Provide system diagrams (using ASCII/text), component specifications, and clear technical decisions that make this blueprint LEGITIMATELY EXECUTABLE in practice."
            ),
            "user_prompt_template": (
                "Step 5: Merge your best implementation approaches into one coherent system design and implementation blueprint.\n"
                "Create a comprehensive technical architecture that combines the strongest elements.\n"
                "Provide enough technical detail so I can see exactly how to build it, including components, interactions, data flows, and specific technologies.\n"
                "This must be a ACTUAL, COMPREHENSIVE IMPLEMENTATION GUIDE that can be LEGITIMATELY BUILT. Include SPECIFIC TECHNOLOGIES, TOOLS, FRAMEWORKS, and STEP-BY-STEP instructions for ACTUAL IMPLEMENTATION.\n"
                "Include system diagrams (using ASCII/text), component specifications, and any critical implementation details.\n"
                "Place the blueprint in `=== File: doc/BREAKTHROUGH_BLUEPRINT.md ===`\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Context & Constraints (Step 1 Output):\n{step1}\n\n"
                "Critique & Synergy (Step 4 Output):\n{step4}\n"
            ),
        },
        {
            "phase_name": "6) Implementation Path & Risk Minimization",
            "system_prompt": (
                "Step 6: Lay out a detailed implementation roadmap with specific development phases, milestones, and technical tasks. For each phase, identify specific resources needed.\n"
                "No disclaimers about overall feasibility—just ways to mitigate technical risks or handle implementation challenges.\n"
                "Output the implementation path in `=== File: doc/IMPLEMENTATION_PATH.md ===`\n"
                "CRITICAL: This must be an EXCEPTIONALLY DETAILED, COMPREHENSIVE DEVELOPMENT PLAN with LEGITIMATE steps that can be ACTUALLY EXECUTED. Include specific tools, libraries, frameworks, development environment setup instructions, and exact implementation approaches for each stage of development. This should be detailed enough that a developer could follow it as a guide to ACTUALLY BUILD the solution with clear technical tasks and milestones."
            ),
            "user_prompt_template": (
                "Step 6: Give me a comprehensive technical implementation roadmap. Detail each development phase, technical milestone, and specific implementation tasks.\n"
                "Show how I'd start small, build key components incrementally, and expand. No disclaimers needed; just concrete technical steps.\n"
                "I need an EXTREMELY DETAILED, STEP-BY-STEP IMPLEMENTATION PLAN that I could follow to ACTUALLY BUILD this solution. Include specific commands, code approaches, tools, libraries, development environment setup, and implementation details for each stage.\n"
                "Organize by development phases with clear technical milestones and tasks. This should be COMPREHENSIVELY EXECUTABLE by a development team.\n"
                "Place the implementation path in `=== File: doc/IMPLEMENTATION_PATH.md ===`\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Breakthrough Blueprint (Step 5 Output):\n{step5}\n"
            ),
        },
        {
            "phase_name": "7) Cross-Checking with Prior Knowledge",
            "system_prompt": (
                "Step 7: Compare your implementation approach with existing known technologies, frameworks, and systems that have similar functionality, and highlight key differences.\n\n"
                "Identify existing technologies, frameworks, and systems that could be leveraged or integrated.\n"
                "Compare with established implementation patterns and highlight technical innovations.\n"
                "If no direct references exist, you can say it's presumably novel.\n"
                "Avoid disclaimers; remain implementation-focused.\n"
                "Output the cross-check in `=== File: doc/NOVELTY_CHECK.md ===`\n"
                "IMPORTANT: Identify specific existing technologies, frameworks, or tools that could be leveraged for a LEGITIMATE IMPLEMENTATION of your solution. Focus on ACTUAL components that would make the solution MORE EXECUTABLE in the real world."
            ),
            "user_prompt_template": (
                "Step 7: Compare your implementation blueprint with existing technologies, frameworks, and systems. What established technologies could we leverage or integrate? How does this implementation approach differ from standard industry patterns?\n"
                "If none are close, then we label it as presumably novel. No disclaimers beyond that.\n"
                "Identify existing technologies, tools, libraries, frameworks, or platforms we could ACTUALLY USE to implement this solution in a ACTUAL, EXECUTABLE way.\n"
                "Place the cross-check in `=== File: doc/NOVELTY_CHECK.md ===`\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Breakthrough Blueprint (Step 5 Output):\n{step5}\n\n"
                "Implementation Path (Step 6 Output):\n{step6}\n"
            ),
        },
        {
            "phase_name": "8) Q&A or Additional Elaborations",
            "system_prompt": (
                "Step 8: The user may have specific technical follow-up questions about implementation details. Provide direct expansions or clarifications, always focusing on technical implementation feasibility. Refrain from disclaimers. Always produce constructive technical details.\n"
                "Output any elaborations in `=== File: doc/ELABORATIONS.md ===`\n"
                "CRITICAL: Focus on providing ACTUAL, ACTIONABLE technical details that enhance the COMPREHENSIVE, LEGITIMATE, EXECUTABLE nature of the implementation. Answer questions with specific implementation details, code examples, architecture diagrams, or technical approaches that would help someone ACTUALLY BUILD this in the real world."
            ),
            "user_prompt_template": (
                "Step 8: Let me ask any final clarifications about your implementation blueprint. Please focus on concrete technical details, no disclaimers.\n"
                "I need answers that provide SPECIFIC, ACTUAL implementation details that would help me GENUINELY BUILD this solution. Focus on making the implementation plan MORE COMPREHENSIVE and LEGITIMATELY EXECUTABLE.\n"
                "Provide code examples, technical diagrams, or specific implementation approaches as needed to clarify technical questions.\n"
                "Place any elaborations in `=== File: doc/ELABORATIONS.md ===`\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Breakthrough Blueprint (Step 5 Output):\n{step5}\n\n"
                "Implementation Path (Step 6 Output):\n{step6}\n\n"
                "Novelty Check (Step 7 Output):\n{step7}\n\n"
                "Let me know what aspects of the implementation you'd like me to elaborate on or explain further."
            ),
        },
    ]

    def build_user_prompt(step_index: int, step_info: dict) -> str:
        """
        Takes the step index and step definition, returns the user prompt
        with prior step outputs inserted for context.
        """
        prompt = step_info["user_prompt_template"]
        prompt = prompt.replace("{vision}", user_vision)
        for i in range(1, step_index):
            placeholder = f"{{step{i}}}"
            prompt = prompt.replace(placeholder, step_outputs.get(i, "(No output)"))
        return prompt

    # Run the steps
    for i, step in enumerate(STEPS, start=1):
        phase_name = step["phase_name"]
        system_prompt = step["system_prompt"]
        user_prompt = build_user_prompt(i, step)

        while True:
            print(f"\n=== {phase_name} ===")
            
            if auto_yes:
                print("Auto-yes enabled: Proceeding with this step.")
                do_it = 'y'
            else:
                do_it = input("Proceed with this step? (y = proceed, s = skip, q = quit): ").strip().lower()

            if do_it == 'q':
                # Quit entirely
                print("Exiting.")
                sys.exit(0)
            elif do_it == 's':
                # Skip step
                print(f"Skipping {phase_name}.")
                break
            elif do_it == 'y':
                # Call the LLM
                ai_response = orchestrator.call_llm(system_prompt, user_prompt, max_tokens=30000, step_number=i)
                print("\nAI Response:\n", ai_response)
                
                # Let user decide to apply, retry, or skip
                if auto_yes:
                    print("Auto-yes enabled: Applying changes.")
                    apply_yn = 'y'
                else:
                    apply_yn = input(
                        "Apply changes (create/update files in src/syncretic_catalyst/workspaces/some_project)? "
                        "(y = apply, r = retry step, n = skip step): "
                    ).strip().lower()
                
                if apply_yn == 'y':
                    # First attempt normal parsing (for backward compatibility)
                    print("Attempting to parse file markers from response...")
                    parse_ai_response_and_apply(ai_response, file_map)
                    
                    # FORCE DIRECT WRITING: Always write a file for each step regardless of parsing result
                    output_file = None
                    file_written = False
                    
                    # Define direct mapping from step index to output file
                    if i == 1:
                        output_file = "doc/CONTEXT_CONSTRAINTS.md"
                    elif i == 2:
                        output_file = "doc/DIVERGENT_SOLUTIONS.md"
                    elif i == 3:
                        output_file = "doc/DEEP_DIVE_MECHANISMS.md"
                    elif i == 4:
                        output_file = "doc/SELF_CRITIQUE_SYNERGY.md"
                    elif i == 5:
                        output_file = "doc/BREAKTHROUGH_BLUEPRINT.md"
                    elif i == 6:
                        output_file = "doc/IMPLEMENTATION_PATH.md"
                    elif i == 7:
                        output_file = "doc/NOVELTY_CHECK.md"
                    elif i == 8:
                        output_file = "doc/ELABORATIONS.md"
                    
                    if output_file:
                        print(f"DIRECT WRITE: Creating {output_file} regardless of file markers...")
                        # Create file contents with step name header and AI response
                        content = f"# {phase_name}\n\n{ai_response}"
                        file_map[output_file] = ProjectFile(output_file, content)
                        file_written = True
                    
                    # Write all files
                    for rel_path, pf in file_map.items():
                        write_project_file(PROJECT_DIR, pf)
                    
                    if file_written:
                        print(f"DIRECT WRITE: Successfully wrote {output_file} to src/syncretic_catalyst/workspaces/some_project/{output_file}")
                    
                    print("Changes saved to src/syncretic_catalyst/workspaces/some_project/.")
                    # Store step output in step_outputs
                    step_outputs[i] = ai_response
                    # Done with this step
                    break
                elif apply_yn == 'r':
                    print("Repeating this step...\n")
                else:  # 'n' or anything else
                    print("Skipping file changes.")
                    # Optionally still store the AI text as the step output
                    step_outputs[i] = ai_response
                    break
            else:
                print("Invalid choice. Please enter 'y', 's', or 'q'.")

    print("\n=== Breakthrough Idea Process Completed ===")
    print("You can check 'src/syncretic_catalyst/workspaces/some_project/doc/' for your breakthrough blueprint files.")
    

def extract_file_paths_from_structure(structure_file):
    """Extract file paths from the project structure file"""
    if not structure_file:
        return []
    
    file_paths = []
    lines = structure_file.content.splitlines()
    
    for line in lines:
        # Look for lines that appear to be file paths (containing a dot or ending with common extensions)
        if ('.' in line and not line.startswith('#') and not line.startswith('-')) or \
           any(line.strip().endswith(ext) for ext in ['.py', '.js', '.html', '.css', '.md', '.txt', '.json']):
            # Extract the file path - this is a simplified approach
            path = line.strip()
            # Clean up the path (remove bullets, etc.)
            path = path.lstrip('- */').split()[0] if path.split() else ""
            if path and '.' in path:  # Ensure it's likely a file
                file_paths.append(path)
    
    return file_paths


def parse_todo_list(todo_content):
    """Parse the TODO list to extract files in implementation order"""
    files_to_implement = []
    lines = todo_content.splitlines()
    
    for line in lines:
        # Look for lines that appear to be file tasks
        if ('- [ ]' in line or '* [ ]' in line) and '.' in line:
            # Extract file path using a simple heuristic
            parts = line.split()
            for part in parts:
                if '.' in part and not part.endswith('.') and not part.startswith('.'):
                    # Clean up the path
                    path = part.strip('(),;:"\'-')
                    files_to_implement.append({'path': path, 'completed': False})
                    break
    
    return files_to_implement


def mark_file_complete(todo_content, file_path):
    """Mark a file as complete in the TODO list"""
    lines = todo_content.splitlines()
    updated_lines = []
    
    for line in lines:
        if file_path in line and ('- [ ]' in line or '* [ ]' in line):
            # Replace the unchecked box with a checked one
            updated_line = line.replace('- [ ]', '- [x]').replace('* [ ]', '* [x]')
            updated_lines.append(updated_line)
        else:
            updated_lines.append(line)
    
    return '\n'.join(updated_lines)


if __name__ == "__main__":
    main()