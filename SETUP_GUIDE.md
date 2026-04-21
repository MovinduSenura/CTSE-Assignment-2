# AI Travel Planner Setup Guide

## 1. Project Overview

This project is a multi-agent AI travel planner built with:

- `LangGraph` for orchestration
- `LangChain Ollama` for the local LLM connection
- `Pydantic` for structured data validation
- `Requests` for external data retrieval
- `Pytest` and `Hypothesis` for testing

The system currently focuses on **Sri Lanka destinations only** and runs as a CLI application through `main.py`.

## 2. Prerequisites

Before running the system, make sure you have:

- Python `3.10+` installed
- `pip` available
- `Ollama` installed and running locally
- The Ollama model `llama3:latest` pulled locally
- Internet access for:
  - OpenStreetMap Nominatim geocoding
  - Wikipedia geosearch and summaries

This repository was successfully checked here with:

- Python `3.13.7`

## 3. Clone or Open the Project

Open the project folder in a terminal:

```powershell
cd "d:\SLIIT\Y4S2\CTSE\Assignment 2\CTSE-Assignment-2"
```

## 4. Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Then activate again:

```powershell
.venv\Scripts\Activate.ps1
```

## 5. Install Dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Installed packages include:

- `langgraph`
- `langchain-ollama`
- `pydantic`
- `python-dotenv`
- `requests`
- `pytest`
- `hypothesis`

## 6. Configure Ollama

Start Ollama if it is not already running, then pull the required model:

```powershell
ollama pull llama3:latest
```

The repository already includes a simple `.env` file:

```env
OLLAMA_MODEL=llama3:latest
LOG_LEVEL=INFO
```

Important note:

- `main.py` currently defaults to `llama3:latest` directly in code.
- The `.env` file is useful as project documentation, but the current code does not actively load it with `python-dotenv`.

## 7. Run the Application

### Option A: Natural-language request

```powershell
python main.py --request "Plan a 2-day trip to Kandy under 30000 for culture and food"
```

### Option B: Structured arguments

```powershell
python main.py --destination Kandy --budget 30000 --days 2 --currency LKR --interests culture food
```

### Option C: Show planner-stage details

```powershell
python main.py --request "Plan a 3-day trip to Ella under 25000 for nature and food" --show-planner-details
```

## 8. Expected Output

When the program runs successfully, it prints:

- the structured input
- optional planner output
- the final reviewed itinerary
- the log file path

Execution logs are written to:

- `logs/execution.log`

## 9. Run Tests

Use:

```powershell
python -m pytest -q
```

Verified result in this repository:

- `28 passed`

## 10. Folder Structure

```text
CTSE-Assignment-2/
|- main.py
|- requirements.txt
|- .env
|- logs/
|- Member_1_Planner/
|- Member_2_Researcher/
|- Member_3_Executor/
|- Member_4_Reviewer/
```

## 11. What Each Module Does

- `Member_1_Planner`: validates user input, normalizes the request, and creates downstream tasks
- `Member_2_Researcher`: resolves the destination and finds nearby attractions from public APIs
- `Member_3_Executor`: estimates the trip budget using destination cost profiles
- `Member_4_Reviewer`: checks completeness and produces the final itinerary text

## 12. Common Issues

### `pytest` is not recognized

Use:

```powershell
python -m pytest -q
```

### Ollama model not found

Run:

```powershell
ollama pull llama3:latest
```

### Destination rejected

The planner currently supports **Sri Lanka destinations only**. Requests for places outside Sri Lanka will fail validation.

### No attraction data found

This can happen if:

- the external API is temporarily unavailable
- the destination cannot be resolved
- nearby Wikipedia attraction data is limited

### Logs folder issues

The application writes to `logs/execution.log`, so make sure the `logs` folder exists. In this repository it already exists.

## 13. Recommended Demo Commands

```powershell
python main.py --request "Plan a 2-day trip to Kandy under 30000 for culture and food"
python main.py --request "Plan a 3-day trip to Ella under 25000 for nature and photography"
python main.py --request "Plan a 1-day trip to Galle under Rs 10000 for beach and food"
```

## 14. Current Limitations

- Destination support is limited to Sri Lanka
- The workflow is sequential, not parallel
- Budget estimation uses fixed heuristic profiles
- External data quality depends on Nominatim and Wikipedia
- `.env` values are not fully wired into runtime behavior

## 15. Quick Start Summary

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull llama3:latest
python main.py --request "Plan a 2-day trip to Kandy under 30000 for culture and food"
python -m pytest -q
```
