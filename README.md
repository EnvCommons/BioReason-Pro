# bioreason-pro-rl-reasoning-data

[![OpenReward Environment](https://img.shields.io/badge/%E2%AD%90%20OpenReward-Environment-f7e6cc)](https://openreward.ai/GeneralReasoning/bioreason-pro-rl-reasoning-data) [![Hugging Face Dataset](https://img.shields.io/badge/Hugging%20Face-Dataset-orange)](https://huggingface.co/datasets/wanglab/bioreason-pro-rl-reasoning-data)

## Description

bioreason-pro-rl-reasoning-data is an environment for evaluating protein function prediction using Gene Ontology (GO) term annotation, based on the [BioReason-Pro](https://github.com/bowang-lab/BioReason-Pro) dataset. Agents receive protein metadata including amino acid sequence, organism, InterPro domain annotations, protein-protein interaction partners, and initial GO term speculations from [GO-GPT](https://huggingface.co/wanglab/gogpt). Following the original BioReason-Pro reasoning pipeline, agents must reason about the protein's function and predict the correct set of GO terms. Scoring uses deterministic set-based F1, comparing predicted GO term IDs against ground truth annotations curated from UniProt with experimental evidence.

## Capabilities

- Protein function prediction via Gene Ontology term annotation
- Multimodal biological reasoning across sequence, domain, and interaction data
- Hierarchical classification across three GO aspects (Molecular Function, Biological Process, Cellular Component)

## Compute Requirements

Agents are given a standard environment with no sandbox or file system access.

## License

[Apache 2.0](https://opensource.org/licenses/Apache-2.0)

## Tasks

Tasks are organized into four splits:

| Split | Description | Tasks |
|-------|-------------|-------|
| `train` | All GO aspects combined | 9,197 |
| `mf` | Molecular Function predictions only | 4,914 |
| `bp` | Biological Process predictions only | 5,881 |
| `cc` | Cellular Component predictions only | 5,610 |

Each task provides the agent with protein ID, name, organism, sequence, subcellular location, InterPro domain annotations, protein-protein interaction partners, and initial GO term speculations from GO-GPT. Following the original BioReason-Pro reasoning template, agents are asked to reason about the protein's function and predict GO term IDs for the specified aspect(s).

## Reward Structure

This is a sparse, verifiable reward environment with deterministic scoring:

1. Agent receives protein information and the GO aspect(s) to predict
2. Agent replies with its predicted GO terms as an ordinary message
3. GO term IDs (pattern `GO:XXXXXXX`) are extracted from the whole reply
4. Set-based F1 is computed against ground truth:
   - Precision = |predicted ∩ truth| / |predicted|
   - Recall = |predicted ∩ truth| / |truth|
   - F1 = 2 * precision * recall / (precision + recall)
5. Continuous reward in [0, 1]

No LLM grader is used.

### Decoding strategy and choice of metric

This environment adopts **greedy decoding**, one of the decoding strategies outlined in the [BioReason-Pro paper](https://www.biorxiv.org/content/10.64898/2026.03.19.712954v1.full.pdf). Greedy decoding produces a single unranked set of GO terms per protein rather than a confidence-ranked list, so there is no per-term score to sweep a decision threshold over.

The reward metric is therefore the **F1 score without thresholding**: set-based F1 over exactly the terms the agent emitted, computed once. This is the operating point greedy decoding actually gives you, and it is what the numbers in this environment mean.

## Data

Data is sourced from the [wanglab/bioreason-pro-rl-reasoning-data](https://huggingface.co/datasets/wanglab/bioreason-pro-rl-reasoning-data) dataset containing 9,197 proteins with experimental GO annotations curated from UniProt. Each protein includes amino acid sequence, InterPro domain annotations, protein-protein interaction partners, and pre-computed GO-GPT predictions. Task data is stored on the OpenReward platform.

## Tools

Agents are given no visible tools. The environment uses a hidden `@terminal` tool: the agent's final plain-text message is the answer; GO term IDs are regex-extracted from the whole reply and set-F1-scored against the reference.

## Time Horizon

Single-turn. The agent replies with one plain-text message listing its GO term predictions.

## Environment Difficulty

BioReason-Pro model performance on GO term prediction, as reported in the paper (F_max):

| Model | F_max |
|-------|-------|
| BioReason-Pro RL (Qwen3-4B + ESM3 + GRPO) | 73.6% |

**Read the Qwen3-4B figure as an upper bound on what that model would score in this environment, not as a comparable baseline.** F_max is the best F1 attainable across a sweep of confidence thresholds — an operating point selected with hindsight over the whole evaluation set. Under the greedy decoding this environment adopts there is no threshold to tune, and the reward is the un-thresholded F1 of the single set the agent emits, which sits at or below F_max by construction. Expect a Qwen3-4B-class model to score somewhat under 73.6% here.

## Other Environment Requirements

There are no further environment requirements. BioReason-Pro uses deterministic F1 scoring and does not require any external API keys.

## Safety

Agents in BioReason-Pro answer protein function prediction questions in a standard environment. The environment does not provide tools for code execution, web access, or file system modification.

Protein function prediction is a dual-use capability. Accurate functional annotation of proteins could in principle be applied to characterize proteins involved in pathogenicity, toxin production, or antimicrobial resistance. However, the tasks in this environment operate on publicly available UniProt annotations and GO terms, and the predictions are limited to categorical ontology labels rather than actionable design instructions. The risk profile is comparable to querying existing protein databases.

## Citation

```bibtex
@article{fallahpour2026bioreason_pro,
  title={BioReason-Pro: Advancing Protein Function Prediction with Multimodal Biological Reasoning},
  author={Fallahpour, Adibvafa and Seyed-Ahmadi, Arman and Idehpour, Parsa and Ibrahim, Omar and Gupta, Purav and Naimer, Jack and Zhu, Kevin and Shah, Arnav and Ma, Shihao and Adduri, Abhinav and G{\"u}loglu, Talu and Liu, Nuo and Cui, Haotian and Jain, Arihant and de Castro, Max and Fallahpour, Amirfaham and Cembellin-Prieto, Antonio and Stiles, John S. and Nem{\v{c}}ko, Filip and Nevue, Alexander A. and Moon, Hyungseok C. and Sosnick, Lucas and Markham, Olivia and Duan, Haonan and Lee, Michelle Y. Y. and Salvador, Andrea F. M. and Maddison, Chris J. and Thaiss, Christoph A. and Ricci-Tam, Chiara and Plosky, Brian S. and Burke, Dave P. and Hsu, Patrick D. and Goodarzi, Hani and Wang, Bo},
  journal={bioRxiv},
  year={2026},
  doi={10.64898/2026.03.19.712954}
}
```
