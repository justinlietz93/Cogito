#!/usr/bin/env python3
import os
import re
import glob

def extract_title(content):
    """Extract the title from the markdown content"""
    match = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "Untitled Section"

def extract_content(filepath):
    """Extract content from a file, skipping any special header markers"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Remove any file markers like "=== File: doc/XXXXX.md ==="
        content = re.sub(r'===\s*File:\s*[^=]+===\s*', '', content)
        
        # Remove any cursor position markers
        content = re.sub(r'<CURRENT_CURSOR_POSITION>', '', content)
        
        return content
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return ""

def main():
    # Define the order of files and their logical numbering
    file_order = [
        ("src/syncretic_catalyst/workspaces/some_project/doc/CONTEXT_CONSTRAINTS.md", "1"),
        ("src/syncretic_catalyst/workspaces/some_project/doc/DIVERGENT_SOLUTIONS.md", "2"),
        ("src/syncretic_catalyst/workspaces/some_project/doc/DEEP_DIVE_MECHANISMS.md", "3"),
        ("src/syncretic_catalyst/workspaces/some_project/doc/SELF_CRITIQUE_SYNERGY.md", "4"),
        ("src/syncretic_catalyst/workspaces/some_project/doc/MISSING_COMPONENTS.md", "5"),
        ("src/syncretic_catalyst/workspaces/some_project/doc/IMPLEMENTATION_PATH.md", "6"),
        ("src/syncretic_catalyst/workspaces/some_project/doc/NOVELTY_CHECK.md", "7"),
        ("src/syncretic_catalyst/workspaces/some_project/doc/ELABORATIONS.md", "8"),
        ("src/syncretic_catalyst/workspaces/some_project/doc/BREAKTHROUGH_BLUEPRINT.md", "9")
    ]
    
    # Output file (final assembled manual goes to universal output_results)
    target_file = "output_results/syncretic_catalyst/some_project/COMPREHENSIVE_MANUAL.md"
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(target_file), exist_ok=True)
    
    # Create the new content starting with the title and introduction
    new_content = [
        "# Comprehensive Implementation Manual\n\n",
        "This document provides a complete guide to understanding, designing, and implementing the project below. It combines all relevant documentation into a single comprehensive resource.\n\n",
        "## Table of Contents\n\n"
    ]
    
    # Placeholder for table of contents
    toc_entries = []
    
    # Collect and process all content
    sections_content = []
    
    for filepath, section_number in file_order:
        if os.path.exists(filepath):
            content = extract_content(filepath)
            if content:
                # Extract the title
                title = extract_title(content)
                cleaned_title = re.sub(r'^[\d\.\s\)\-]+', '', title).strip()
                
                # Format the section with proper heading
                formatted_section = f"# {section_number}. {cleaned_title}\n\n{content}"
                
                # Update heading levels (increase all by one level)
                formatted_section = re.sub(r'^# ', '## ', formatted_section, flags=re.MULTILINE)
                formatted_section = re.sub(r'^## ', '### ', formatted_section, flags=re.MULTILINE)
                formatted_section = re.sub(r'^### ', '#### ', formatted_section, flags=re.MULTILINE)
                formatted_section = re.sub(r'^#### ', '##### ', formatted_section, flags=re.MULTILINE)
                formatted_section = re.sub(r'^##### ', '###### ', formatted_section, flags=re.MULTILINE)
                
                # Add to table of contents
                toc_entries.append(f"{section_number}. [{cleaned_title}](#{section_number}-{cleaned_title.lower().replace(' ', '-').replace('(', '').replace(')', '').replace('&', '').replace(':', '')})")
                
                # Add to sections
                sections_content.append(formatted_section)
        else:
            print(f"Warning: File {filepath} not found")
    
    # Add table of contents
    for entry in toc_entries:
        new_content.append(f"- {entry}\n")
    
    new_content.append("\n")
    
    # Add all sections
    for section in sections_content:
        new_content.append(section)
        new_content.append("\n\n")
    
    # Write to the target file
    try:
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(''.join(new_content))
        print(f"Successfully created {target_file}")
    except Exception as e:
        print(f"Error writing target file: {e}")
        return

if __name__ == "__main__":
    main() 