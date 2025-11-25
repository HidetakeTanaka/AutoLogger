# Project Title  
AutoLogger – Baseline Module (Role C: Baseline Implementer)
#  Author
Farhana Easmin Mithila
# Overview
This document describes the baseline implementations.As the Baseline Implementer, the responsibility is to build two comparative systems:

Heuristic Baseline (rule-based)

Random Baseline (probabilistic)

Both baselines consume structured output produced by the parser (Role A) and generate automatic logging statements in a unified JSON format to support downstream evaluation (Role D).



# 📁 Folder Structure
AutoLogger/
│
├── parser/
│   └── parser.py                      # Provided by Role A
│
├── baselines/
│   ├── baseline_heuristic.py          # Heuristic baseline
│   ├── baseline_random.py             # Random baseline
│   ├── parser_output.json             # Parser output used as input
│   └── README_baselines.md            # Documentation for baselines
│
└── example.py                         # Example script used for testing

# 1. Required Input File
Both baseline systems require this file:

    baselines/parser_output.json

This file must contain the parser output for a target Python script



## How to generate it:
1. Run the parser on a Python file (example.py):

        python parser/parser.py example.py

This produces:

    example.candidates.json

2. Copy it into the baselines folder:

   copy example.candidates.json baselines/parser_output.json


Now the baseline code can run successfully
## 2. Run the Heuristic Baseline

    python baseline_heuristic.py
 Output:


    baselines/results_heuristic.json

What it does:

Reads all candidate positions from

    parser_output.json

Normalizes parser kinds (func_entry, before_return, etc.)

Assigns deterministic log messages:

Entering a function

Exiting a function

Exception in a function

Assigns fixed log levels:

entry → INFO

return → DEBUG

except → ERROR

io/event → INFO

The heuristic baseline acts as a strong traditional baseline for comparison against the LLM-based system.
## 3. Run the Random Baseline
    python baseline_random.py
 Output:

    baselines/results_random.json
What it does:

Randomly selects ~30% of candidates

Randomly chooses a log level from:


    DEBUG, INFO, WARNING, ERROR
Creates messages like:

    Random log at line <line> in <function>
Uses a fixed random seed (42) for reproducibility

This baseline acts as a weak baseline to show the value of structured logging versus random behavior.
## 4. Output JSON Schema
Both baseline outputs follow this structure:

{
  "file": "<source_file>",
  "baseline_type": "heuristic" or "random",
  "logs": [
    {
      "line": 12,
      "level": "INFO",
      "message": "Entering my_function",
      "kind": "entry",
      "function": "my_function"
    }
  ]
}


This is the same schema used by:

The LLM module (Role B)

The Evaluation module (Role D)
## 5. Internal Logic Summary

 Heuristic Rules:

func_entry → entry (INFO)

before_return → return (DEBUG)

except → except (ERROR)

other →  event (INFO)

 Random Baseline Logic

probability = 0.30

seed = 42

Random selection of log level

Message always:
    "Random log at line <line> in <function>"

## 6. How to Test the Full Pipeline

Step 1: Generate parser output

    python parser/parser.py example.py

Step 2: Move parser output to baselines

    copy example.candidates.json baselines/parser_output.json

Step 3: Run baseline systems

    python baseline_heuristic.py

    python baseline_random.py

# Troubleshooting:

Missing parser_output.json → copy parser output.

Missing parser/parser.py → ensure correct folder.

Missing example.py → create a simple Python script.

# Role Completion:

Heuristic baseline implemented

Random baseline implemented

JSON format followed

Parser→Baseline pipeline functioning

Integration-ready
