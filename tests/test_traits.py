import unittest

from horse_racing_game.domain.horse import Horse, HorseStats
from horse_racing_game.domain.track import Track, TrackSegment
from horse_racing_game.domain.weather import Weather
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.simulation.race_engine import RaceEngine
from horse_racing_game.simulation.traits import trait_effect


def _stats() -> HorseStats:
    return HorseStats(
        max_speed_mps=17.0,
        acceleration=8.0,
        stamina_capacity=80.0,
        stamina_recovery=4.0,
        handling=8.0,
        nervousness=3.0,
    )


def _horse(horse_id: str, traits: tuple[str, ...]) -> Horse:
    return Horse(
        horse_id=horse_id,
        name=horse_id.replace("_", " ").title(),
        role="player",
        preferred_surface="turf",
        signature_sound="sig",
        stats=_stats(),
        traits=traits,
    )


def _track() -> Track:
    return Track(
        track_id="t",
        name="Test",
        length_m=400.0,
        surface="turf",
        lanes=4,
        handedness="left",
        final_stretch_start_m=300.0,
        audio_profile={},
        segments=(
            TrackSegment(0.0, 200.0, "none", 0.0, 0.0, "a"),
            TrackSegment(200.0, 280.0, "left", 0.5, 0.0, "b"),
            TrackSegment(280.0, 400.0, "none", 0.0, 0.0, "c"),
        ),
    )


def _run_distance(traits: tuple[str, ...], weather: Weather, ticks: int = 40) -> float:
    # Sample distance partway through (before the finish saturates at length_m)
    # so trait-driven differences in pace are observable.
    horse = _horse("subject", traits)
    engine = RaceEngine(_track(), (horse,), "subject", seed=7, weather=weather)
    command = RaceCommand(throttle_delta=1.0, push_requested=True)
    result = engine.tick(command, 0.25)
    for _ in range(ticks - 1):
        result = engine.tick(command, 0.25)
    return result.state.player().distance_m


class TraitEffectTests(unittest.TestCase):
    def test_unknown_and_stable_traits_are_neutral(self) -> None:
        effect = trait_effect(
            ("totally_made_up", "stable_oak_lane"),
            surface="turf",
            weather_id="clear",
            curve_intensity=0.0,
            in_final_stretch=False,
        )
        self.assertEqual(effect.speed_multiplier, 1.0)
        self.assertEqual(effect.stamina_cost_multiplier, 1.0)
        self.assertEqual(effect.acceleration_multiplier, 1.0)

    def test_endurance_lowers_stamina_cost(self) -> None:
        effect = trait_effect(
            ("endurance",),
            surface="turf",
            weather_id="clear",
            curve_intensity=0.0,
            in_final_stretch=False,
        )
        self.assertLess(effect.stamina_cost_multiplier, 1.0)

    def test_fast_finisher_only_helps_in_final_stretch(self) -> None:
        before = trait_effect(
            ("fast_finisher",), surface="turf", weather_id="clear",
            curve_intensity=0.0, in_final_stretch=False,
        )
        during = trait_effect(
            ("fast_finisher",), surface="turf", weather_id="clear",
            curve_intensity=0.0, in_final_stretch=True,
        )
        self.assertEqual(before.speed_multiplier, 1.0)
        self.assertGreater(during.speed_multiplier, 1.0)

    def test_mud_specialist_only_on_soft_surfaces(self) -> None:
        on_turf = trait_effect(
            ("mud_specialist",), surface="turf", weather_id="clear",
            curve_intensity=0.0, in_final_stretch=False,
        )
        on_mud = trait_effect(
            ("mud_specialist",), surface="mud", weather_id="clear",
            curve_intensity=0.0, in_final_stretch=False,
        )
        self.assertEqual(on_turf.speed_multiplier, 1.0)
        self.assertGreater(on_mud.speed_multiplier, 1.0)

    def test_rain_comfort_only_in_rain(self) -> None:
        clear = trait_effect(
            ("rain_comfort",), surface="turf", weather_id="clear",
            curve_intensity=0.0, in_final_stretch=False,
        )
        rain = trait_effect(
            ("rain_comfort",), surface="turf", weather_id="rain",
            curve_intensity=0.0, in_final_stretch=False,
        )
        self.assertEqual(clear.speed_multiplier, 1.0)
        self.assertGreater(rain.speed_multiplier, 1.0)


class TraitsInEngineTests(unittest.TestCase):
    def test_sprinter_covers_more_ground_than_traitless(self) -> None:
        clear = Weather("clear", "Clear", 1.0, 1.0, 1.0, None)
        plain = _run_distance((), clear)
        sprinter = _run_distance(("sprinter",), clear)
        self.assertGreater(sprinter, plain)

    def test_rain_comfort_helps_in_rain(self) -> None:
        rain = Weather("rain", "Rain", 0.94, 1.14, 0.9, None)
        plain = _run_distance((), rain)
        comfy = _run_distance(("rain_comfort",), rain)
        self.assertGreater(comfy, plain)

    def test_traits_remain_deterministic(self) -> None:
        clear = Weather("clear", "Clear", 1.0, 1.0, 1.0, None)
        first = _run_distance(("sprinter", "fast_finisher"), clear)
        second = _run_distance(("sprinter", "fast_finisher"), clear)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
