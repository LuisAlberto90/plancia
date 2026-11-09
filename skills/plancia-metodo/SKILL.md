---
name: plancia-metodo
description: How to approach any request in a code project with the least work and tokens - pick the right path (answer, small fix, planned change, parallel analysis), explore on a budget, avoid loops, verify before saying done. Use at the start of every coding task, question about the codebase, analysis, bug fix or refactor.
---

# Plancia method: the shortest correct path

Reply in the user's language.

## 0. Context first (saves the most tokens)
- If `.factory/CONTESTO.md` exists, read it first. Do not re-discover what it already says (stack, commands, modules, tests, big files).
- If it is missing and the task needs exploring, suggest once: `plancia contesto --scrivi`.
- Read project rules (AGENTS.md / CLAUDE.md / copilot-instructions) only if not already loaded.

## 1. Pick the path (decide in one line, then act)
| Request | Path |
|---|---|
| Question / explanation / "where is X" | Answer directly. Read only what the answer needs. No plan, no files written. |
| Small fix (1-2 files, clear intent) | Do it → run the narrowest check → report. |
| Change across several files or behaviour | Plan of max 7 short steps → wait for the user's OK → implement in order → targeted tests → report. |
| Independent areas to read/analyse (e.g. 3 modules) | One subagent per area, in parallel, each with a narrow brief and a max length for its answer. Then merge. Never use subagents for edits to the same files. |
| Ambiguous request | Ask ONE closed question (2-3 options), the one that removes most uncertainty. Max 3 questions, then say what you assume. |
| A list of unrelated requests | It is N tasks: ask which first. |

Never ask for things the code can tell you (file names, signatures): find them.

## 1b. Write the plan on the Plancia (every request except a pure question)
The user watches the plan as a graph. It is your FIRST action, before reading files:
`plancia piano nuovo "<short title>" "A: <step>" "B: <step> <- A" "C: <step> <-" "D: <step> <- B,C"`
The Plancia scores the plan (0-10) and tells you what to fix: if it says "Improve it now", rewrite it once with `piano nuovo --new`.

How to write a plan that scores 8+:
- Ground it in the project: take module names, paths and build/test commands from `.factory/CONTESTO.md`. Never invent names you have not seen.
- One step = ONE action on ONE exact object, with a check: `<verb> <file | module | command> => <how you know it is done>`.
  Good: "B: Baseline: `cd orders-api && mvn test` => record pass/fail counts". Bad: "B: Run tests", "Analyze backend", "Fix issues".
- No placeholders: never "TBD", "etc.", "handle edge cases", "as needed". Spell it out or drop it.
- Size: 3-5 steps for analysis, 6-12 for a change. A step a reviewer could accept or reject on its own.
- For a change always include: baseline build/tests BEFORE the first edit; one step per file changed (name it); one step for callers/config that use what you change (found with grep); docs if they mention it; final verification `=> same counts as baseline`; summary.
- Parallel work: steps that do not need each other's output get `<-` alone (or `<- A` for a shared prerequisite), so they show as branches. Never chain independent areas (BE and FE, module X and Y).
- Scope check: if the request covers unrelated subsystems, say so and plan the first one; ask before the others.

Executing:
- `plancia passo B` when you start B; `plancia passo B fatto "<result: numbers, files>"`; `plancia passo C errore "<cause>"`; `plancia passo D saltato "<why>"`. One `plancia` call per command line, never hidden inside long commands. Close EVERY step.
- New work discovered mid-way: `plancia piano aggiungi "E: <step> <- B"`; never rewrite finished steps.
- Sub-agents: when you delegate a branch, tell the sub-agent "do not call plancia, do not write a plan" and mark that branch's steps yourself when it returns. If you ARE a sub-agent (your prompt came from another agent), never create a plan.
- If `plancia` is not installed, skip this section silently. Never spend more than one line of output on it.
- Edit files with the editor tool, not with shell scripts (python/sed/echo >): edits stay visible to the user and to the guards.

## 2. Minimal solution ladder (stop at the first step that holds)
1. Is it really needed? Speculative → skip it, say so in one line.
2. Standard library? 3. Native platform feature? 4. Dependency already installed?
5. One line? 6. Only then: the minimum that works.
No unrequested abstractions, no scaffolding "for later", shortest working diff, delete rather than add.
Never simplify away: input validation at trust boundaries, error handling that prevents data loss, security, explicit requirements, tests for changed public behaviour.

## 3. Exploration budget
- Stop exploring as soon as you can make the change or give the answer.
- Never re-read a file already read in this session. Big files: grep, then read only the needed range.
- A search that returns nothing: at most one different attempt, then change hypothesis or ask.
- Filter long command output (grep for FAIL/ERROR/summary) instead of reading it all.

## 4. Anti-loop rules (hard)
- Same error twice with the same approach → stop, change approach or explain and ask. Never a third identical try.
- Max 3 fix attempts on one failure; then report what you tried and the best next step.
- Do not repeat a command that already gave the same result. Do not "check again" without a change in between.
- Environment problems (missing tool, service down, credentials) are not code bugs: report them, do not work around them.

## 5. Verify before "done"
- Evidence, not claims: the command you ran and its result (exit code, tests passed/failed, row counts).
- Test the perimeter you touched first, wider suite only if needed. Out-of-perimeter failures are notes, not your failure.
- Never commit, push, or touch protected files (.env, keys, .git); if the Plancia denies an action, do not work around it.

## 6. Close with a traffic light (one line, always)
`🟢 DONE — <what changed / the answer> → next: <one step or "nothing">`
`🟡 PARTIAL — <done> / <not verified and why> → next: <step>`
`🔴 BLOCKED — <cause> → needed from you: <one action>`
Keep the rest short: result first, then at most 3 lines on what you skipped and when to add it.
