"""Small official Text to Dialogue adapter. No retries, env keys, or response logging."""
from __future__ import annotations

import httpx
from pydantic import SecretStr


class ProviderError(RuntimeError):
    def __init__(self, message: str, uncertain: bool = False):
        super().__init__(message)
        self.uncertain = uncertain


class ElevenLabs:
    provider_name = "ElevenLabs"
    def __init__(self, key: str, transport=None):
        if not key.strip():
            raise ValueError("Supply your own ElevenLabs API key in this session")
        self._key = SecretStr(key.strip())
        self._transport = transport

    def _request(self, method, path, *, body=None, audio=False, params=None):
        # Never include request/response bodies or headers in errors. Do not follow redirects.
        try:
            with httpx.Client(base_url="https://api.elevenlabs.io", timeout=120,
                              follow_redirects=False, trust_env=False, transport=self._transport) as client:
                with client.stream(method, path, headers={"xi-api-key": self._key.get_secret_value()},
                                   json=body, params=params) as response:
                    status = response.status_code
                    if status != 200:
                        messages = {401: "Key rejected. Check your session key.",
                                    403: "Key lacks permission, or this voice/model is unavailable to your account.",
                                    402: "Insufficient credits or plan access.",
                                    422: "Invalid dialogue, voice or model settings.",
                                    429: "Rate or quota limit reached. Check your account before resuming."}
                        raise ProviderError(messages.get(status, "Provider request failed. Check your account before retrying."),
                                            uncertain=audio and (status >= 500 or status not in messages))
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > (8_000_000 if audio else 2_000_000):
                            raise ProviderError("Provider output exceeded the safe size limit.", uncertain=audio)
                    if audio:
                        if len(data) < 512 or not (data[:3] == b"ID3" or (data[0] == 255 and data[1] & 224 == 224)):
                            raise ProviderError("Provider did not return a usable MP3. Check request history.", uncertain=True)
                        return bytes(data)
                    import json
                    return json.loads(data)
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError):
            raise ProviderError("Connection or response failed. No automatic retry; check provider request history.",
                                uncertain=audio) from None

    def catalog(self):
        account = self._request("GET", "/v1/user/subscription")
        models = self._request("GET", "/v1/models")
        voices, token = [], None
        for _ in range(10):
            params = {"language": "ru", "page_size": 100}
            if token:
                params["next_page_token"] = token
            page = self._request("GET", "/v2/voices", params=params)
            voices.extend({"voice_id": v["voice_id"], "name": v["name"], "category": v.get("category", "")}
                          for v in page.get("voices", []) if "cloned" not in v.get("category", "").lower())
            token = page.get("next_page_token")
            if not token:
                break
        return {"account": {k: account.get(k) for k in ("tier", "character_count", "character_limit")},
                "models": [{k: m.get(k) for k in ("model_id", "name", "model_rates")} for m in models
                           if m.get("can_do_text_to_speech")], "voices": voices}

    def dialogue(self, turns, voices, model, seed=None):
        body = {"inputs": [{"text": t.text, "voice_id": voices[t.speaker]} for t in turns],
                "model_id": model, "language_code": "ru"}
        if seed is not None:
            body["seed"] = seed
        return self._request("POST", "/v1/text-to-dialogue", body=body, audio=True,
                             params={"output_format": "mp3_44100_128"})
