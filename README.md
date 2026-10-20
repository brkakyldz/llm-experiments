<p align="center"><img src="assets/banner.jpg" alt="llm experiments: small experiments on how LLM agents behave at work, graded on the trace as well as the reply" width="100%"></p>

<p align="center">
  <img src="https://img.shields.io/badge/experiments-2-B3C3D8?style=flat-square&labelColor=253F66" alt="2 experiments">
  <img src="https://img.shields.io/badge/runs-real_model_calls-B3C3D8?style=flat-square&labelColor=253F66" alt="real model calls">
  <img src="https://img.shields.io/badge/replay-offline,_no_key-B3C3D8?style=flat-square&labelColor=253F66" alt="offline replay">
  <img src="https://img.shields.io/badge/license-MIT-B3C3D8?style=flat-square&labelColor=253F66" alt="MIT license">
</p>

Small experiments on how LLM agents behave when they do real work: calling tools, changing state,
and reporting back what they did. Each folder is one experiment with its code, every recorded run,
a viewer for the traces, and a write-up of what happened, including what did not go as expected.

## Experiments

<a href="explanation-sways-judge/"><img src="assets/cards/explanation-sways-judge.jpg" width="100%" alt="explanation-sways-judge: the wrong reply W18 passed 3 of 3 bare and failed 3 of 3 with its explanation; across 40 replies wrong replies passed 30% bare and 17% explained, correct replies 32% and 85%"></a>

**[explanation-sways-judge](explanation-sways-judge/)** · 2026-10-19 · Does an LLM judge pass wrong
answers more often when they come with a fluent explanation? Not this judge. Over 240 calls on 40
support replies, wrong replies passed less often with the agent's explanation (17% against 30%)
and correct ones far more often (85% against 32%): the explanation wrote out the dates and amounts
the judge otherwise miscounted. It still talked the judge into 2 of 20 wrong replies.
[Write-up](explanation-sways-judge/) ·
[trace viewer](https://brkakyldz.github.io/llm-experiments/explanation-sways-judge/trace-viewer.html)

<br>

<a href="said-vs-did/"><img src="assets/cards/said-vs-did.jpg" width="100%" alt="said-vs-did: the final reply the judge passed 7/10 next to the trace, where a plain-code rule caught the leak of another customer's order"></a>

**[said-vs-did](said-vs-did/)** · 2026-10-15 · Does grading only an agent's final reply miss what
it did along the way? A support agent correctly refused a refund on someone else's order, and named
what was inside that order. An LLM judge reading the reply passed it with 7/10; a plain-code check
over the trace caught the leak.
[Write-up](said-vs-did/) ·
[trace viewer](https://brkakyldz.github.io/llm-experiments/said-vs-did/trace-viewer.html)

## How these experiments are run

| | |
|---|---|
| **Real runs only** | Every trace in this repo comes from a real model call. Nothing in an agent's path is scripted; the code runs whatever tools the model asks for. |
| **Every run is kept** | A folder reports all of its runs, including pilots and the runs where nothing interesting happened. |
| **The plan comes first** | The hypothesis, the rules and the run plan are written down before the first live run, in each folder's `docs/design.md`. Changes made after seeing results are listed in the write-up. |
| **Plain code wherever it can grade** | State changes, tool calls and their order are checked with deterministic code. An LLM is used only where reading language is unavoidable, and its output is stored in the trace. |
| **Replay without a key** | `python run.py --replay` re-scores the saved traces offline, so anyone can check the numbers without an API key. |

## Layout

```
explanation-sways-judge/   one experiment: code, traces/, results/, docs/, assets/, trace-viewer.html, README.md
said-vs-did/               one experiment, same shape
assets/                    banner and experiment cards for this page; sources in assets/src/
```

Each experiment folder is self-contained: it shares no code with the others and runs on its own.
This page's images are HTML and CSS under `assets/src/`, rendered with
`python assets/src/render.py` (Playwright, on Windows for its system fonts). The small robot
avatar was made with an image model; every word and number in the images is text from the
experiments' READMEs.

MIT licensed, see [LICENSE](LICENSE).
