"""Test agent for BioReason-Pro (terminal-tool style, zero visible tools).

The agent receives protein/context info and replies with a plain-text message
listing predicted GO term IDs. The @terminal grader regex-extracts all
`GO:XXXXXXX` matches from the whole reply and computes set F1 against the
reference.

Runs against the deployed env by default; set LOCAL=1 for localhost:8080.
"""

import asyncio
import json
import os

from openai import AsyncOpenAI
from openreward import AsyncOpenReward


def _text_of(response) -> str:
    parts = []
    for item in response.output:
        if item.type == "message":
            for block in item.content:
                if block.type == "output_text":
                    parts.append(block.text)
    return "\n".join(parts).strip()


async def main():
    or_client = AsyncOpenReward()
    oai_client = AsyncOpenAI()

    MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-5.2")
    ENV_NAME = os.environ.get("ENV_NAME", "GeneralReasoning/bioreason-pro-rl-reasoning-data")
    SPLIT = os.environ.get("SPLIT", "mf")
    NUM_TASKS = int(os.environ.get("NUM_TASKS", "1"))
    MAX_TURNS = int(os.environ.get("MAX_TURNS", "10"))

    base_url = "http://localhost:8080" if os.environ.get("LOCAL") else None
    environment = or_client.environments.get(name=ENV_NAME, base_url=base_url)

    tasks = await environment.list_tasks(split=SPLIT)
    tools = await environment.list_tools(format="openai")
    terminal_tool = await environment.terminal_tool()

    print(f"Environment: {ENV_NAME} ({base_url or 'deployed'})")
    print(f"Split={SPLIT}, found {len(tasks)} tasks; visible tools: {[t['name'] for t in tools]}")
    print(f"Terminal tool (hidden): {terminal_tool}")

    rewards = []
    for task in tasks[:NUM_TASKS]:
        task_id = task.task_spec["id"]
        print(f"\n=== Task {task_id} ({task.task_spec.get('aspect')}) ===")

        async with environment.session(task=task) as session:
            assistant_ends_rollout = await session.is_assistant_message_final()
            session_tools = await session.list_tools()
            assert "answer" not in [t.name for t in session_tools], \
                "terminal tool leaked into the model's tool list"

            prompt = await session.get_prompt()
            input_list = [{"role": "user", "content": prompt[0].text}]

            reward = None
            turn = 0
            while turn < MAX_TURNS:
                turn += 1
                # Zero-tool env: omit `tools` entirely (some providers reject []).
                kwargs = {"model": MODEL_NAME, "input": input_list}
                if tools:
                    kwargs["tools"] = tools
                response = await oai_client.responses.create(**kwargs)
                input_list += response.output

                calls = [i for i in response.output if i.type == "function_call"]
                if calls:
                    # No tools exposed; defensive.
                    for item in calls:
                        tr = await session.call_tool(
                            item.name, json.loads(str(item.arguments)),
                        )
                        input_list.append({
                            "type": "function_call_output",
                            "call_id": item.call_id,
                            "output": tr.blocks[0].text if tr.blocks else "",
                        })
                    continue

                final_message = _text_of(response)
                print(f"Final message ({len(final_message)} chars): {final_message[:200]}")

                if not assistant_ends_rollout:
                    print("Not terminal-style; stopping.")
                    break

                out = await session.call_terminal_tool(final_message)
                reward = out.reward
                print(f"call_terminal_tool -> reward={reward:.4f} finished={out.finished}")
                if out.blocks:
                    print(out.blocks[0].text[:300])
                break

            rewards.append(reward)

    scored = [r for r in rewards if r is not None]
    print(f"\n=== Summary ===")
    print(f"num_tasks={len(rewards)} num_scored={len(scored)} "
          f"mean_reward={sum(scored)/len(scored) if scored else None}")
    print(f"rewards={rewards}")


if __name__ == "__main__":
    asyncio.run(main())
