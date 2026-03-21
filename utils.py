import re
from pathlib import Path

import numpy as np
import pandas as pd


_ORWD_PATH = Path("/orwd_data")
_LOCAL_PATH = Path(__file__).resolve().parent
DATA_DIR = _ORWD_PATH if _ORWD_PATH.exists() else _LOCAL_PATH


# Matches the original BioReason-Pro CAFA5_REASONING_TEMPLATE_WITH_CONTEXT_PPI system prompt
SYSTEM_PROMPT = (
    "You are a scientific assistant specialized in protein function prediction. "
    "Given a protein sequence, organism information, and additional context "
    "(InterPro domain annotations and/or initial GO term speculations), "
    "step-by-step reason about the InterPro terms, Gene Ontology (GO) terms "
    "regarding molecular function, biological process, and cellular component, "
    "protein-protein interactions (PPI), and overall function. Use the provided "
    "information as a starting point and improve upon it with deeper analysis. "
    "Provide a summary of your findings in your final answer."
)

ASPECT_GO_SUFFIX = {
    "mf": " and predict Molecular Function (MF) GO terms.",
    "bp": " and predict Biological Process (BP) GO terms.",
    "cc": " and predict Cellular Component (CC) GO terms.",
    "all": " and predict Molecular Function (MF), Biological Process (BP), and Cellular Component (CC) GO terms.",
}

ASPECT_COLUMNS = {
    "mf": "go_mf",
    "bp": "go_bp",
    "cc": "go_cc",
}


def parse_go_list(value) -> list[str]:
    """Parse a GO term list from various storage formats (list, numpy array, string)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        return re.findall(r"GO:\d{7}", value)
    return []


def _safe_str(value, default: str = "") -> str:
    """Return string value, or default if null/NaN."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    s = str(value).strip()
    return s if s else default


def format_prompt(row: pd.Series, aspect: str) -> str:
    """Format prompt faithful to the original BioReason-Pro reasoning template.

    The original pipeline (CAFA5_REASONING_TEMPLATE_WITH_CONTEXT_PPI) provides:
    - System: scientific assistant instructions
    - User: organism, InterPro annotations, PPI partners, GO-GPT speculations

    Since our environment targets text-only LLMs (no protein embedding module),
    we also include the protein sequence and metadata directly in the prompt.
    """
    interpro = _safe_str(row.get("interpro_formatted"), "None available")
    ppi = _safe_str(row.get("ppi_formatted"), "None available")
    go_pred = _safe_str(row.get("go_pred"), "None available")
    organism = _safe_str(row.get("organism"), "Unknown")
    protein_id = row["protein_id"]
    protein_names = _safe_str(row.get("protein_names"), "Unknown")
    protein_function = _safe_str(row.get("protein_function"), "Unknown")
    subcellular = _safe_str(row.get("subcellular_location"), "Unknown")
    sequence = row["sequence"]
    length = int(row["length"])

    go_suffix = ASPECT_GO_SUFFIX[aspect]

    # Matches the original CAFA5_REASONING_TEMPLATE_WITH_CONTEXT_PPI user prompt
    # with added protein metadata since we don't have a separate protein embedding module
    user_prompt = f"""Protein ID: {protein_id}
Protein Name: {protein_names}
Organism: {organism}
Sequence Length: {length}
Subcellular Location: {subcellular}
Protein Function: {protein_function}

Protein Sequence:
{sequence}

InterPro Annotations:
{interpro}

Protein-Protein Interaction Partners:
{ppi}

Initial GO Term Speculations (from GO-GPT):
{go_pred}

Reason about the function of the protein{go_suffix}

Provide your predicted GO terms as a list of GO term IDs (e.g., GO:0003674, GO:0005488, ...)."""

    return f"{SYSTEM_PROMPT}\n\n{user_prompt}"


def load_data() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Load data and return (split->tasks, id->answers).

    Returns:
        tasks_by_split: dict mapping split name to list of task dicts (public info only)
        answers: dict mapping task_id to answer dict with GO term sets
    """
    df = pd.read_parquet(DATA_DIR / "data.parquet")

    tasks_by_split: dict[str, list[dict]] = {
        "train": [],
        "mf": [],
        "bp": [],
        "cc": [],
    }
    answers: dict[str, dict] = {}

    for _, row in df.iterrows():
        pid = row["protein_id"]

        # Parse GO terms for each aspect
        go_terms = {}
        for aspect, col in ASPECT_COLUMNS.items():
            go_terms[aspect] = parse_go_list(row.get(col))

        # Combined GO terms for the "train" split
        all_go = parse_go_list(row.get("go_ids"))
        if not all_go:
            all_go = list(set(
                go_terms["mf"] + go_terms["bp"] + go_terms["cc"]
            ))

        # Per-aspect tasks
        for aspect in ["mf", "bp", "cc"]:
            if go_terms[aspect]:
                task_id = f"{pid}_{aspect}"
                prompt_text = format_prompt(row, aspect)

                tasks_by_split[aspect].append({
                    "id": task_id,
                    "protein_id": pid,
                    "prompt_text": prompt_text,
                    "aspect": aspect,
                })
                answers[task_id] = {
                    "go_terms": set(go_terms[aspect]),
                }

        # "train" split: all aspects combined
        if all_go:
            task_id = f"{pid}_all"
            prompt_text = format_prompt(row, "all")

            tasks_by_split["train"].append({
                "id": task_id,
                "protein_id": pid,
                "prompt_text": prompt_text,
                "aspect": "all",
            })
            answers[task_id] = {
                "go_terms": set(all_go),
            }

    return tasks_by_split, answers
