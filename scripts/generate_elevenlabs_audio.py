from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://api.elevenlabs.io"
SFX_DEFAULT_MODEL = "eleven_text_to_sound_v2"
MUSIC_DEFAULT_MODEL = "music_v2"
FALLBACK_HTTP_CODES = {401, 402, 403, 408, 409, 425, 429, 500, 502, 503, 504}
RETRY_HTTP_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    type: str
    api_base: str
    api_key: str
    supports: tuple[str, ...] = ("sound_effect", "music")
    config: dict[str, Any] | None = None


@dataclass(frozen=True)
class GenerationResult:
    asset_id: str
    output_path: Path
    skipped: bool
    failed: bool = False
    provider_name: str | None = None
    error: str | None = None


class ProviderAPIError(RuntimeError):
    def __init__(self, provider_name: str, code: int | None, details: str, url: str):
        code_text = "network" if code is None else str(code)
        super().__init__(f"{provider_name} API error {code_text} for {url}: {details}")
        self.provider_name = provider_name
        self.code = code
        self.details = details
        self.url = url


class NoUsableProviderError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SFX/music from content/elevenlabs_audio_prompts.json with provider/key fallback and resume support")
    parser.add_argument("--spec", default="content/elevenlabs_audio_prompts.json", help="Path to JSON generation spec")
    parser.add_argument("--providers-config", default=None, help="Optional JSON file with a {'providers': [...]} list")
    parser.add_argument("--api-key", default=os.environ.get("ELEVENLABS_API_KEY"), help="Single ElevenLabs API key; defaults to ELEVENLABS_API_KEY")
    parser.add_argument("--api-keys", nargs="*", default=None, help="Several ElevenLabs API keys tried in order. Avoid putting secrets in shell history if possible.")
    parser.add_argument("--api-base", default=os.environ.get("ELEVENLABS_API_BASE", API_BASE), help="ElevenLabs API base URL")
    parser.add_argument("--only", nargs="*", default=None, help="Generate only these asset ids")
    parser.add_argument("--kind", choices=("sound_effect", "music"), default=None, help="Generate only one asset kind")
    parser.add_argument("--dry-run", action="store_true", help="Print planned generations without calling any API")
    parser.add_argument("--force", action="store_true", help="Regenerate existing files instead of resuming/skipping them")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds to sleep between successful API calls")
    parser.add_argument("--timeout", type=float, default=300.0, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=2, help="Retries per provider for transient HTTP/network errors")
    parser.add_argument("--state", default="content/elevenlabs_generation_state.json", help="Progress/state JSON used for resume reporting")
    parser.add_argument("--no-state", action="store_true", help="Do not write progress/state file")
    parser.add_argument("--continue-on-error", dest="continue_on_error", action="store_true", default=True, help="Continue with later assets after all providers fail. Default: enabled")
    parser.add_argument("--stop-on-error", dest="continue_on_error", action="store_false", help="Stop as soon as one asset cannot be generated")
    parser.add_argument("--merge-manifest", action="store_true", help="Also merge generated entries into content/sound_manifest.json")
    args = parser.parse_args()

    project_root = _project_root_from_script()
    spec_path = _resolve(project_root, args.spec)
    spec = _load_json(spec_path)
    _validate_spec(spec)

    requested_only = set(args.only or [])
    assets = _selected_assets(spec, requested_only, args.kind)
    if requested_only:
        found = {str(asset.get("id")) for asset in assets}
        missing = sorted(requested_only - found)
        if missing:
            print("Unknown asset id(s): " + ", ".join(missing), file=sys.stderr)
            return 2

    output_root = _resolve(project_root, _required_string(spec, "output_dir"))
    generated_manifest_path = _resolve(project_root, _required_string(spec, "generated_manifest"))
    state_path = _resolve(project_root, args.state)
    defaults = spec.get("defaults") if isinstance(spec.get("defaults"), dict) else {}

    providers = _build_provider_chain(
        spec=spec,
        project_root=project_root,
        providers_config=args.providers_config,
        cli_api_keys=args.api_keys,
        single_api_key=args.api_key,
        api_base=args.api_base,
    )

    if args.dry_run:
        _print_dry_run(assets, output_root, defaults, providers, args.force)
        return 0

    if not providers and _assets_requiring_generation(assets, output_root, bool(args.force)):
        print(
            "Missing API providers. Set ELEVENLABS_API_KEY, ELEVENLABS_API_KEYS, "
            "ELEVENLABS_API_KEY_1/2/3, or add a providers list in the JSON spec.",
            file=sys.stderr,
        )
        return 2

    state = _load_state(state_path) if not args.no_state else {"assets": {}}
    results: list[GenerationResult] = []
    unavailable_all: set[str] = set()
    unavailable_by_kind: dict[str, set[str]] = {}

    provider_names = ', '.join(provider.name for provider in providers) if providers else '(aucun)'
    print(f"Providers actifs: {provider_names}")

    for index, asset in enumerate(assets, start=1):
        asset_id = str(asset.get("id", f"asset_{index}"))
        try:
            result = _generate_asset_with_fallback(
                providers=providers,
                unavailable_all=unavailable_all,
                unavailable_by_kind=unavailable_by_kind,
                output_root=output_root,
                asset=asset,
                defaults=defaults,
                force=bool(args.force),
                timeout=float(args.timeout),
                retries=max(0, int(args.retries)),
            )
        except Exception as exc:
            output_path = output_root / str(asset.get("file", ""))
            result = GenerationResult(asset_id, output_path, skipped=False, failed=True, error=str(exc))
            results.append(result)
            print(f"[{index}/{len(assets)}] ERROR {asset_id}: {exc}", file=sys.stderr)
            if not args.no_state:
                _record_state(state, state_path, asset, result, attempts=None)
            if not args.continue_on_error:
                return 1
            continue

        results.append(result)
        if result.skipped:
            status = "skip"
        elif result.failed:
            status = "fail"
        else:
            status = "ok"
        provider_suffix = f" via {result.provider_name}" if result.provider_name else ""
        print(f"[{index}/{len(assets)}] {status} {result.asset_id}{provider_suffix} -> {result.output_path}")
        if not args.no_state:
            _record_state(state, state_path, asset, result, attempts=None)
        if not result.skipped and not result.failed and args.sleep > 0:
            time.sleep(args.sleep)

    manifest_entries = _existing_sound_effect_manifest_entries(output_root, spec)
    _write_json(generated_manifest_path, manifest_entries)
    if args.merge_manifest:
        _merge_manifest(project_root / "content" / "sound_manifest.json", manifest_entries)

    failed = [result for result in results if result.failed]
    if failed:
        print(f"Terminé avec {len(failed)} échec(s). Fichiers présents dans le manifest généré: {len(manifest_entries)}", file=sys.stderr)
        return 1
    return 0


