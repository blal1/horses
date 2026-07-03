from dataclasses import dataclass


@dataclass(frozen=True)
class AudioMixProfile:
    profile_id: str
    name: str
    music_volume: float
    ambient_volume: float
    show_help_by_default: bool
    tutorial_voice: bool


MIX_PROFILES = (
    AudioMixProfile("normal", "Normal", 0.22, 0.28, True, True),
    AudioMixProfile("descriptive", "Descriptive", 0.16, 0.22, True, True),
    AudioMixProfile("minimal", "Minimal", 0.12, 0.12, False, False),
)


def mix_profile_by_id(profile_id: str) -> AudioMixProfile:
    for profile in MIX_PROFILES:
        if profile.profile_id == profile_id:
            return profile
    return MIX_PROFILES[0]
