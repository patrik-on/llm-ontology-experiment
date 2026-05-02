from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def generate_with_ollama(
    prompt: str,
    model_name: str,
    base_url: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> str:
    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": max_tokens,
        },
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(
            f"Ollama is not reachable at {base_url}. Start Ollama and ensure the model is available."
        ) from exc
    except HTTPError as exc:
        raise RuntimeError(f"Ollama request failed with HTTP {exc.code}: {exc.reason}") from exc

    if "response" not in data:
        raise RuntimeError(f"Ollama response did not contain a 'response' field: {data}")
    return str(data["response"])