def _project_root_from_script() -> Path:
    script_path = Path(__file__).resolve()
    if script_path.parent.name.lower() == "scripts":
        return script_path.parent.parent
    return script_path.parent


def _build_provider_chain(
    spec: dict[str, Any],
    project_root: Path,
    providers_config: str | None,
    cli_api_keys: list[str] | None,
    single_api_key: str | None,
    api_base: str,
) -> list[ProviderSpec]:
    raw_providers: list[Any] = []

    if isinstance(spec.get("providers"), list):
        raw_providers.extend(spec["providers"])

    if providers_config:
        config_path = _resolve(project_root, providers_config)
        provider_config = _load_json(config_path)
        if not isinstance(provider_config, dict) or not isinstance(provider_config.get("providers"), list):
            raise ValueError(f"Expected a providers list in {config_path}")
        raw_providers.extend(provider_config["providers"])

    providers: list[ProviderSpec] = []
    for index, raw_provider in enumerate(raw_providers, start=1):
        providers.extend(_provider_specs_from_raw(raw_provider, index=index, default_api_base=api_base))

    # CLI/env keys are appended after configured providers. Duplicates are removed later.
    cli_keys: list[str] = []
    if cli_api_keys:
        for key in cli_api_keys:
            cli_keys.extend(_split_secret_list(key))
    if single_api_key:
        cli_keys.extend(_split_secret_list(single_api_key))

    env_keys: list[str] = []
    env_keys.extend(_split_secret_list(os.environ.get("ELEVENLABS_API_KEYS", "")))
    for index in range(1, 21):
        env_keys.extend(_split_secret_list(os.environ.get(f"ELEVENLABS_API_KEY_{index}", "")))
    env_keys.extend(_split_secret_list(os.environ.get("ELEVENLABS_API_KEY", "")))

    for index, key in enumerate(cli_keys + env_keys, start=1):
        providers.append(
            ProviderSpec(
                name=f"elevenlabs_key_{index}",
                type="elevenlabs",
                api_base=api_base,
                api_key=key,
                supports=("sound_effect", "music"),
                config={},
            )
        )

    return _dedupe_providers(providers)


