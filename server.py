import sys

from fastapi import FastAPI, HTTPException
from flask import Flask, request, jsonify
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import subprocess
import uvicorn
import json
import os


REPO_DIRECTORY = "./repos"
SCAN_RESULTS_DIR = "./scan_results"

# Ensure directories exist
os.makedirs(REPO_DIRECTORY, exist_ok=True)
os.makedirs(SCAN_RESULTS_DIR, exist_ok=True)

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

def scan_all_repos():
    """Cron job to scan all repositories and store results in JSON files."""
    print("Scanning all repos...")
    repos = [d for d in os.listdir(REPO_DIRECTORY) if os.path.isdir(os.path.join(REPO_DIRECTORY, d))]
    print(f"Repositories found: {repos}")

    for repo in repos:
        try:
            scan_repo(repo)
        except Exception as e:
            print(f" Error scanning {repo}: {e}")

def scan_repo(repo_name: str):
    """Runs Semgrep on a specific repo and stores the results."""
    local_path = os.path.join(REPO_DIRECTORY, repo_name)
    output_file = os.path.join(SCAN_RESULTS_DIR, f"{repo_name}.json")

    if not os.path.exists(local_path):
        print(f"Repo {repo_name} does not exist locally.")
        return

    try:
        subprocess.run([
            "semgrep", "scan", "--config", "p/default", "--json",
            "--output", output_file, "--quiet", local_path
        ], check=True)
        print(f"Scan completed for {repo_name}, results saved at {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Semgrep failed for {repo_name}: {e}")
    except FileNotFoundError:
        print("Error: Semgrep is not installed. Please install it with `pip install semgrep`.")

# Running scan once on startup
scan_all_repos()

# Initialize Background Scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(scan_all_repos, 'interval', hours=1)  # Runs every hour
scheduler.start()
print("Scheduler started and running in the background...")

@app.get("/repos")
def list_repos():
    print(" Fetching list of repositories...")
    """Returns a list of available repositories that have scan results."""
    repo_files = [f.replace(".json", "") for f in os.listdir(SCAN_RESULTS_DIR) if f.endswith(".json")]
    return {"repos": repo_files}

@app.get("/results/{repo_name}")
def get_scan_results(repo_name: str):
    """Returns the scan results for a specific repo."""
    output_file = os.path.join(SCAN_RESULTS_DIR, f"{repo_name}.json")

    if not os.path.exists(output_file):
        raise HTTPException(status_code=404, detail="No scan results found for this repo.")

    with open(output_file, "r") as f:
        scan_results = json.load(f)

    return {"results": scan_results.get("results", [])}


if __name__ == "__main__":
    print("Starting FastAPI server on http://localhost:8000 ...")
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
    except (KeyboardInterrupt, SystemExit):
        print("\nShutting down scheduler...")
        scheduler.shutdown()
        print("Scheduler stopped.")
