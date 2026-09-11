"""
execute_all_notebooks.py
Executes all notebooks in place using nbclient / nbconvert so that outputs are populated.
"""

import os
import sys
import nbformat
from nbclient import NotebookClient

# Add repo root to sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

NOTEBOOKS = [
    "notebooks/01_first_look_and_discovery.ipynb",
    "notebooks/02_your_first_readable_model.ipynb",
    "work/notebooks/w01_research_question.ipynb",
    "work/notebooks/w02_ml_task_framing.ipynb",
    "work/notebooks/w03_data_contract.ipynb",
    "work/notebooks/w03_feature_leakage_check.ipynb",
    "work/notebooks/w04_signal_audit.ipynb",
    "work/notebooks/w04_baseline_score.ipynb",
    "work/notebooks/w05_model.ipynb",
    "work/notebooks/w06_validation_audit.ipynb",
    "work/notebooks/w07_action_playbook.ipynb",
    "work/notebooks/capstone.ipynb"
]

def run_notebook(rel_path):
    full_path = os.path.join(repo_root, rel_path)
    print(f"\n==========================================")
    print(f"Executing {rel_path}...")
    nb = nbformat.read(full_path, as_version=4)
    # Use cwd=repo_root so relative paths like data/raw/... resolve correctly
    client = NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": repo_root}})
    client.execute()
    nbformat.write(nb, full_path)
    print(f"Successfully executed and saved: {rel_path}")

def main():
    failures = []
    for nb in NOTEBOOKS:
        try:
            run_notebook(nb)
        except Exception as e:
            print(f"ERROR running {nb}: {e}")
            failures.append((nb, str(e)))
    
    if failures:
        print("\nFailed notebooks:")
        for nb, err in failures:
            print(f"- {nb}: {err}")
        sys.exit(1)
    else:
        print("\nALL NOTEBOOKS EXECUTED CLEANLY WITH NO ERRORS!")

if __name__ == "__main__":
    main()
