"""HTTP clients for the supported LLM providers.

Only the Python standard library is used so the extension works with whatever
interpreter LibreOffice ships, without requiring pip packages.
"""

import json
import socket
import urllib.error
import urllib.request


class ProviderError(Exception):
    """Raised for any recoverable problem talking to a provider."""


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
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise ProviderError(_friendly_http_error(error.code, detail))
    except urllib.error.URLError as error:
        raise ProviderError("Could not reach the server: %s" % error.reason)
    except socket.timeout:
        raise ProviderError("The request timed out.")
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
    return _parse_openai(_http_post_json(url, payload, headers, timeout))


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
    return _parse_anthropic(_http_post_json(url, payload, headers, timeout))


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
    return _parse_gemini(_http_post_json(url, payload, headers, timeout))


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
    return _parse_openai(_http_post_json(url, payload, headers, timeout))


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
        return data["message"].get("content", "")
    return _parse_openai(data)


_PROTOCOL_HANDLERS = {
    "openai": _chat_openai,
    "azure": _chat_azure,
    "anthropic": _chat_anthropic,
    "gemini": _chat_gemini,
    "ollama": _chat_ollama,
}


def chat(provider_id, api_key, model, base_url, messages, system="",
         temperature=0.3, max_tokens=1024, timeout=120):
    """Send a chat request and return the assistant's text response.

    messages is a list of {"role": "user"|"assistant", "content": str}.
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
        return handler(
            base_url, api_key, model, messages, system,
            temperature, max_tokens, timeout,
        )
    except ProviderError:
        raise
    except socket.timeout:
        raise ProviderError("The request timed out after %ss." % timeout)
    except Exception as error:  # noqa: BLE001 - surface anything else to the UI
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