def _provider_specs_from_raw(raw_provider: Any, index: int, default_api_base: str) -> list[ProviderSpec]:
    if not isinstance(raw_provider, dict):
        raise ValueError(f"Provider #{index} must be an object")

    provider_type = str(raw_provider.get("type", "elevenlabs")).strip().lower()
    base_name = str(raw_provider.get("name", f"provider_{index}")).strip() or f"provider_{index}"
    api_base = str(raw_provider.get("api_base", default_api_base)).strip() or default_api_base
    supports_raw = raw_provider.get("supports", ["sound_effect", "music"])
    if isinstance(supports_raw, str):
        supports = tuple(part.strip() for part in supports_raw.replace(";", ",").split(",") if part.strip())
    elif isinstance(supports_raw, list):
        supports = tuple(str(part).strip() for part in supports_raw if str(part).strip())
    else:
        supports = ("sound_effect", "music")

    keys: list[str] = []
    if raw_provider.get("api_key"):
        keys.extend(_split_secret_list(str(raw_provider.get("api_key"))))
    if raw_provider.get("api_key_env"):
        for env_name in str(raw_provider.get("api_key_env")).replace(";", ",").split(","):
            env_name = env_name.strip()
            if env_name:
                keys.extend(_split_secret_list(os.environ.get(env_name, "")))

    # custom_http can be used without a key if the local/private endpoint does not need auth.
    if not keys and provider_type != "custom_http":
        return []
    if not keys:
        keys = [""]

    providers: list[ProviderSpec] = []
    for key_index, key in enumerate(keys, start=1):
        suffix = "" if len(keys) == 1 else f"_{key_index}"
        providers.append(
            ProviderSpec(
                name=base_name + suffix,
                type=provider_type,
                api_base=api_base,
                api_key=key,
                supports=supports,
                config=dict(raw_provider),
            )
        )
    return providers


def _dedupe_providers(providers: list[ProviderSpec]) -> list[ProviderSpec]:
    result: list[ProviderSpec] = []
    seen: set[tuple[str, str, str, str]] = set()
    used_names: dict[str, int] = {}
    for provider in providers:
        key_hash = hashlib.sha256(provider.api_key.encode("utf-8")).hexdigest() if provider.api_key else ""
        marker = (provider.type, provider.api_base.rstrip("/"), key_hash, ",".join(provider.supports))
        if provider.api_key and marker in seen:
            continue
        seen.add(marker)
        name = provider.name
        if name in used_names:
            used_names[name] += 1
            name = f"{name}_{used_names[provider.name]}"
            provider = ProviderSpec(name, provider.type, provider.api_base, provider.api_key, provider.supports, provider.config)
        else:
            used_names[name] = 1
        result.append(provider)
    return result


def _split_secret_list(value: str) -> list[str]:
    value = (value or "").strip()
    if not value:
        return []
    # Windows-friendly: set ELEVENLABS_API_KEYS=key1;key2;key3
    separators = [";", ",", "\n", "\r", "\t", " "]
    parts = [value]
    for separator in separators:
        next_parts: list[str] = []
        for part in parts:
            next_parts.extend(part.split(separator))
        parts = next_parts
    return [part.strip().strip('"').strip("'") for part in parts if part.strip().strip('"').strip("'")]


