from dataclasses import dataclass

from horse_racing_game.app.difficulty import DEFAULT_DIFFICULTY, DIFFICULTY_TIERS, DifficultyTier
from horse_racing_game.domain.horse import Horse
from horse_racing_game.domain.track import Track
from horse_racing_game.domain.weather import Weather
from horse_racing_game.audio.mix_profile import AudioMixProfile
from horse_racing_game.domain.stable import Stable


MENU_ROW_COUNT = 20


@dataclass(frozen=True)
class MenuSelection:
    player_horse_id: str
    track_id: str
    weather_id: str = "clear"
    audio_mix_id: str = "normal"
    stable_id: str = "oak_lane"
    difficulty_id: str = "pro"
    mode: str = "race"


class PygameMenuState:
    def __init__(
        self,
        horses: tuple[Horse, ...],
        tracks: tuple[Track, ...],
        weather_options: tuple[Weather, ...] = (),
        audio_profiles: tuple[AudioMixProfile, ...] = (),
        stables: tuple[Stable, ...] = (),
        difficulty_tiers: tuple[DifficultyTier, ...] = (),
    ) -> None:
        if not horses:
            raise ValueError("Pygame menu requires at least one horse.")
        if not tracks:
            raise ValueError("Pygame menu requires at least one track.")
        if not weather_options:
            weather_options = (Weather("clear", "Clear", 1.0, 1.0, 1.0, None),)
        if not audio_profiles:
            audio_profiles = (AudioMixProfile("normal", "Normal", 0.22, 0.28, True, True),)
        if not stables:
            stables = (Stable("oak_lane", "Oak Lane Stable", "balanced", "Balanced yard"),)
        if not difficulty_tiers:
            difficulty_tiers = DIFFICULTY_TIERS
        self._horses = horses
        self._tracks = tracks
        self._weather_options = weather_options
        self._audio_profiles = audio_profiles
        self._stables = stables
        self._difficulty_tiers = difficulty_tiers
        self.selected_row = 0
        self.selected_horse_index = 0
        self.selected_track_index = 0
        self.selected_weather_index = 0
        self.selected_audio_profile_index = 0
        self.selected_stable_index = 0
        self.selected_difficulty_index = next(
            (index for index, tier in enumerate(self._difficulty_tiers) if tier.tier_id == DEFAULT_DIFFICULTY.tier_id),
            0,
        )

    @property
    def horses(self) -> tuple[Horse, ...]:
        return self._horses

    @property
    def tracks(self) -> tuple[Track, ...]:
        return self._tracks

    @property
    def weather_options(self) -> tuple[Weather, ...]:
        return self._weather_options

    @property
    def audio_profiles(self) -> tuple[AudioMixProfile, ...]:
        return self._audio_profiles

    @property
    def stables(self) -> tuple[Stable, ...]:
        return self._stables

    @property
    def difficulty_tiers(self) -> tuple[DifficultyTier, ...]:
        return self._difficulty_tiers

    @property
    def selected_horse(self) -> Horse:
        return self._horses[self.selected_horse_index]

    @property
    def selected_track(self) -> Track:
        return self._tracks[self.selected_track_index]

    @property
    def selected_weather(self) -> Weather:
        return self._weather_options[self.selected_weather_index]

    @property
    def selected_audio_profile(self) -> AudioMixProfile:
        return self._audio_profiles[self.selected_audio_profile_index]

    @property
    def selected_stable(self) -> Stable:
        return self._stables[self.selected_stable_index]

    @property
    def selected_difficulty(self) -> DifficultyTier:
        return self._difficulty_tiers[self.selected_difficulty_index]

    def move_row(self, delta: int) -> None:
        self.selected_row = (self.selected_row + delta) % MENU_ROW_COUNT

    def cycle_current_option(self, delta: int) -> None:
        if self.selected_row == 0:
            self.selected_horse_index = (self.selected_horse_index + delta) % len(self._horses)
        elif self.selected_row == 1:
            self.selected_track_index = (self.selected_track_index + delta) % len(self._tracks)
        elif self.selected_row == 2:
            self.selected_weather_index = (self.selected_weather_index + delta) % len(self._weather_options)
        elif self.selected_row == 3:
            self.selected_audio_profile_index = (self.selected_audio_profile_index + delta) % len(self._audio_profiles)
        elif self.selected_row == 4:
            self.selected_stable_index = (self.selected_stable_index + delta) % len(self._stables)
        elif self.selected_row == 5:
            self.selected_difficulty_index = (self.selected_difficulty_index + delta) % len(self._difficulty_tiers)

    def select_ids(
        self,
        horse_id: str,
        track_id: str,
        weather_id: str = "",
        audio_mix_id: str = "",
        stable_id: str = "",
        difficulty_id: str = "",
    ) -> None:
        for index, horse in enumerate(self._horses):
            if horse.horse_id == horse_id:
                self.selected_horse_index = index
                break
        for index, track in enumerate(self._tracks):
            if track.track_id == track_id:
                self.selected_track_index = index
                break
        for index, weather in enumerate(self._weather_options):
            if weather.weather_id == weather_id:
                self.selected_weather_index = index
                break
        for index, profile in enumerate(self._audio_profiles):
            if profile.profile_id == audio_mix_id:
                self.selected_audio_profile_index = index
                break
        for index, stable in enumerate(self._stables):
            if stable.stable_id == stable_id:
                self.selected_stable_index = index
                break
        for index, tier in enumerate(self._difficulty_tiers):
            if tier.tier_id == difficulty_id:
                self.selected_difficulty_index = index
                break

    def selection(self, mode: str = "race") -> MenuSelection:
        return MenuSelection(
            player_horse_id=self.selected_horse.horse_id,
            track_id=self.selected_track.track_id,
            weather_id=self.selected_weather.weather_id,
            audio_mix_id=self.selected_audio_profile.profile_id,
            stable_id=self.selected_stable.stable_id,
            difficulty_id=self.selected_difficulty.tier_id,
            mode=mode,
        )
