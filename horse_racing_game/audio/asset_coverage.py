"""Audio asset coverage — the bridge between cue requirements and generation.

Closes the loop for the generated-audio pipeline:

    cue rules  →  detect which preferred sounds the catalog is missing
               →  emit an ElevenLabs prompt spec for exactly those sounds
               →  scripts/generate_elevenlabs_audio.py produces them
               →  merge into the sound catalog

Everything here is pure (no network, no I/O beyond an optional spec write), so it
is unit-testable and safe to call at startup as a coverage check.
"""

import json
from pathlib import Path

from horse_racing_game.audio.event_cues import cue_sound_requirements
from horse_racing_game.audio.sound_catalog import SoundCatalog


OUTPUT_DIR = "assets/generated/elevenlabs"
GENERATED_MANIFEST = "content/generated_elevenlabs_sound_manifest.json"


def missing_cue_sound_ids(catalog: SoundCatalog) -> tuple[str, ...]:
    """Preferred cue sound ids that are not in the catalog (would fall back)."""
    return tuple(sorted(sid for sid in cue_sound_requirements() if catalog.get(sid) is None))


def coverage_report(catalog: SoundCatalog) -> str:
    requirements = cue_sound_requirements()
    missing = missing_cue_sound_ids(catalog)
    covered = len(requirements) - len(missing)
    if not missing:
        return f"Cue audio coverage: {covered}/{len(requirements)} — all preferred cue sounds present."
    return (
        f"Cue audio coverage: {covered}/{len(requirements)}. "
        f"Missing (will fall back): {', '.join(missing)}."
    )


def prompt_spec_for_missing(catalog: SoundCatalog) -> dict:
    """An ElevenLabs generation spec (compatible with
    ``scripts/generate_elevenlabs_audio.py``) covering only the missing cue
    sounds. ``assets`` is empty when nothing is missing — check before writing,
    since the generator rejects an empty spec."""
    requirements = cue_sound_requirements()
    assets = [
        {
            "id": sound_id,
            "kind": "sound_effect",
            "category": requirements[sound_id],
            "file": f"sfx/{sound_id}.mp3",
            "duration_seconds": 1.5,
            "loop": False,
            "volume": 0.6,
            "priority": 50,
            "prompt": _default_prompt(sound_id, requirements[sound_id]),
        }
        for sound_id in missing_cue_sound_ids(catalog)
    ]
    return {"output_dir": OUTPUT_DIR, "generated_manifest": GENERATED_MANIFEST, "assets": assets}


def write_missing_prompt_spec(catalog: SoundCatalog, path: Path) -> int:
    """Write a generation spec for the missing cues; returns how many were written.
    Writes nothing and returns 0 when coverage is complete."""
    spec = prompt_spec_for_missing(catalog)
    if not spec["assets"]:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return len(spec["assets"])


def _default_prompt(sound_id: str, category: str) -> str:
    readable = sound_id.replace("_", " ")
    return (
        f"Short one-shot {category} sound effect for '{readable}', "
        "clean transient, accessible and non-startling, no music, dry mix, no reverb tail."
    )