def _assets_requiring_generation(assets: list[dict[str, Any]], output_root: Path, force: bool) -> list[dict[str, Any]]:
    if force:
        return assets
    return [
        asset
        for asset in assets
        if not _existing_file_is_usable(output_root / _required_string(asset, "file"), asset)
    ]


def _generate_asset_with_fallback(
    providers: list[ProviderSpec],
    unavailable_all: set[str],
    unavailable_by_kind: dict[str, set[str]],
    output_root: Path,
    asset: dict[str, Any],
    defaults: dict[str, Any],
    force: bool,
    timeout: float,
    retries: int,
) -> GenerationResult:
    asset_id = _required_string(asset, "id")
    output_path = output_root / _required_string(asset, "file")
    kind = _required_string(asset, "kind")

    if output_path.exists() and not force and _existing_file_is_usable(output_path, asset):
        return GenerationResult(asset_id, output_path, skipped=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    for provider in providers:
        if provider.name in unavailable_all:
            continue
        if provider.name in unavailable_by_kind.get(kind, set()):
            continue
        if kind not in provider.supports:
            continue

        try:
            audio = _generate_with_provider(provider, asset, defaults, timeout=timeout, retries=retries)
            _validate_audio_bytes(audio, asset)
            output_path.write_bytes(audio)
            return GenerationResult(asset_id, output_path, skipped=False, provider_name=provider.name)
        except ProviderAPIError as exc:
            errors.append(str(exc))
            print(f"  fallback: {asset_id} failed on {provider.name}: {_short_error(exc)}", file=sys.stderr)
            if _provider_kind_unavailable(exc, kind):
                unavailable_by_kind.setdefault(kind, set()).add(provider.name)
                print(f"  provider disabled for {kind}: {provider.name}", file=sys.stderr)
            elif _provider_quota_exhausted(exc):
                unavailable_all.add(provider.name)
                print(f"  provider disabled for this run: {provider.name} (quota/rate limit/auth)", file=sys.stderr)
            elif not _should_try_next_provider(exc):
                # Request/model/schema errors usually will not be fixed by another key of the same provider.
                # Still allow other provider types to try below; same-type duplicated keys are skipped only if the error is endpoint/model-like.
                pass
            continue
        except Exception as exc:
            errors.append(f"{provider.name}: {exc}")
            print(f"  fallback: {asset_id} failed on {provider.name}: {exc}", file=sys.stderr)
            continue

    if not errors:
        raise NoUsableProviderError(f"No provider available for {kind}. Check API keys/providers and supports lists.")
    raise NoUsableProviderError("All providers failed for " + asset_id + ":\n- " + "\n- ".join(errors))


def _generate_with_provider(provider: ProviderSpec, asset: dict[str, Any], defaults: dict[str, Any], timeout: float, retries: int) -> bytes:
    if provider.type == "elevenlabs":
        return _generate_elevenlabs(provider, asset, defaults, timeout=timeout, retries=retries)
    if provider.type == "custom_http":
        return _generate_custom_http(provider, asset, defaults, timeout=timeout, retries=retries)
    raise ValueError(f"Unsupported provider type for {provider.name}: {provider.type}")


def _generate_elevenlabs(provider: ProviderSpec, asset: dict[str, Any], defaults: dict[str, Any], timeout: float, retries: int) -> bytes:
    kind = _required_string(asset, "kind")
    if kind == "sound_effect":
        endpoint, body = _elevenlabs_sfx_request(asset, defaults.get("sound_effects", {}))
    elif kind == "music":
        endpoint, body = _elevenlabs_music_request(asset, defaults.get("music", {}))
    else:
        raise ValueError(f"Unsupported kind: {kind}")
    return _post_json(provider, endpoint, body, timeout=timeout, retries=retries)


def _elevenlabs_sfx_request(asset: dict[str, Any], defaults_raw: Any) -> tuple[str, dict[str, Any]]:
    defaults = defaults_raw if isinstance(defaults_raw, dict) else {}
    output_format = str(asset.get("output_format", defaults.get("output_format", "mp3_44100_128")))
    endpoint = "/v1/sound-generation?" + urllib.parse.urlencode({"output_format": output_format})

    duration = _optional_float(asset.get("duration_seconds", None))
    if duration is None:
        duration = _optional_float(defaults.get("duration_seconds", None))
    if duration is not None:
        duration = _clamp(duration, 0.5, 30.0)

    prompt_influence = _optional_float(asset.get("prompt_influence", defaults.get("prompt_influence", 0.3)))
    prompt_influence = _clamp(prompt_influence if prompt_influence is not None else 0.3, 0.0, 1.0)

    model_id = asset.get("model_id", defaults.get("model_id", SFX_DEFAULT_MODEL))
    if not isinstance(model_id, str) or not model_id:
        model_id = SFX_DEFAULT_MODEL

    body: dict[str, Any] = {
        "text": _prompt_text(asset, defaults),
        "prompt_influence": prompt_influence,
        "model_id": model_id,
    }
    if duration is not None:
        body["duration_seconds"] = duration
    if bool(asset.get("loop", False)):
        body["loop"] = True
    return endpoint, body


def _elevenlabs_music_request(asset: dict[str, Any], defaults_raw: Any) -> tuple[str, dict[str, Any]]:
    defaults = defaults_raw if isinstance(defaults_raw, dict) else {}
    output_format = str(asset.get("output_format", defaults.get("output_format", "auto")))
    endpoint = "/v1/music?" + urllib.parse.urlencode({"output_format": output_format})

    duration_ms = int(_clamp(float(asset.get("duration_seconds", 30.0)) * 1000.0, 3000.0, 600000.0))
    model_id = str(asset.get("model_id", defaults.get("model_id", MUSIC_DEFAULT_MODEL)))

    body: dict[str, Any] = {
        "prompt": _required_string(asset, "prompt"),
        "music_length_ms": duration_ms,
        "model_id": model_id,
        "force_instrumental": bool(asset.get("force_instrumental", defaults.get("force_instrumental", True))),
    }
    return endpoint, body


def _generate_custom_http(provider: ProviderSpec, asset: dict[str, Any], defaults: dict[str, Any], timeout: float, retries: int) -> bytes:
    """Generic fallback provider.

    This is intentionally simple: the provider receives a JSON body with prompt/kind/duration/loop.
    It can return raw audio bytes, or JSON containing one of: audio_base64, audio, b64_json, audio_url, url.
    """
    config = provider.config or {}
    kind = _required_string(asset, "kind")
    endpoint_key = "sfx_endpoint" if kind == "sound_effect" else "music_endpoint"
    endpoint = str(config.get(endpoint_key, config.get("endpoint", ""))).strip()
    if not endpoint:
        raise ValueError(f"custom_http provider {provider.name} has no endpoint for {kind}")

    body: dict[str, Any] = {
        "asset_id": _required_string(asset, "id"),
        "kind": kind,
        "prompt": _required_string(asset, "prompt"),
        "duration_seconds": float(asset.get("duration_seconds", 2.0 if kind == "sound_effect" else 30.0)),
        "loop": bool(asset.get("loop", False)),
        "output_format": str(asset.get("output_format", "mp3")),
    }
    extra_body = config.get("extra_body")
    if isinstance(extra_body, dict):
        body.update(extra_body)

    return _post_json(provider, endpoint, body, timeout=timeout, retries=retries)


def _post_json(provider: ProviderSpec, endpoint: str, body: dict[str, Any], timeout: float, retries: int) -> bytes:
    url = _absolute_url(provider.api_base, endpoint)
    payload = json.dumps(body).encode("utf-8")
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        request = urllib.request.Request(
            url,
            data=payload,
            headers=_headers_for_provider(provider),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content = response.read()
                content_type = response.headers.get("content-type", "")
                return _decode_audio_response(provider, content, content_type, timeout=timeout)
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            api_error = ProviderAPIError(provider.name, error.code, details, url)
            if error.code not in RETRY_HTTP_CODES or attempt >= retries:
                raise api_error from error
            last_error = api_error
        except urllib.error.URLError as error:
            api_error = ProviderAPIError(provider.name, None, str(error), url)
            if attempt >= retries:
                raise api_error from error
            last_error = api_error

        time.sleep(min(2.0 * (attempt + 1), 10.0))

    raise RuntimeError(f"Request failed after retries: {last_error}")


def _headers_for_provider(provider: ProviderSpec) -> dict[str, str]:
    headers = {
        "content-type": "application/json",
        "accept": "application/octet-stream, audio/*, application/json",
    }
    config = provider.config or {}

    if provider.type == "elevenlabs":
        headers["xi-api-key"] = provider.api_key
        return headers

    header_name = str(config.get("auth_header", "Authorization"))
    auth_scheme = str(config.get("auth_scheme", "Bearer"))
    if provider.api_key:
        headers[header_name] = f"{auth_scheme} {provider.api_key}" if auth_scheme else provider.api_key

    extra_headers = config.get("headers")
    if isinstance(extra_headers, dict):
        for key, value in extra_headers.items():
            headers[str(key)] = str(value)
    return headers


def _decode_audio_response(provider: ProviderSpec, content: bytes, content_type: str, timeout: float) -> bytes:
    lowered = content_type.lower()
    if provider.type == "elevenlabs" or "audio/" in lowered or "octet-stream" in lowered:
        return content

    # Generic JSON response decoding for custom providers.
    if "json" not in lowered:
        return content
    try:
        data = json.loads(content.decode("utf-8"))
    except Exception:
        return content
    if not isinstance(data, dict):
        raise RuntimeError(f"{provider.name} returned JSON but not an object")

    for field in ("audio_base64", "audio", "b64_json"):
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            return base64.b64decode(value)

    for field in ("audio_url", "url"):
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            with urllib.request.urlopen(value, timeout=timeout) as response:
                return response.read()

    raise RuntimeError(f"{provider.name} returned JSON without audio_base64/audio_url")


def _absolute_url(api_base: str, endpoint: str) -> str:
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    return api_base.rstrip("/") + "/" + endpoint.lstrip("/")


def _should_try_next_provider(error: ProviderAPIError) -> bool:
    if error.code is None:
        return True
    if error.code in FALLBACK_HTTP_CODES:
        return True
    details = error.details.lower()
    return any(token in details for token in ("quota_exceeded", "paid_plan_required", "credits", "rate_limit", "limited_access"))


def _provider_quota_exhausted(error: ProviderAPIError) -> bool:
    """Whether this API key should be skipped for the rest of the run.

    The request layer already retries transient 425/429/5xx responses. Once a
    key still fails here, advancing to the next configured key gives the batch a
    chance to finish instead of hammering the same exhausted/limited account for
    every remaining asset.
    """
    details = error.details.lower()
    if error.code in {425, 429}:
        return True
    if error.code in {401, 403} and any(
        token in details
        for token in ("invalid_api_key", "invalid api key", "unauthorized", "forbidden", "xi-api-key")
    ):
        return True
    quota_tokens = (
        "quota",
        "quota_exceeded",
        "credit",
        "credits",
        "0 credits",
        "credits remaining",
        "character limit",
        "characters limit",
        "monthly limit",
        "usage limit",
        "rate_limit",
        "rate limit",
        "too many requests",
        "tooearly",
        "too early",
        "billing hard limit",
        "subscription limit",
    )
    return any(token in details for token in quota_tokens)


def _provider_kind_unavailable(error: ProviderAPIError, kind: str) -> bool:
    details = error.details.lower()
    if kind == "music" and ("paid_plan_required" in details or "music api is not available" in details):
        return True
    return False


def _short_error(error: Exception, max_len: int = 220) -> str:
    text = str(error).replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _print_dry_run(assets: list[dict[str, Any]], output_root: Path, defaults: dict[str, Any], providers: list[ProviderSpec], force: bool) -> None:
    print(f"Providers actifs: {', '.join(provider.name for provider in providers) if providers else '(aucun)'}")
    for asset in assets:
        kind = _required_string(asset, "kind")
        output_path = output_root / _required_string(asset, "file")
        if force and output_path.exists():
            planned_status = "regenerate"
        elif output_path.exists() and _existing_file_is_usable(output_path, asset):
            planned_status = "skip-existing"
        elif output_path.exists():
            planned_status = "regenerate-invalid"
        else:
            planned_status = "generate"
        endpoint, body = _planned_request(asset, defaults)
        supported = [provider.name for provider in providers if kind in provider.supports]
        print(f"DRY {kind:13} {asset['id']:32} [{planned_status}] -> {output_path}")
        print(f"     providers: {', '.join(supported) if supported else '(none)'}")
        print(f"     endpoint: {endpoint}")
        print(f"     body: {_redacted_json(body)}")
    print(f"Planned assets: {len(assets)}")


def _planned_request(asset: dict[str, Any], defaults_raw: Any) -> tuple[str, dict[str, Any]]:
    defaults = defaults_raw if isinstance(defaults_raw, dict) else {}
    kind = _required_string(asset, "kind")
    if kind == "sound_effect":
        return _elevenlabs_sfx_request(asset, defaults.get("sound_effects", {}))
    if kind == "music":
        return _elevenlabs_music_request(asset, defaults.get("music", {}))
    raise ValueError(f"Unsupported kind: {kind}")


def _manifest_entry(output_root: Path, asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "sound_id": _required_string(asset, "id"),
        "path": str((output_root / _required_string(asset, "file")).as_posix()),
        "source": "ElevenLabs generated audio",
        "license": "ElevenLabs generated; verify provider/plan terms before distribution",
        "category": _required_string(asset, "category"),
        "loop": bool(asset.get("loop", False)),
        "default_volume": float(asset.get("volume", 0.5)),
        "priority": int(asset.get("priority", 40)),
        "notes": _required_string(asset, "prompt"),
    }


def _existing_sound_effect_manifest_entries(output_root: Path, spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every generated SFX file that exists, independent of CLI filters.

    A filtered run such as ``--kind music`` should not erase the generated SFX
    manifest. Music stays out of this sound manifest because runtime music is
    handled separately by ``pygame_music``.
    """
    return [
        _manifest_entry(output_root, asset)
        for asset in _selected_assets(spec, set(), "sound_effect")
        if (output_root / _required_string(asset, "file")).exists()
    ]


def _merge_manifest(path: Path, generated_entries: list[dict[str, Any]]) -> None:
    existing = _load_json(path) if path.exists() else []
    if not isinstance(existing, list):
        raise ValueError(f"Expected list in {path}")
    generated_by_id = {entry["sound_id"]: entry for entry in generated_entries}
    merged = [entry for entry in existing if not isinstance(entry, dict) or entry.get("sound_id") not in generated_by_id]
    merged.extend(generated_entries)
    _write_json(path, merged)


def _selected_assets(spec: dict[str, Any], only: set[str], kind: str | None) -> list[dict[str, Any]]:
    raw_assets = spec.get("assets")
    if not isinstance(raw_assets, list):
        raise ValueError("Spec must contain an assets list")
    assets = [asset for asset in raw_assets if isinstance(asset, dict)]
    if only:
        assets = [asset for asset in assets if asset.get("id") in only]
    if kind is not None:
        assets = [asset for asset in assets if asset.get("kind") == kind]
    return assets


def _validate_spec(spec: Any) -> None:
    if not isinstance(spec, dict):
        raise ValueError("Spec must be a JSON object")
    _required_string(spec, "output_dir")
    _required_string(spec, "generated_manifest")
    assets = spec.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("Spec must contain a non-empty assets list")

    seen: set[str] = set()
    for index, asset in enumerate(assets, start=1):
        if not isinstance(asset, dict):
            raise ValueError(f"Asset #{index} must be an object")
        asset_id = _required_string(asset, "id")
        if asset_id in seen:
            raise ValueError(f"Duplicate asset id: {asset_id}")
        seen.add(asset_id)
        kind = _required_string(asset, "kind")
        if kind not in {"sound_effect", "music"}:
            raise ValueError(f"Unsupported kind for {asset_id}: {kind}")
        _required_string(asset, "category")
        _required_string(asset, "file")
        _required_string(asset, "prompt")
        duration = _optional_float(asset.get("duration_seconds"))
        if duration is not None:
            if kind == "sound_effect" and not 0.5 <= duration <= 30.0:
                raise ValueError(f"duration_seconds for {asset_id} must be between 0.5 and 30.0")
            if kind == "music" and not 3.0 <= duration <= 600.0:
                raise ValueError(f"duration_seconds for {asset_id} must be between 3.0 and 600.0")


def _prompt_text(asset: dict[str, Any], defaults: dict[str, Any]) -> str:
    prompt = _required_string(asset, "prompt").strip()
    prefix = str(asset.get("prompt_prefix", defaults.get("prompt_prefix", ""))).strip()
    suffix = str(asset.get("prompt_suffix", defaults.get("prompt_suffix", ""))).strip()
    parts = [part for part in (prefix, prompt, suffix) if part]
    return " ".join(parts)


def _existing_file_is_usable(path: Path, asset: dict[str, Any]) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    try:
        _validate_audio_bytes(path.read_bytes(), asset)
    except Exception:
        return False
    return True


def _validate_audio_bytes(audio: bytes, asset: dict[str, Any]) -> None:
    asset_id = _required_string(asset, "id")
    if not audio:
        raise RuntimeError(f"{asset_id} returned an empty audio file")
    stripped = audio[:256].lstrip().lower()
    if stripped.startswith(b"{") or stripped.startswith(b"<html") or stripped.startswith(b"<!doctype html"):
        raise RuntimeError(f"{asset_id} returned non-audio response bytes")

    expected_duration = _optional_float(asset.get("duration_seconds"))
    minimum_bytes = _minimum_audio_bytes(expected_duration)
    if len(audio) < minimum_bytes:
        raise RuntimeError(
            f"{asset_id} audio is too small to be complete: {len(audio)} bytes, expected at least {minimum_bytes}"
        )

    measured_duration = _probe_audio_duration_seconds(audio)
    if measured_duration is None or expected_duration is None:
        return
    minimum_duration = max(0.1, min(expected_duration - 0.05, expected_duration * 0.85))
    if measured_duration < minimum_duration:
        raise RuntimeError(
            f"{asset_id} audio is too short: {measured_duration:.2f}s, expected about {expected_duration:.2f}s"
        )


def _minimum_audio_bytes(expected_duration: float | None) -> int:
    if expected_duration is None:
        return 2048
    # Conservative floor for compressed MP3/Opus responses. Real 128 kbps MP3 is
    # much larger; this only catches empty, truncated, or error-body files.
    return max(2048, int(expected_duration * 4000))


def _probe_audio_duration_seconds(audio: bytes) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(audio)
    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(temp_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        if completed.returncode != 0:
            return None
        text = completed.stdout.strip()
        return float(text) if text else None
    except Exception:
        return None
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass

def _record_state(state: dict[str, Any], state_path: Path, asset: dict[str, Any], result: GenerationResult, attempts: Any) -> None:
    assets_state = state.setdefault("assets", {})
    assets_state[result.asset_id] = {
        "status": "failed" if result.failed else "skipped" if result.skipped else "ok",
        "path": str(result.output_path.as_posix()),
        "provider": result.provider_name,
        "error": result.error,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "kind": asset.get("kind"),
        "attempts": attempts,
    }
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(state_path, state)


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"assets": {}}
    data = _load_json(path)
    if isinstance(data, dict):
        data.setdefault("assets", {})
        return data
    return {"assets": {}}


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing required string: {key}")
    return value


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _resolve(project_root: Path, path: str) -> Path:
    parsed = Path(path)
    return parsed if parsed.is_absolute() else project_root / parsed


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temporary_path.replace(path)


def _redacted_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    raise SystemExit(main())








