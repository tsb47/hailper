"""HTTP clients for the supported LLM providers.

Only the Python standard library is used so the extension works with whatever
interpreter LibreOffice ships, without requiring pip packages.
"""

import json
import socket
import time
import urllib.error
import urllib.request

_RETRY_CODES = (429, 500, 502, 503, 504)
_RETRY_ATTEMPTS = 3


class ProviderError(Exception):
    """Raised for any recoverable problem talking to a provider."""


def _retryable(error):
    if isinstance(error, urllib.error.HTTPError):
        return error.code in _RETRY_CODES
    return isinstance(error, (urllib.error.URLError, socket.timeout))


# protocol is one of: "openai", "anthropic", "gemini", "ollama"
#
# Almost every commercial provider now exposes an OpenAI-compatible
# /chat/completions endpoint, so they all share the "openai" protocol and only
# differ by base URL and default model.
PROVIDERS = {
    "ollama": {
        "label": "Ollama (local)",
        "protocol": "ollama",
        "base_url": "http://localhost:11434",
        "default_model": "llama3.2:3b",
        "requires_key": False,
        "models": ["qwen3:4b", "llama3.2:3b", "gemma3:1b", "mistral", "phi4"],
    },
    "openai": {
        "label": "OpenAI",
        "protocol": "openai",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "requires_key": True,
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o4-mini"],
    },
    "deepseek": {
        "label": "DeepSeek",
        "protocol": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "requires_key": True,
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "qwen": {
        "label": "Qwen (Alibaba DashScope)",
        "protocol": "openai",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "requires_key": True,
        "models": [
            "qwen-plus",
            "qwen-max",
            "qwen-turbo",
            "qwen3-235b-a22b",
            "qwen2.5-72b-instruct",
        ],
    },
    "grok": {
        "label": "xAI Grok",
        "protocol": "openai",
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-3-mini",
        "requires_key": True,
        "models": ["grok-3-mini", "grok-3", "grok-2-1212", "grok-beta"],
    },
    "claude": {
        "label": "Anthropic Claude",
        "protocol": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-20250514",
        "requires_key": True,
        "models": [
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-opus-latest",
        ],
    },
    "gemini": {
        "label": "Google Gemini",
        "protocol": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "gemini-2.0-flash",
        "requires_key": True,
        "models": ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-pro"],
    },
    "openrouter": {
        "label": "OpenRouter",
        "protocol": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "requires_key": True,
        "models": [],
    },
    "custom": {
        "label": "Custom OpenAI-compatible",
        "protocol": "openai",
        "base_url": "",
        "default_model": "",
        "requires_key": False,
        "models": [],
    },
}

# Additional providers mirroring the catalogue OpenCode supports. Nearly all of
# them speak the OpenAI-compatible /chat/completions protocol and only differ by
# base URL, so they are added here as presets (the user still supplies the key).
PROVIDERS.update({
    "lmstudio": {
        "label": "LM Studio (local)",
        "protocol": "openai",
        "base_url": "http://127.0.0.1:1234/v1",
        "default_model": "",
        "requires_key": False,
        "models": [],
    },
    "llamacpp": {
        "label": "llama.cpp server (local)",
        "protocol": "openai",
        "base_url": "http://127.0.0.1:8080/v1",
        "default_model": "",
        "requires_key": False,
        "models": [],
    },
    "atomic": {
        "label": "Atomic Chat (local)",
        "protocol": "openai",
        "base_url": "http://127.0.0.1:1337/v1",
        "default_model": "",
        "requires_key": False,
        "models": [],
    },
    "llmgateway": {
        "label": "LLM Gateway (local)",
        "protocol": "openai",
        "base_url": "http://localhost:4001/v1",
        "default_model": "",
        "requires_key": False,
        "models": [],
    },
    "azure": {
        "label": "Azure OpenAI",
        "protocol": "azure",
        "base_url": "",
        "default_model": "gpt-4o-mini",
        "requires_key": True,
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
    },
    "groq": {
        "label": "Groq",
        "protocol": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "requires_key": True,
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                   "qwen/qwen3-32b", "moonshotai/kimi-k2-instruct"],
    },
    "mistral": {
        "label": "Mistral",
        "protocol": "openai",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-large-latest",
        "requires_key": True,
        "models": ["mistral-large-latest", "mistral-medium-latest",
                   "mistral-small-latest", "codestral-latest"],
    },
    "cerebras": {
        "label": "Cerebras",
        "protocol": "openai",
        "base_url": "https://api.cerebras.ai/v1",
        "default_model": "llama-3.3-70b",
        "requires_key": True,
        "models": ["llama-3.3-70b", "qwen-3-coder-480b", "gpt-oss-120b"],
    },
    "together": {
        "label": "Together AI",
        "protocol": "openai",
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "requires_key": True,
        "models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo",
                   "Qwen/Qwen2.5-72B-Instruct-Turbo",
                   "deepseek-ai/DeepSeek-V3"],
    },
    "fireworks": {
        "label": "Fireworks AI",
        "protocol": "openai",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "requires_key": True,
        "models": ["accounts/fireworks/models/llama-v3p3-70b-instruct",
                   "accounts/fireworks/models/deepseek-v3",
                   "accounts/fireworks/models/qwen3-235b-a22b"],
    },
    "perplexity": {
        "label": "Perplexity",
        "protocol": "openai",
        "base_url": "https://api.perplexity.ai",
        "default_model": "sonar",
        "requires_key": True,
        "models": ["sonar", "sonar-pro", "sonar-reasoning"],
    },
    "cohere": {
        "label": "Cohere",
        "protocol": "openai",
        "base_url": "https://api.cohere.ai/compatibility/v1",
        "default_model": "command-r-plus",
        "requires_key": True,
        "models": ["command-r-plus", "command-r", "command-a-03-2025"],
    },
    "deepinfra": {
        "label": "Deep Infra",
        "protocol": "openai",
        "base_url": "https://api.deepinfra.com/v1/openai",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "requires_key": True,
        "models": [],
    },
    "baseten": {
        "label": "Baseten",
        "protocol": "openai",
        "base_url": "https://inference.baseten.co/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "nvidia": {
        "label": "NVIDIA NIM",
        "protocol": "openai",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "meta/llama-3.3-70b-instruct",
        "requires_key": True,
        "models": ["meta/llama-3.3-70b-instruct",
                   "qwen/qwen2.5-coder-32b-instruct"],
    },
    "moonshot": {
        "label": "Moonshot (Kimi)",
        "protocol": "openai",
        "base_url": "https://api.moonshot.ai/v1",
        "default_model": "kimi-k2-0711-preview",
        "requires_key": True,
        "models": ["kimi-k2-0711-preview", "moonshot-v1-128k"],
    },
    "minimax": {
        "label": "MiniMax",
        "protocol": "openai",
        "base_url": "https://api.minimax.io/v1",
        "default_model": "MiniMax-M2",
        "requires_key": True,
        "models": ["MiniMax-M2", "MiniMax-Text-01"],
    },
    "zai": {
        "label": "Z.AI (GLM)",
        "protocol": "openai",
        "base_url": "https://api.z.ai/api/paas/v4",
        "default_model": "glm-4.6",
        "requires_key": True,
        "models": ["glm-4.6", "glm-4.5", "glm-4.5-air"],
    },
    "huggingface": {
        "label": "Hugging Face",
        "protocol": "openai",
        "base_url": "https://router.huggingface.co/v1",
        "default_model": "moonshotai/Kimi-K2-Instruct",
        "requires_key": True,
        "models": ["moonshotai/Kimi-K2-Instruct", "zai-org/GLM-4.6"],
    },
    "nebius": {
        "label": "Nebius Token Factory",
        "protocol": "openai",
        "base_url": "https://api.studio.nebius.ai/v1",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "requires_key": True,
        "models": [],
    },
    "scaleway": {
        "label": "Scaleway Generative APIs",
        "protocol": "openai",
        "base_url": "https://api.scaleway.ai/v1",
        "default_model": "llama-3.3-70b-instruct",
        "requires_key": True,
        "models": [],
    },
    "ovhcloud": {
        "label": "OVHcloud AI Endpoints",
        "protocol": "openai",
        "base_url": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
        "default_model": "Meta-Llama-3_3-70B-Instruct",
        "requires_key": True,
        "models": [],
    },
    "vercel": {
        "label": "Vercel AI Gateway",
        "protocol": "openai",
        "base_url": "https://ai-gateway.vercel.sh/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "digitalocean": {
        "label": "DigitalOcean",
        "protocol": "openai",
        "base_url": "https://inference.do-ai.run/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "cortecs": {
        "label": "Cortecs",
        "protocol": "openai",
        "base_url": "https://api.cortecs.ai/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "gmi": {
        "label": "GMI Cloud",
        "protocol": "openai",
        "base_url": "https://api.gmi-serving.com/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "ionet": {
        "label": "IO.NET",
        "protocol": "openai",
        "base_url": "https://api.intelligence.io.solutions/api/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "venice": {
        "label": "Venice AI",
        "protocol": "openai",
        "base_url": "https://api.venice.ai/api/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "zenmux": {
        "label": "ZenMux",
        "protocol": "openai",
        "base_url": "https://zenmux.ai/api/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "poolside": {
        "label": "Poolside",
        "protocol": "openai",
        "base_url": "https://inference.poolside.ai/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "stackit": {
        "label": "STACKIT",
        "protocol": "openai",
        "base_url": "https://api.openai-compat.model-serving.eu01.onstackit.cloud/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "302ai": {
        "label": "302.AI",
        "protocol": "openai",
        "base_url": "https://api.302.ai/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "edenai": {
        "label": "Eden AI",
        "protocol": "openai",
        "base_url": "https://api.edenai.run/v3",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "ollamacloud": {
        "label": "Ollama Cloud",
        "protocol": "openai",
        "base_url": "https://ollama.com/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "opencode": {
        "label": "OpenCode Zen",
        "protocol": "openai",
        "base_url": "https://opencode.ai/zen/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
})

# Remaining OpenCode-catalogue providers that are reachable with a simple key.
PROVIDERS.update({
    "frogbot": {
        "label": "FrogBot",
        "protocol": "openai",
        "base_url": "https://api.frogbot.ai/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "helicone": {
        "label": "Helicone AI Gateway",
        "protocol": "openai",
        "base_url": "https://ai-gateway.helicone.ai/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "scx": {
        "label": "SCX.ai",
        "protocol": "openai",
        "base_url": "https://api.scx.ai/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "cloudflareworkers": {
        "label": "Cloudflare Workers AI",
        "protocol": "openai",
        "base_url": "https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/v1",
        "default_model": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        "requires_key": True,
        "models": [],
    },
    "cloudflaregateway": {
        "label": "Cloudflare AI Gateway",
        "protocol": "openai",
        "base_url": "https://gateway.ai.cloudflare.com/v1/ACCOUNT_ID/GATEWAY_ID/compat",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "azurecognitive": {
        "label": "Azure Cognitive Services",
        "protocol": "azure",
        "base_url": "",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
    "modal": {
        "label": "Modal (shared endpoint)",
        "protocol": "openai",
        "base_url": "https://WORKSPACE--ENDPOINT.modal.run/v1",
        "default_model": "",
        "requires_key": True,
        "models": [],
    },
})


def provider_ids():
    return list(PROVIDERS.keys())


def provider_spec(provider_id):
    return PROVIDERS.get(provider_id)


def _http_post_json(url, payload, headers, timeout):
    body = json.dumps(payload).encode("utf-8")
    delay = 1.0
    last_error = None
    for attempt in range(_RETRY_ATTEMPTS):
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        for key, value in headers.items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as error:
            if _retryable(error) and attempt < _RETRY_ATTEMPTS - 1:
                last_error = error
                time.sleep(delay)
                delay *= 2
                continue
            detail = error.read().decode("utf-8", "replace")
            raise ProviderError(_friendly_http_error(error.code, detail))
        except urllib.error.URLError as error:
            if attempt < _RETRY_ATTEMPTS - 1:
                last_error = error
                time.sleep(delay)
                delay *= 2
                continue
            raise ProviderError("Could not reach the server: %s" % error.reason)
        except socket.timeout:
            if attempt < _RETRY_ATTEMPTS - 1:
                last_error = "timeout"
                time.sleep(delay)
                delay *= 2
                continue
            raise ProviderError("The request timed out.")
    else:
        raise ProviderError("The request failed after retries: %s" % last_error)
    try:
        return json.loads(raw)
    except ValueError:
        raise ProviderError("The server returned a non-JSON response: %s" % raw[:300])


def _friendly_http_error(code, detail):
    message = detail.strip()
    try:
        parsed = json.loads(detail)
        if isinstance(parsed, dict):
            err = parsed.get("error")
            if isinstance(err, dict) and err.get("message"):
                message = err["message"]
            elif isinstance(err, str):
                message = err
            elif parsed.get("message"):
                message = parsed["message"]
    except ValueError:
        pass
    if code == 401:
        return "Authentication failed (401). Check your API key.\n%s" % message[:500]
    if code == 403:
        return "Access denied (403). Check your key and model permissions.\n%s" % message[:500]
    if code == 404:
        return "Endpoint or model not found (404). Check the base URL and model name.\n%s" % message[:500]
    if code == 429:
        return "Rate limit or quota exceeded (429).\n%s" % message[:500]
    return "HTTP %s: %s" % (code, message[:600])


def _openai_messages(messages, system):
    prepared = []
    if system:
        prepared.append({"role": "system", "content": system})
    prepared.extend(messages)
    return prepared


def _parse_openai(data):
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise ProviderError("Unexpected OpenAI-style response: %s" % json.dumps(data)[:300])


def _parse_anthropic(data):
    parts = data.get("content") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    if not text:
        raise ProviderError("Unexpected Anthropic response: %s" % json.dumps(data)[:300])
    return text


def _parse_gemini(data):
    candidates = data.get("candidates") or []
    if not candidates:
        feedback = data.get("promptFeedback") or {}
        raise ProviderError(
            "Gemini returned no candidates. %s" % json.dumps(feedback)[:300]
        )
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    return text


def _mk_usage(prompt_tokens, completion_tokens):
    if prompt_tokens is None and completion_tokens is None:
        return None
    return {"input": int(prompt_tokens or 0), "output": int(completion_tokens or 0)}


def _usage_openai(data):
    usage = data.get("usage") or {}
    return _mk_usage(usage.get("prompt_tokens"), usage.get("completion_tokens"))


def _usage_anthropic(data):
    usage = data.get("usage") or {}
    return _mk_usage(usage.get("input_tokens"), usage.get("output_tokens"))


def _usage_gemini(data):
    meta = data.get("usageMetadata") or {}
    return _mk_usage(meta.get("promptTokenCount"), meta.get("candidatesTokenCount"))


def _usage_ollama(data):
    return _mk_usage(data.get("prompt_eval_count"), data.get("eval_count"))


def _chat_openai(base_url, api_key, model, messages, system, temperature, max_tokens, timeout):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    payload = {
        "model": model,
        "messages": _openai_messages(messages, system),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = _http_post_json(url, payload, headers, timeout)
    return _parse_openai(data), _usage_openai(data)


def _chat_anthropic(base_url, api_key, model, messages, system, temperature, max_tokens, timeout):
    url = base_url.rstrip("/") + "/messages"
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        payload["system"] = system
    data = _http_post_json(url, payload, headers, timeout)
    return _parse_anthropic(data), _usage_anthropic(data)


def _chat_gemini(base_url, api_key, model, messages, system, temperature, max_tokens, timeout):
    url = "%s/models/%s:generateContent" % (base_url.rstrip("/"), model)
    headers = {"x-goog-api-key": api_key}
    contents = []
    for message in messages:
        role = "user" if message.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": message.get("content", "")}]})
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    data = _http_post_json(url, payload, headers, timeout)
    return _parse_gemini(data), _usage_gemini(data)


def _chat_azure(base_url, api_key, model, messages, system, temperature, max_tokens, timeout):
    url = base_url.rstrip("/") + "/chat/completions"
    if "api-version=" not in url:
        url += ("&" if "?" in url else "?") + "api-version=2024-10-21"
    headers = {}
    if api_key:
        headers["api-key"] = api_key
    payload = {
        "model": model,
        "messages": _openai_messages(messages, system),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = _http_post_json(url, payload, headers, timeout)
    return _parse_openai(data), _usage_openai(data)


def _chat_ollama(base_url, api_key, model, messages, system, temperature, max_tokens, timeout):
    url = base_url.rstrip("/") + "/api/chat"
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    payload = {
        "model": model,
        "messages": _openai_messages(messages, system),
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    data = _http_post_json(url, payload, headers, timeout)
    if "message" in data and isinstance(data["message"], dict):
        text = data["message"].get("content", "")
    else:
        text = _parse_openai(data)
    return text, _usage_ollama(data)


_PROTOCOL_HANDLERS = {
    "openai": _chat_openai,
    "azure": _chat_azure,
    "anthropic": _chat_anthropic,
    "gemini": _chat_gemini,
    "ollama": _chat_ollama,
}


def chat(provider_id, api_key, model, base_url, messages, system="",
         temperature=0.3, max_tokens=1024, timeout=120, on_usage=None):
    """Send a chat request and return the assistant's text response.

    messages is a list of {"role": "user"|"assistant", "content": str}.
    on_usage, if given, is called with {"input": n, "output": n} when available.
    """
    spec = PROVIDERS.get(provider_id)
    if spec is None:
        raise ProviderError("Unknown provider: %s" % provider_id)

    base_url = (base_url or spec["base_url"]).strip()
    if not base_url:
        raise ProviderError("No base URL configured for '%s'." % provider_id)

    model = (model or spec["default_model"]).strip()
    if not model:
        raise ProviderError("No model configured for '%s'." % provider_id)

    if spec["requires_key"] and not api_key:
        raise ProviderError(
            "No API key configured for %s. Open HaiLPER > Settings." % spec["label"]
        )

    handler = _PROTOCOL_HANDLERS[spec["protocol"]]
    try:
        text, usage = handler(
            base_url, api_key, model, messages, system,
            temperature, max_tokens, timeout,
        )
        if on_usage is not None:
            try:
                on_usage(usage)
            except Exception:
                pass
        return text
    except ProviderError:
        raise
    except socket.timeout:
        raise ProviderError("The request timed out after %ss." % timeout)
    except Exception as error:  # noqa: BLE001 - surface anything else to the UI
        raise ProviderError("%s: %s" % (type(error).__name__, error))


# --------------------------------------------------------------- tool calling
def _openai_tool_specs(tools):
    return [{"type": "function",
             "function": {"name": t["name"], "description": t["description"],
                          "parameters": t["parameters"]}} for t in tools]


def _anthropic_tool_specs(tools):
    return [{"name": t["name"], "description": t["description"],
             "input_schema": t["parameters"]} for t in tools]


def _gemini_tool_specs(tools):
    return [{"functionDeclarations": [
        {"name": t["name"], "description": t["description"],
         "parameters": t["parameters"]} for t in tools]}]


def _parse_openai_tool_calls(message):
    calls = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        try:
            arguments = json.loads(function.get("arguments") or "{}")
        except ValueError:
            arguments = {}
        calls.append({"id": call.get("id") or function.get("name"),
                      "name": function.get("name"), "arguments": arguments})
    return calls


def _chat_tools_openai(base_url, api_key, model, messages, system, tools,
                       temperature, max_tokens, timeout):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    payload = {"model": model, "messages": _openai_messages(messages, system),
               "temperature": temperature, "max_tokens": max_tokens}
    if tools:
        payload["tools"] = _openai_tool_specs(tools)
        payload["tool_choice"] = "auto"
    data = _http_post_json(url, payload, headers, timeout)
    message = (data.get("choices") or [{}])[0].get("message") or {}
    return (message.get("content") or "", _parse_openai_tool_calls(message),
            _usage_openai(data), message)


def _chat_tools_azure(base_url, api_key, model, messages, system, tools,
                      temperature, max_tokens, timeout):
    url = base_url.rstrip("/") + "/chat/completions"
    if "api-version=" not in url:
        url += ("&" if "?" in url else "?") + "api-version=2024-10-21"
    headers = {}
    if api_key:
        headers["api-key"] = api_key
    payload = {"model": model, "messages": _openai_messages(messages, system),
               "temperature": temperature, "max_tokens": max_tokens}
    if tools:
        payload["tools"] = _openai_tool_specs(tools)
        payload["tool_choice"] = "auto"
    data = _http_post_json(url, payload, headers, timeout)
    message = (data.get("choices") or [{}])[0].get("message") or {}
    return (message.get("content") or "", _parse_openai_tool_calls(message),
            _usage_openai(data), message)


def _chat_tools_ollama(base_url, api_key, model, messages, system, tools,
                       temperature, max_tokens, timeout):
    url = base_url.rstrip("/") + "/api/chat"
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    payload = {"model": model, "messages": _openai_messages(messages, system),
               "stream": False,
               "options": {"temperature": temperature, "num_predict": max_tokens}}
    if tools:
        payload["tools"] = _openai_tool_specs(tools)
    data = _http_post_json(url, payload, headers, timeout)
    message = data.get("message") or {}
    return (message.get("content") or "", _parse_openai_tool_calls(message),
            _usage_ollama(data), message)


def _chat_tools_anthropic(base_url, api_key, model, messages, system, tools,
                          temperature, max_tokens, timeout):
    url = base_url.rstrip("/") + "/messages"
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    payload = {"model": model, "max_tokens": max_tokens,
               "temperature": temperature, "messages": messages}
    if system:
        payload["system"] = system
    if tools:
        payload["tools"] = _anthropic_tool_specs(tools)
    data = _http_post_json(url, payload, headers, timeout)
    content = data.get("content") or []
    text = "".join(block.get("text", "") for block in content
                   if isinstance(block, dict) and block.get("type") == "text")
    calls = [{"id": block.get("id"), "name": block.get("name"),
              "arguments": block.get("input") or {}}
             for block in content
             if isinstance(block, dict) and block.get("type") == "tool_use"]
    return text, calls, _usage_anthropic(data), content


def _gemini_contents(messages):
    contents = []
    for message in messages:
        if "parts" in message:
            contents.append({"role": message.get("role", "user"),
                             "parts": message["parts"]})
        else:
            role = "user" if message.get("role") == "user" else "model"
            contents.append({"role": role,
                             "parts": [{"text": message.get("content", "")}]})
    return contents


def _chat_tools_gemini(base_url, api_key, model, messages, system, tools,
                       temperature, max_tokens, timeout):
    url = "%s/models/%s:generateContent" % (base_url.rstrip("/"), model)
    headers = {"x-goog-api-key": api_key}
    payload = {"contents": _gemini_contents(messages),
               "generationConfig": {"temperature": temperature,
                                    "maxOutputTokens": max_tokens}}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    if tools:
        payload["tools"] = _gemini_tool_specs(tools)
    data = _http_post_json(url, payload, headers, timeout)
    candidate = (data.get("candidates") or [{}])[0]
    content = candidate.get("content", {})
    parts = content.get("parts", []) if isinstance(content, dict) else []
    text = "".join(part.get("text", "") for part in parts
                   if isinstance(part, dict) and "text" in part)
    calls = []
    for part in parts:
        function_call = part.get("functionCall") if isinstance(part, dict) else None
        if function_call:
            calls.append({"id": function_call.get("name"),
                          "name": function_call.get("name"),
                          "arguments": function_call.get("args") or {}})
    return text, calls, _usage_gemini(data), content


_TOOL_HANDLERS = {
    "openai": _chat_tools_openai,
    "azure": _chat_tools_azure,
    "ollama": _chat_tools_ollama,
    "anthropic": _chat_tools_anthropic,
    "gemini": _chat_tools_gemini,
}


def chat_tools(provider_id, api_key, model, base_url, messages, system="",
               tools=None, temperature=0.3, max_tokens=1024, timeout=120,
               on_usage=None):
    """Call the model with native tool calling.

    Returns (text, tool_calls, usage, raw_message). tool_calls is a list of
    {id, name, arguments}; raw_message is provider-specific and must be passed
    back to tool_result_messages().
    """
    spec = PROVIDERS.get(provider_id)
    if spec is None:
        raise ProviderError("Unknown provider: %s" % provider_id)
    base_url = (base_url or spec["base_url"]).strip()
    if not base_url:
        raise ProviderError("No base URL configured for '%s'." % provider_id)
    model = (model or spec["default_model"]).strip()
    if not model:
        raise ProviderError("No model configured for '%s'." % provider_id)
    if spec["requires_key"] and not api_key:
        raise ProviderError(
            "No API key configured for %s. Open HaiLPER > Settings." % spec["label"])

    handler = _TOOL_HANDLERS.get(spec["protocol"])
    if handler is None or not tools:
        text = chat(provider_id, api_key, model, base_url, messages, system,
                    temperature, max_tokens, timeout, on_usage=on_usage)
        return text, [], None, None
    try:
        text, calls, usage, raw = handler(
            base_url, api_key, model, messages, system, tools,
            temperature, max_tokens, timeout)
        if on_usage is not None:
            try:
                on_usage(usage)
            except Exception:
                pass
        return text, calls, usage, raw
    except ProviderError:
        raise
    except socket.timeout:
        raise ProviderError("The request timed out after %ss." % timeout)
    except Exception as error:  # noqa: BLE001
        raise ProviderError("%s: %s" % (type(error).__name__, error))


def tool_result_messages(provider_id, raw_message, results):
    spec = PROVIDERS.get(provider_id) or {}
    protocol = spec.get("protocol")
    if protocol in ("openai", "azure", "ollama"):
        if raw_message is None:
            return []
        out = [{"role": "assistant",
                "content": raw_message.get("content") or "",
                "tool_calls": raw_message.get("tool_calls") or []}]
        for item in results:
            out.append({"role": "tool", "tool_call_id": item["id"],
                        "content": item["content"]})
        return out
    if protocol == "anthropic":
        out = [{"role": "assistant", "content": raw_message or []}]
        out.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": item["id"],
             "content": item["content"]} for item in results]})
        return out
    if protocol == "gemini":
        out = [{"role": "model", "parts": (raw_message or {}).get("parts", [])}]
        out.append({"role": "user", "parts": [
            {"functionResponse": {"name": item["name"],
                                  "response": {"result": item["content"]}}}
            for item in results]})
        return out
    return []


def _open_stream(url, payload, headers, timeout):
    body = json.dumps(payload).encode("utf-8")
    delay = 1.0
    for attempt in range(_RETRY_ATTEMPTS):
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "text/event-stream")
        for key, value in headers.items():
            request.add_header(key, value)
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            if _retryable(error) and attempt < _RETRY_ATTEMPTS - 1:
                time.sleep(delay)
                delay *= 2
                continue
            detail = error.read().decode("utf-8", "replace")
            raise ProviderError(_friendly_http_error(error.code, detail))
        except urllib.error.URLError as error:
            if attempt < _RETRY_ATTEMPTS - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise ProviderError("Could not reach the server: %s" % error.reason)
        except socket.timeout:
            if attempt < _RETRY_ATTEMPTS - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise ProviderError("The request timed out.")
    raise ProviderError("Could not connect after retries.")


def _sse_objects(response):
    """Yield the JSON payloads of an SSE stream, skipping [DONE]."""
    for raw in response:
        line = raw.decode("utf-8", "replace").strip()
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            yield json.loads(data)
        except ValueError:
            continue


def _stream_openai(base_url, api_key, model, messages, system, temperature,
                   max_tokens, timeout, on_chunk):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    payload = {
        "model": model,
        "messages": _openai_messages(messages, system),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    parts = []
    usage = None
    with _open_stream(url, payload, headers, timeout) as response:
        for obj in _sse_objects(response):
            if obj.get("usage"):
                usage = _usage_openai(obj)
            try:
                delta = obj["choices"][0].get("delta", {}).get("content")
            except (KeyError, IndexError, TypeError):
                delta = None
            if delta:
                parts.append(delta)
                on_chunk(delta)
    return "".join(parts), usage


def _stream_azure(base_url, api_key, model, messages, system, temperature,
                  max_tokens, timeout, on_chunk):
    url = base_url.rstrip("/") + "/chat/completions"
    if "api-version=" not in url:
        url += ("&" if "?" in url else "?") + "api-version=2024-10-21"
    headers = {}
    if api_key:
        headers["api-key"] = api_key
    payload = {
        "model": model,
        "messages": _openai_messages(messages, system),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    parts = []
    usage = None
    with _open_stream(url, payload, headers, timeout) as response:
        for obj in _sse_objects(response):
            if obj.get("usage"):
                usage = _usage_openai(obj)
            try:
                delta = obj["choices"][0].get("delta", {}).get("content")
            except (KeyError, IndexError, TypeError):
                delta = None
            if delta:
                parts.append(delta)
                on_chunk(delta)
    return "".join(parts), usage


def _stream_anthropic(base_url, api_key, model, messages, system, temperature,
                      max_tokens, timeout, on_chunk):
    url = base_url.rstrip("/") + "/messages"
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
        "stream": True,
    }
    if system:
        payload["system"] = system
    parts = []
    input_tokens = None
    output_tokens = None
    with _open_stream(url, payload, headers, timeout) as response:
        for obj in _sse_objects(response):
            kind = obj.get("type")
            if kind == "message_start":
                usage = (obj.get("message") or {}).get("usage") or {}
                input_tokens = usage.get("input_tokens", input_tokens)
            elif kind == "message_delta":
                usage = obj.get("usage") or {}
                output_tokens = usage.get("output_tokens", output_tokens)
            if kind == "content_block_delta":
                text = obj.get("delta", {}).get("text")
                if text:
                    parts.append(text)
                    on_chunk(text)
    return "".join(parts), _mk_usage(input_tokens, output_tokens)


def _stream_gemini(base_url, api_key, model, messages, system, temperature,
                   max_tokens, timeout, on_chunk):
    url = "%s/models/%s:streamGenerateContent?alt=sse" % (
        base_url.rstrip("/"), model)
    headers = {"x-goog-api-key": api_key}
    contents = []
    for message in messages:
        role = "user" if message.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": message.get("content", "")}]})
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    parts = []
    usage = None
    with _open_stream(url, payload, headers, timeout) as response:
        for obj in _sse_objects(response):
            if obj.get("usageMetadata"):
                usage = _usage_gemini(obj)
            for candidate in obj.get("candidates", []) or []:
                for part in candidate.get("content", {}).get("parts", []) or []:
                    text = part.get("text")
                    if text:
                        parts.append(text)
                        on_chunk(text)
    return "".join(parts), usage


def _stream_ollama(base_url, api_key, model, messages, system, temperature,
                   max_tokens, timeout, on_chunk):
    url = base_url.rstrip("/") + "/api/chat"
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    payload = {
        "model": model,
        "messages": _openai_messages(messages, system),
        "stream": True,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    parts = []
    usage = None
    with _open_stream(url, payload, headers, timeout) as response:
        for raw in response:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            text = (obj.get("message") or {}).get("content")
            if text:
                parts.append(text)
                on_chunk(text)
            candidate = _usage_ollama(obj)
            if candidate:
                usage = candidate
            if obj.get("done"):
                break
    return "".join(parts), usage


_STREAM_HANDLERS = {
    "openai": _stream_openai,
    "azure": _stream_azure,
    "anthropic": _stream_anthropic,
    "gemini": _stream_gemini,
    "ollama": _stream_ollama,
}


def chat_stream(provider_id, api_key, model, base_url, messages, system="",
                temperature=0.3, max_tokens=1024, timeout=120, on_chunk=None,
                on_usage=None):
    """Like chat() but calls on_chunk(delta) as text arrives.

    Falls back to a single non-streaming response if streaming is unavailable.
    on_usage, if given, receives {"input": n, "output": n}. Returns the text.
    """
    spec = PROVIDERS.get(provider_id)
    if spec is None:
        raise ProviderError("Unknown provider: %s" % provider_id)
    base_url = (base_url or spec["base_url"]).strip()
    if not base_url:
        raise ProviderError("No base URL configured for '%s'." % provider_id)
    model = (model or spec["default_model"]).strip()
    if not model:
        raise ProviderError("No model configured for '%s'." % provider_id)
    if spec["requires_key"] and not api_key:
        raise ProviderError(
            "No API key configured for %s. Open HaiLPER > Settings." % spec["label"])

    handler = _STREAM_HANDLERS.get(spec["protocol"])
    if handler is None or on_chunk is None:
        reply = chat(provider_id, api_key, model, base_url, messages, system,
                     temperature, max_tokens, timeout, on_usage=on_usage)
        if on_chunk is not None:
            on_chunk(reply)
        return reply
    try:
        text, usage = handler(base_url, api_key, model, messages, system,
                              temperature, max_tokens, timeout, on_chunk)
        if on_usage is not None:
            try:
                on_usage(usage)
            except Exception:
                pass
        return text
    except ProviderError:
        raise
    except socket.timeout:
        raise ProviderError("The request timed out after %ss." % timeout)
    except Exception as error:  # noqa: BLE001
        raise ProviderError("%s: %s" % (type(error).__name__, error))


def list_models(provider_id, api_key="", base_url="", timeout=15):
    """Best-effort model listing; returns [] when unsupported."""
    spec = PROVIDERS.get(provider_id)
    if spec is None:
        return []
    base_url = (base_url or spec["base_url"]).strip()

    if spec["protocol"] == "ollama":
        url = base_url.rstrip("/") + "/api/tags"
    elif spec["protocol"] == "openai":
        url = base_url.rstrip("/") + "/models"
    else:
        return list(spec.get("models", []))

    request = urllib.request.Request(url, method="GET")
    if api_key:
        request.add_header("Authorization", "Bearer " + api_key)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
    except Exception:
        return list(spec.get("models", []))

    names = []
    if spec["protocol"] == "ollama":
        names = [m.get("name", "") for m in data.get("models", []) if isinstance(m, dict)]
    else:
        names = [m.get("id", "") for m in data.get("data", []) if isinstance(m, dict)]
    names = [n for n in names if n]
    return names or list(spec.get("models", []))
