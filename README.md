# week1-demo-app
Week 1 - Demo App
=======
# Customer Discovery

A single-page Streamlit app with Customer Profile, Fraud Vectors, Product
Positioning, and Similar Customers tabs. The last two display “Coming soon...”.
Discovery uses either local Ollama or OpenRouter and keeps results only in the
current browser session. Optional Tavily web search retrieves current excerpts
before either model generates its brief. Retrieved source links and excerpts appear
above the tabs; the model is instructed to cite their numbered IDs. Results still
need validation and potential fraud vectors are hypotheses, not allegations.

## Run locally

Python 3.11 is recommended (Python 3.9+ supported).

```sh
cd week1_demo_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

On Windows activate with `.venv\Scripts\activate`. Open http://localhost:8501.

### Ollama

Install [Ollama](https://ollama.com), then run:

```sh
ollama pull llama3.2:latest
ollama serve
```

If the Ollama desktop app already serves the API, a second server is unnecessary.
Leave `LOCAL=true` in `.env`. Change `OLLAMA_MODEL` to use another installed model.

### OpenRouter

Set these values in `.env`, then restart Streamlit:

```dotenv
LOCAL=false
OPENROUTER_API_KEY=your-real-key
OPENROUTER_MODEL=your-chosen-provider/model-id
```

Choose an available model that supports JSON object output from the
[OpenRouter model catalog](https://openrouter.ai/models).
Credentials stay on the server and are never shown in the UI.

## Web search (Ollama and OpenRouter)

Create a [Tavily API key](https://app.tavily.com), then add it to your existing
`.env` (do not overwrite your model configuration):

```dotenv
WEB_SEARCH_ENABLED=true
TAVILY_API_KEY=your-tavily-api-key
SEARCH_MAX_RESULTS=5
SEARCH_TIMEOUT=30
```

Leave **Search the web** checked when running discovery. The app makes one basic
Tavily search per run using the customer name, website domain, and business-profile
terms. It passes up to five excerpts (1,800 characters each by default) to either
Ollama or OpenRouter. It does not crawl the full website. Source numbers such as
[1] in the generated brief refer to the displayed source list; citations are
model-generated and their factual support is not automatically verified.

Ollama inference stays local, but searching requires internet access and sends the
query to Tavily. With OpenRouter, retrieved excerpts also go to the selected LLM
provider. Search API usage is subject to your Tavily plan. No extra Python package
is needed. See the [Tavily Search API documentation](https://docs.tavily.com/documentation/api-reference/endpoint/search).

Missing keys, search errors, and empty results stop discovery with an actionable
message; the app never silently presents an offline answer as researched. Uncheck
**Search the web** to run without search, or set `WEB_SEARCH_ENABLED=false` as the
default. For cloud hosting, add `TAVILY_API_KEY` to Streamlit/Replit secrets too.
Existing private prompts should allow supplied web excerpts and source citations;
remove old instructions that say web research is unavailable.

## Configuration

`config.toml` has a `local` flag, separate `[ollama]` and `[openrouter]` sections,
and `[prompts]` with editable System Prompt and User Prompt templates.
API keys are referenced by environment variable name, never stored in this file.

Precedence: deployment environment > `.env` > `config.toml` defaults.

| Variable | Purpose |
| --- | --- |
| `LOCAL` | `true` for Ollama, `false` for OpenRouter |
| `OLLAMA_MODEL`, `OPENROUTER_MODEL` | Provider-specific model names |
| `MODEL_NAME` | Optional override for whichever provider is active |
| `OLLAMA_BASE_URL`, `OPENROUTER_BASE_URL` | Provider server addresses |
| `OLLAMA_API_KEY`, `OPENROUTER_API_KEY` | Optional Ollama / required OpenRouter credential |
| `SYSTEM_PROMPT`, `USER_PROMPT` | Optional private prompt overrides |
| `WEB_SEARCH_ENABLED` | Default state of the Search the web checkbox |
| `TAVILY_API_KEY` | Search credential shared by both LLM modes |
| `SEARCH_MAX_RESULTS` | Source limit, 1–10; default 5 |
| `SEARCH_TIMEOUT` | Search read timeout, 1–120 seconds; default 30 |
| `REQUEST_TIMEOUT` | Read timeout in seconds, 1–600; default 120 |

User Prompt tokens: `{customer_name}` and `{website_url}`. Other braces are
preserved, so templates can include JSON. The application appends the customer
inputs and a fixed JSON response contract. Responses must contain a Markdown `customer_profile`, a `fraud_vectors` array
of objects with `vector`, `description`, `impact`, `signals`, and `mitigation`
string fields, and a separate `questions` array of strings. The app renders
fraud vectors as a wrapped, striped table and questions as numbered cards below
it. On narrow screens the table scrolls horizontally. Run discovery again to
replace any old session results with the new format.

Use quoted multiline values in `.env` for longer private prompts. Restart after
changing deployment environment variables. Do not put secrets in tracked prompts.

## GitHub and Streamlit Community Cloud

Use this folder as your repository root, or keep it as a subdirectory and select
`week1_demo_app/app.py` as the entrypoint. GitHub stores source; GitHub Pages cannot
run this Python server.

1. Upload the project files to a GitHub repository. `.gitignore` excludes `.env`,
   `.env.*` (except `.env.example`), virtual environments, and Streamlit secrets.
2. In Streamlit Community Cloud, select the repository and `app.py` entrypoint
   (or the subdirectory path above), using Python 3.11.
3. In the app's Secrets settings add top-level TOML values:

   ```toml
   LOCAL = "false"
   OPENROUTER_API_KEY = "your-real-key"
   OPENROUTER_MODEL = "your-chosen-provider/model-id"
   ```

Streamlit exposes these top-level secrets as environment variables. Never commit
`.streamlit/secrets.toml`. Before your first push, inspect `git status` and confirm
no private values were put in tracked files. Ignore rules do not untrack files
already committed.

## Replit

Import the GitHub repository with this project's files at the repository root.
The included `.replit` uses Python 3.11, listens on `0.0.0.0:8501`, and maps it to
external port 80.

1. Run `python -m pip install -r requirements.txt` in the Shell.
2. Add `LOCAL=false`, `OPENROUTER_API_KEY`, and `OPENROUTER_MODEL` in Replit Secrets.
3. Click Run to preview; publish using a Reserved VM deployment. The deployment
   build and run commands are included in `.replit`.

Cloud deployments cannot reach Ollama on your laptop through `localhost`. Use
OpenRouter for hosting, or configure a secured, reachable Ollama endpoint.
This demo has no authentication or per-user usage quotas: restrict deployment
access before sharing a server-funded API key with a wider audience.

## Verification

```sh
python -m unittest discover -s tests -v
```

Tests mock provider requests, so they do not require API keys or spend credits.
For a live smoke test, configure a provider, enter a customer and URL, and confirm
both discovery tabs populate. Provider errors and invalid responses are displayed
as actionable messages; failed runs clear the previous brief.

## API references

- [Ollama chat API](https://docs.ollama.com/api/chat)
- [OpenRouter chat completions](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request)
- [Streamlit deployment secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
- [Replit configuration](https://docs.replit.com/features/project-setup/configuration)

### Response format recovery

Ollama requests include a JSON schema for the profile, fraud rows, and questions.
OpenRouter retains JSON-object mode for compatibility, with the schema included
in the prompt. If the model returns an invalid structure, the app makes at most
one additional LLM call to repair it using the original context and sources.
Web search is not repeated. This may add latency and, with OpenRouter, token
cost. Provider connection, authentication, and HTTP errors are not retried.
>>>>>>> e2b2d43 (Initial commit)
