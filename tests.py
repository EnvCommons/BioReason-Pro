import pytest

from bioreason_pro import BioReasonPro, AnswerInput


split = BioReasonPro.list_splits()[0]
tasks = BioReasonPro.list_tasks(split=split)
N_CHECK = 10
tasks = tasks[:N_CHECK]


@pytest.mark.asyncio
@pytest.mark.parametrize("task", tasks)
async def test_bad_answer(task: dict):
    env = BioReasonPro(task_spec=task)
    res = await env.answer(params=AnswerInput(answer="covfefe"))
    assert res.reward == 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize("task", tasks)
async def test_perfect_answer(task: dict):
    env = BioReasonPro(task_spec=task)
    go_terms_str = " ".join(env.ground_truth)
    res = await env.answer(params=AnswerInput(answer=go_terms_str))
    assert res.reward == 1.0


@pytest.mark.asyncio
@pytest.mark.parametrize("task", tasks)
async def test_partial_answer(task: dict):
    env = BioReasonPro(task_spec=task)
    half = list(env.ground_truth)[: len(env.ground_truth) // 2]
    if not half:
        pytest.skip("Not enough GO terms to test partial")
    res = await env.answer(params=AnswerInput(answer=" ".join(half)))
    assert 0.0 < res.reward < 1.0
