import re
from typing import List

from pydantic import BaseModel

from openreward.environments import Environment, JSONObject, Split, ToolOutput, terminal, tool, TextBlock
from utils import load_data


# Reward for a submission made after the task has already been graded. Negative
# so repeat submissions are actively discouraged, not merely left unscored.
REPEAT_SUBMISSION_PENALTY = -0.1


class TaskSpec(BaseModel):
    id: str
    protein_id: str
    prompt_text: str
    aspect: str


class AnswerInput(BaseModel, extra="forbid"):
    answer: str


TASKS_BY_SPLIT, ANSWERS = load_data()


def compute_f1(predicted: set[str], truth: set[str]) -> dict:
    """Compute set-based precision, recall, and F1 for GO term prediction."""
    if not predicted or not truth:
        return {"f1": 0.0, "precision": 0.0, "recall": 0.0}
    tp = len(predicted & truth)
    precision = tp / len(predicted)
    recall = tp / len(truth)
    if precision + recall == 0:
        return {"f1": 0.0, "precision": 0.0, "recall": 0.0}
    f1 = 2 * precision * recall / (precision + recall)
    return {"f1": f1, "precision": precision, "recall": recall}


class BioReasonPro(Environment):
    def __init__(self, task_spec: JSONObject, secrets: dict[str, str] = {}) -> None:
        super().__init__(task_spec)
        self.validated = TaskSpec.model_validate(task_spec)
        self.ground_truth = ANSWERS[self.validated.id]["go_terms"]

        # Graded submissions this session. @terminal already hides this tool from
        # the model, so the harness normally invokes it once at the end of the
        # rollout -- but Environment._call_tool dispatches by name and does not
        # exclude terminal tools, so a direct second call would re-grade and pay
        # out again. Defence in depth.
        self.submitted = 0

    @terminal
    @tool
    async def answer(self, params: AnswerInput) -> ToolOutput:
        """Grade the assistant's final message by extracting GO term IDs and computing set F1."""
        if self.submitted > 0:
            return ToolOutput(
                blocks=[TextBlock(text="An answer has already been submitted for this task. "
                                       "This episode is over: it is not re-graded, and repeat "
                                       "submissions are penalised (reward -0.1).")],
                metadata={"already_submitted": True, "submission_count": self.submitted},
                reward=REPEAT_SUBMISSION_PENALTY,
                finished=True,
            )

        predicted = set(re.findall(r"GO:\d{7}", params.answer))
        metrics = compute_f1(predicted, self.ground_truth)
        reward = metrics["f1"]

        self.submitted += 1

        return ToolOutput(
            metadata={
                **metrics,
                "n_predicted": len(predicted),
                "n_truth": len(self.ground_truth),
            },
            blocks=[TextBlock(text=(
                f"F1: {metrics['f1']:.3f} | "
                f"Precision: {metrics['precision']:.3f} | "
                f"Recall: {metrics['recall']:.3f} | "
                f"Predicted: {len(predicted)} | "
                f"Ground Truth: {len(self.ground_truth)}"
            ))],
            reward=reward,
            finished=True,
        )

    async def get_prompt(self) -> List[TextBlock]:
        return [TextBlock(text=self.validated.prompt_text)]

    @classmethod
    def list_tasks(cls, split: str) -> list[JSONObject]:
        if split not in TASKS_BY_SPLIT:
            raise ValueError(f"Unknown split: {split}. Available: {list(TASKS_BY_SPLIT.keys())}")
        return TASKS_BY_SPLIT[split]  # type: ignore

    @classmethod
    def list_splits(cls) -> list[Split]:
        return [
            Split(name="train", type="train"),
            Split(name="mf", type="train"),
            Split(name="bp", type="train"),
            Split(name="cc", type="train"),
        ]
