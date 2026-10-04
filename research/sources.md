# MIRROR: Research Sources & Literature Review

Curated for the MIRROR Embodied AI Agent. Last updated: 2026-10-04.  
Curated reference list of literature informing the architecture and safety design.

---

## 1. Physical Affordances & Grounded Planning

### [1] Do As I Can, Not As I Say: Grounding Language in Robotic Affordances (SayCan)
* **Authors:** Michael Ahn, Anthony Brohan, Noah Brown, Yevgen Chebotar, Omar Cortes, Byron David, Chelsea Finn, Keerthana Gopalakrishnan, Karol Hausman, Alex Herzog, Daniel Ho, Jasmine Hsu, Julian Ibarz, Brian Ichter, Alex Irpan, Eric Jang, Rosario Jauregui Ruano, Kyle Jeffrey, Sally Jesmonth, Nikhil J Joshi, Ryan Julian, Dmitry Kalashnikov, Yuheng Kuang, Kuang-Huei Lee, Sergey Levine, Yao Lu, Linda Luu, Carolina Parada, Peter Pastor, Jornell Quiambao, Kanishka Rao, Jarek Rettinghouse, Diego Reyes, Pierre Sermanet, Nicolas Sievers, Clayton Tan, Alexander Toshev, Vincent Vanhoucke, Fei Xia, Ted Xiao, Peng Xu, Sichun Xu, Mengyuan Yan, Andy Zeng.
* **Citation:** *arXiv:2204.01691* (Google Research, Everyday Robots), 2022.
* **Core Insight:** Large language models know how to do many tasks abstractly, but cannot ground feasibility in the current physical state. SayCan pairs semantic probability $P(\text{task} \mid \text{goal})$ with affordance probability $P(\text{possible} \mid \text{state})$.
* **MIRROR Application:** Informs the affordance principle: before proposing any step, the world model checks scene prerequisites (e.g. required objects visible and accessible) rather than outputting ungrounded multi-step trajectories.

---

### [2] Inner Monologue: Embodied Reasoning through Planning with Language Models
* **Authors:** Wenlong Huang, Fei Xia, Ted Xiao, Harris Chan, Jacky Liang, Pete Florence, Andy Zeng, Jonathan Tompson, Igor Mordatch, Yevgen Chebotar, Pierre Sermanet, Noah Brown, Tomas Jackson, Linda Luu, Sergey Levine, Karol Hausman, Brian Ichter.
* **Citation:** *arXiv:2207.05608* (CoRL 2022 Oral).
* **Core Insight:** Closed-loop feedback (scene description, success detection, human input) injected back into language prompts significantly outperforms open-loop execution.
* **MIRROR Application:** Directly motivates MIRROR's closed-loop execution: `observe -> plan (1 step) -> act -> verify -> observe`. No multi-step plan is executed blindly without sensor verification after each action.

---

### [3] PaLM-E: An Embodied Multimodal Language Model
* **Authors:** Danny Driess, Fei Xia, Mehdi S. M. Sajjadi, Corey Lynch, Awtar Goyal, Peng Xu, Pierre Sermanet, Kanishka Rao, Niklas Karlsson, Karol Hausman, Alex Herzog, Brian Ichter, Andy Zeng, Florence Monti, Pete Florence.
* **Citation:** *arXiv:2303.03378* (ICML 2023).
* **Core Insight:** Multimodal language models that ingest continuous sensor observations can ground embodied reasoning across temporal sequences.
* **MIRROR Application:** Informs the separation between the perceptual observation layer (object labels and scene state) and the deterministic safety governor (`PolicyGate`).

---

## 2. Visual Verification & State Change Detection

### [4] Robust Change Captioning (DUDA)
* **Authors:** C. C. Park, T. Darrell, A. Rohrbach.
* **Citation:** *Robust Change Captioning* (ICCV 2019).
* **Core Insight:** Disentangling true semantic physical modifications from ambient camera noise, lighting shifts, and viewpoints requires explicit before/after feature comparison conditioned on scene anchors.
* **MIRROR Application:** MIRROR's verifier enforces anchor matching (desk/counter must match across before/after frames). If anchors cannot be verified, the outcome must strictly be `cannot_tell`, preventing false positives from perspective jitter.

---

## 3. Safety Policies & Human-in-the-Loop Safeguards

### [5] Safety and Robustness in Embodied AI and Robotic Assistants
* **Authors:** Dylan Hadfield-Menell, Anca Dragan, Pieter Abbeel, Stuart J. Russell.
* **Citation:** *Cooperative Inverse Reinforcement Learning* (NeurIPS 2016) & *The Off-Switch Game* (IJCAI 2017).
* **Core Insight:** Autonomous agents operating in human environments must maintain uncertainty regarding user preferences and defer authority whenever actions carry high entropy or irreversible physical hazards.
* **MIRROR Application:** Foundational to MIRROR's safety tiers: `A0` Autonomous, `A1` Reversible, `A2` Explicit Confirmation, `A3` Default Deny. Physical actions involving heat, cutting tools, or ladders strictly require human confirmation; high-voltage or structural tasks are refused unconditionally.

---

## 4. Verification Benchmarking

### [6] Hallucination Benchmarks in Vision-Language Models
* **Authors:** Yifan Li, Yifan Du, Kun Zhou, Ji-Rong Wen, Xin Zhao.
* **Citation:** *Evaluating Object Hallucination in Large Vision-Language Models* (EMNLP 2023 / POPE benchmark).
* **Core Insight:** Modern VLMs hallucinate object presence when negative prompt controls and rigorous confidence thresholds are not strictly enforced.
* **MIRROR Application:** Direct rationale for MIRROR's core rule: **"No task is marked complete unless empirical verification confirms the result."** The app never relies on model self-reported confidence alone; expected evidence tokens must be physically visible in fresh frames with backend confidence $\ge 0.85$.
