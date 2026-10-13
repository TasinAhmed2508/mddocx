# Graphify and AI-provider setup

This repository uses Graphify to index and navigate the codebase. Graphify is
optional: the `mddocx` renderer itself does not need an AI API key, and it is
not a Python dependency of this package.

Examples below use PowerShell on Windows. On macOS and Linux the `graphify`
commands are identical; only environment variables differ (`export NAME=value`
instead of `$env:NAME = "value"`).

## Install Graphify

Graphify is an external CLI, so install it before running anything here. The
PyPI distribution is `graphifyy` (two y's) while the command is `graphify`:

```bash
uv tool install graphifyy      # or: pipx install graphifyy
uv tool install --upgrade graphifyy
```

A plain `pip install graphifyy` also works when you install into a managed
environment. `pip install graphify` installs an unrelated project.

Then register the assistant skill for the tool you use:

```bash
graphify install                 # default platform
```

This repository's graph was built with graphify 0.9.58; newer releases exist, so
check `graphify --version` and `graphify --help` for the flags your build has.

## Recommended workflow

The graph output lives in the git-ignored `graphify-out/` directory, so a fresh
clone starts without a graph and every `graphify query` fails until it is built
once. `graphify extract` is safe to re-run: it has no API cost with `--code-only`.

Run the local AST-only graph first. It is deterministic and has no API cost:

```powershell
graphify extract . --code-only --no-cluster --out .
graphify query "Where is compiler and CLI configuration handled?"
graphify god-nodes --top 12
```

After source changes, refresh the graph without an LLM:

```powershell
graphify update .
```

Use semantic extraction only when you need inferred relationships or community
names. The project graph is written to `graphify-out/`; do not put API keys in
that directory or commit them.

## Gemini setup

1. Create a Gemini API key in Google AI Studio.
2. Set it only in the current shell or in a local, ignored environment file:

```powershell
$env:GEMINI_API_KEY = "your-key"
graphify extract . --backend gemini --model gemini-2.5-flash --max-concurrency 2
```

The model flag is optional; use a model currently available to your Gemini
account. Google documents `GEMINI_API_KEY` as the standard environment variable.

## OpenAI setup

If an API key is accidentally pasted into chat, source control, a terminal
command, or a log, revoke it immediately and create a replacement. Never put
the replacement directly in this document or in a command that will be saved
in shell history.

Create an API key at the OpenAI API platform and set it in the current
PowerShell process. Replace the placeholder locally; do not commit the value:

```powershell
$env:OPENAI_API_KEY = "REPLACE_WITH_A_NEW_KEY"
graphify extract . --backend openai --model gpt-4.1-mini --max-concurrency 1 --token-budget 100000
```

For a persistent Windows setup, use the Windows user or system environment
variable UI, or a secrets manager. Avoid putting the key in a `.ps1` file or a
`.env` file unless that file is encrypted or ignored and protected with normal
secret-management controls.

Important: “GPT-6 Luna” and “GPT-5.6 Luna” are product labels, not confirmed
OpenAI API model identifiers for Graphify. Graphify 0.9.58 uses
`gpt-4.1-mini` as its built-in OpenAI default. Use that default unless the
OpenAI API models endpoint shows another exact identifier available to your
API project. A ChatGPT/Codex subscription does not automatically provide API
credits.

For a self-hosted OpenAI-compatible server:

```powershell
$env:OPENAI_BASE_URL = "http://localhost:8080/v1"
$env:OPENAI_MODEL = "the-model-served-by-your-server"
graphify extract . --backend openai --max-concurrency 1
```

## Token and cost estimate

Graphify's `--token-budget` is a per-chunk cap, not a guaranteed bill. Actual
billing depends on the extracted input, output, retries, model, and concurrency.
The basic estimate is:

```text
cost = (input_tokens / 1,000,000 × input_price)
     + (output_tokens / 1,000,000 × output_price)
```

Useful controls for keeping spend predictable:

```powershell
graphify extract . --backend gemini --token-budget 12000 --max-concurrency 1
graphify extract . --backend openai --token-budget 12000 --max-concurrency 1
```

For the current project, the already-run AST-only scan found 95 code files and
cost **$0** in API tokens. A semantic scan may process substantially less than
the raw repository because Graphify chunks and caches work, but the exact token
count must be read from the command output/provider dashboard.

Do not hard-code a price for “GPT-5.6 Luna” or “GPT-6 Luna” until that exact API
model appears on the OpenAI API pricing page. Product/Codex access and API
pricing are separate. Gemini has a free tier in eligible regions and paid
pricing by model/tier; check Google's live pricing page before budgeting.

## Security checklist

- Never commit `GEMINI_API_KEY`, `OPENAI_API_KEY`, or a provider token.
- Prefer a process-local environment variable or a secrets manager.
- Use `--code-only` for routine navigation and reserve semantic extraction for
  questions that need inferred relationships.
- Keep `--max-concurrency 1` while validating a new provider configuration.
- Review Graphify output before sharing it; it can contain source identifiers
  and code structure.

## Official references

- Gemini setup: https://ai.google.dev/gemini-api/docs/get-started
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- OpenAI API pricing: https://openai.com/api/pricing/
