# Research agent

## Objective

Add a current-research layer to the development flow without turning the researcher model into the one that writes code.

Research must answer questions like:

- What is the correct API/version today?
- What changed in a library/framework?
- Is there a known vulnerability or breaking change?
- What does the official documentation recommend for a concrete case?
- What alternatives exist and what are their trade-offs?
- Which current platform restrictions may affect the design?

The researcher delivers evidence to the building agent. The builder decides whether that evidence justifies a change, and any behavior change still goes through spec/plan/approval.

## Recommended integration with OpenCode

OpenCode supports subagents defined in `.opencode/agents/` with controlled permissions. The researcher included here has no edit or shell permissions; web research only.

In current OpenCode documentation, `websearch` and `webfetch` are available as research tools; `websearch` does not require its own API key when enabled through OpenCode's compatible infrastructure. To enable it when starting OpenCode in PowerShell:

```powershell
$env:OPENCODE_ENABLE_EXA="1"
opencode
```

It can then be invoked manually with:

```text
@researcher investigate ...
```

## Google Gemini API: optional

I do not recommend turning Gemini into the coding agent. It can be useful as an **additional research source**, especially for grounding with Google Search.

As of 2026-10-06, Gemini documentation states that certain models have a free input/output quota and that Gemini 2.5 Flash-Lite offers free Google Search grounding of up to 500 requests per day on the free tier. Quotas depend on project/model and may change.

The free tier also states that content may be used to improve Google products. Therefore, for private repositories or sensitive information, the researcher must not automatically send complete code or secrets to Gemini.

The API key must live outside the repository, for example in `GEMINI_API_KEY`, and never in code, `VITE_*`, versioned prompts or commits.

## Recommended decision

For this reusable base, keep **OpenCode + websearch/webfetch** as the default path: simpler, no mandatory credential, and provider-agnostic.

Add Gemini only as an optional integration when it genuinely adds a verifiable coverage or Google Search grounding advantage.
