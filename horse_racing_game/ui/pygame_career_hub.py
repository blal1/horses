import os
from dataclasses import dataclass
from pathlib import Path

import pygame

from horse_racing_game.app.career import MAX_CAREER_ENERGY, career_title
from horse_racing_game.app.career_depth import (
    DEFAULT_CAREER_CONTRACTS,
    CareerContract,
    CareerProfile,
    career_condition_risk,
    career_condition_status,
)
from horse_racing_game.app.championship import championship_title, load_championship_calendar, next_championship_race
from horse_racing_game.app.progress import (
    GameProgress,
    record_career_contract,
    record_stable_staff_hire,
    record_stable_upgrade_purchase,
)
from horse_racing_game.app.stable_management import (
    DEFAULT_STABLE_UPGRADES,
    DEFAULT_STABLE_STAFF,
    StaffMember,
    StableManagementState,
    StableUpgrade,
    SupplyInventory,
    stable_rest_energy_gain,
)
from horse_racing_game.audio.pygame_backend import PygameAudioBackend
from horse_racing_game.content.loaders import load_sound_catalog, load_stables
from horse_racing_game.ui.menu_models import MenuSelection


CAREER_HUB_UPGRADES = DEFAULT_STABLE_UPGRADES
CAREER_HUB_STAFF = DEFAULT_STABLE_STAFF


@dataclass(frozen=True)
class CareerHubResult:
    selection: MenuSelection | None

    @classmethod
    def start(cls, selection: MenuSelection) -> "CareerHubResult":
        return cls(selection)

    @classmethod
    def back(cls) -> "CareerHubResult":
        return cls(None)


class PygameCareerHubScreen:
    def __init__(
        self,
        content_root: Path,
        project_root: Path,
        progress: GameProgress,
        selection: MenuSelection,
    ) -> None:
        self._content_root = content_root
        self._project_root = project_root
        self._progress = progress
        self._selection = selection
        self._calendar = load_championship_calendar(content_root / "championship.json")
        self._stables = load_stables(content_root / "stables.json")
        catalog = load_sound_catalog(content_root / "sound_manifest.json")
        self._audio = PygameAudioBackend(project_root, catalog)
        self._selected_row = {"career": 0, "career_training": 1, "career_rest": 2}.get(selection.mode, 0)
        self._contract_index = self._initial_contract_index()
        self._upgrade_index = self._initial_upgrade_index()
        self._staff_index = self._initial_staff_index()

    def run(self) -> MenuSelection | None:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "centered")
        pygame.init()
        screen = pygame.display.set_mode((980, 640), pygame.SHOWN)
        pygame.display.set_caption("Horse Racing - Career Hub")
        clock = pygame.time.Clock()
        title_font = pygame.font.Font(None, 52)
        body_font = pygame.font.Font(None, 28)
        small_font = pygame.font.Font(None, 22)
        self._speak_selection()

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    result = self._handle_keydown(event.key)
                    if result is not None:
                        pygame.quit()
                        return result.selection
                elif event.type == pygame.MOUSEBUTTONUP:
                    result = self._handle_click(event.pos)
                    if result is not None:
                        pygame.quit()
                        return result.selection

            self._draw(screen, title_font, body_font, small_font)
            pygame.display.flip()
            clock.tick(60)

        pygame.quit()
        return None

    def _handle_keydown(self, key: int) -> CareerHubResult | None:
        if key in {pygame.K_ESCAPE, pygame.K_q, pygame.K_m}:
            self._audio.speak("Back to the menu.", 80)
            return CareerHubResult.back()
        if key in {pygame.K_UP, pygame.K_w}:
            self._selected_row = (self._selected_row - 1) % len(self._rows())
            self._speak_selection()
        elif key in {pygame.K_DOWN, pygame.K_s, pygame.K_TAB}:
            self._selected_row = (self._selected_row + 1) % len(self._rows())
            self._speak_selection()
        elif key in {pygame.K_LEFT, pygame.K_a} and self._selected_row == 3:
            self._cycle_contract(-1)
            self._speak_selection()
        elif key in {pygame.K_RIGHT, pygame.K_d} and self._selected_row == 3:
            self._cycle_contract(1)
            self._speak_selection()
        elif key in {pygame.K_LEFT, pygame.K_a} and self._selected_row == 5:
            self._cycle_upgrade(-1)
            self._speak_selection()
        elif key in {pygame.K_RIGHT, pygame.K_d} and self._selected_row == 5:
            self._cycle_upgrade(1)
            self._speak_selection()
        elif key in {pygame.K_LEFT, pygame.K_a} and self._selected_row == 7:
            self._cycle_staff(-1)
            self._speak_selection()
        elif key in {pygame.K_RIGHT, pygame.K_d} and self._selected_row == 7:
            self._cycle_staff(1)
            self._speak_selection()
        elif key in {pygame.K_RETURN, pygame.K_SPACE}:
            if self._selected_row == 0:
                if self._progress.career_injury_days > 0:
                    self._audio.speak("Your horse is injured. Rest before racing.", 90)
                    return None
                self._audio.speak("Starting the next career race.", 90)
                return CareerHubResult.start(self._selection_for("career"))
            if self._selected_row == 1:
                if self._progress.career_injury_days > 0:
                    self._audio.speak("Your horse is injured. Rest before training.", 90)
                    return None
                if self._progress.career_energy <= 0:
                    self._audio.speak("No career energy left. Rest first.", 90)
                    return None
                self._audio.speak("Starting career training.", 90)
                return CareerHubResult.start(self._selection_for("career_training"))
            if self._selected_row == 2:
                if self._progress.career_energy >= MAX_CAREER_ENERGY:
                    self._audio.speak("Career energy is already full.", 90)
                    return None
                self._audio.speak("Resting at the stable.", 90)
                return CareerHubResult.start(self._selection_for("career_rest"))
            if self._selected_row == 3:
                self._cycle_contract(1)
                self._speak_selection()
                return None
            if self._selected_row == 4:
                contract = self._selected_contract()
                if not contract.is_available(self._career_profile().reputation):
                    self._audio.speak(
                        f"{contract.sponsor_id} is locked. Reputation {contract.required_reputation} required.",
                        90,
                    )
                    return None
                if self._progress.active_career_contract_id == contract.contract_id:
                    self._audio.speak(f"{contract.sponsor_id} is already signed.", 90)
                    return None
                self._progress = record_career_contract(self._project_root, self._progress, contract.contract_id)
                self._audio.speak(f"Signed contract with {contract.sponsor_id}.", 90)
                return None
            if self._selected_row == 5:
                self._cycle_upgrade(1)
                self._speak_selection()
                return None
            if self._selected_row == 6:
                upgrade = self._selected_upgrade()
                if upgrade.upgrade_id in self._progress.stable_upgrade_ids:
                    self._audio.speak(f"{upgrade.upgrade_id} is already owned.", 90)
                    return None
                try:
                    self._progress = record_stable_upgrade_purchase(
                        self._project_root,
                        self._progress,
                        upgrade.upgrade_id,
                        upgrade.cost,
                    )
                except ValueError:
                    self._audio.speak(f"Need {upgrade.cost} rewards for {upgrade.upgrade_id}.", 90)
                    return None
                self._audio.speak(f"Purchased stable upgrade {upgrade.upgrade_id}.", 90)
                return None
            if self._selected_row == 7:
                self._cycle_staff(1)
                self._speak_selection()
                return None
            if self._selected_row == 8:
                staff_member = self._selected_staff_member()
                if staff_member.staff_id in self._progress.stable_staff_ids:
                    self._audio.speak(f"{staff_member.staff_id} is already hired.", 90)
                    return None
                try:
                    self._progress = record_stable_staff_hire(
                        self._project_root,
                        self._progress,
                        staff_member.staff_id,
                        staff_member.weekly_cost,
                    )
                except ValueError:
                    self._audio.speak(f"Need {staff_member.weekly_cost} rewards to hire {staff_member.staff_id}.", 90)
                    return None
                self._audio.speak(f"Hired {staff_member.staff_id}.", 90)
                return None
            self._audio.speak("Back to the menu.", 80)
            return CareerHubResult.back()
        return None

    def _handle_click(self, position: tuple[int, int]) -> CareerHubResult | None:
        for row_index in range(len(self._rows())):
            if self._option_rect(row_index).collidepoint(position):
                self._selected_row = row_index
                return self._handle_keydown(pygame.K_RETURN)
        return None

    def _selection_for(self, mode: str) -> MenuSelection:
        return MenuSelection(
            player_horse_id=self._selection.player_horse_id,
            track_id=self._selection.track_id,
            weather_id=self._selection.weather_id,
            audio_mix_id=self._selection.audio_mix_id,
            stable_id=self._selection.stable_id,
            difficulty_id=self._selection.difficulty_id,
            mode=mode,
        )

    def _speak_selection(self) -> None:
        self._audio.speak(self._selection_text(), 75)

    def _selection_text(self) -> str:
        if self._selected_row == 0:
            contract = self._active_contract()
            upkeep = self._stable_management_state().weekly_cost()
            net_win = max(0, contract.prize_for_rank(1) - upkeep)
            return (
                "Career race. Press enter to run the next championship event. "
                f"Current contract pays {contract.prize_for_rank(1)} for a win. "
                f"Staff upkeep will deduct {upkeep}; projected contract net {net_win}. "
                f"Condition {self._condition_status()}, injury risk {self._condition_risk()} percent."
            )
        if self._selected_row == 1:
            stable_state = self._stable_management_state()
            return (
                "Career training. Spend one energy. Press enter to improve the selected horse. "
                f"Stable training bonus {stable_state.training_effect_bonus('speed'):.2f}. "
                f"Condition {self._condition_status()}, injury risk {self._condition_risk()} percent."
            )
        if self._selected_row == 2:
            return (
                f"Career rest. Recover {self._rest_energy_gain()} energy and reduce fatigue. "
                "Press enter to return fresh."
            )
        if self._selected_row == 3:
            contract = self._selected_contract()
            status = self._contract_status(contract)
            return (
                f"Choose contract. {contract.sponsor_id}. "
                f"{status}. Requires reputation {contract.required_reputation}. Win pays {contract.prize_for_rank(1)}. "
                "Press enter or right to change."
            )
        if self._selected_row == 4:
            contract = self._selected_contract()
            status = self._contract_status(contract)
            return f"Contract. {contract.sponsor_id}, {status}. Press enter to sign."
        if self._selected_row == 5:
            upgrade = self._selected_upgrade()
            return (
                f"Choose upgrade. {upgrade.upgrade_id}, {self._upgrade_status(upgrade)}. "
                f"Costs {upgrade.cost} rewards. Press enter or right to change."
            )
        if self._selected_row == 6:
            upgrade = self._selected_upgrade()
            return f"Stable upgrade. {upgrade.upgrade_id}, {self._upgrade_status(upgrade)}. Press enter to buy."
        if self._selected_row == 7:
            staff_member = self._selected_staff_member()
            return (
                f"Choose staff. {staff_member.staff_id}, {self._staff_status(staff_member)}. "
                f"Costs {staff_member.weekly_cost} rewards. Press enter or right to change."
            )
        if self._selected_row == 8:
            staff_member = self._selected_staff_member()
            return f"Stable staff. {staff_member.staff_id} costs {staff_member.weekly_cost} rewards. Press enter to hire."
        return "Back to menu. Press enter to return."

    def _draw(
        self,
        screen: pygame.Surface,
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        screen.fill((18, 24, 30))
        screen.blit(title_font.render("Career Hub", True, (248, 240, 205)), (58, 42))
        screen.blit(
            small_font.render("Up/Down: choice | Enter/Space: activate | Esc/Q/M: menu", True, (245, 220, 130)),
            (62, 92),
        )

        left = pygame.Rect(58, 132, 410, 430)
        right = pygame.Rect(510, 132, 410, 430)
        for rect, label in ((left, "Season"), (right, "Stable")):
            pygame.draw.rect(screen, (31, 40, 48), rect, border_radius=6)
            pygame.draw.rect(screen, (84, 102, 116), rect, width=2, border_radius=6)
            screen.blit(body_font.render(label, True, (246, 238, 210)), (rect.left + 20, rect.top + 18))

        for index, line in enumerate(self._season_lines()):
            screen.blit(small_font.render(line, True, (198, 216, 218)), (left.left + 22, left.top + 64 + index * 32))
        for index, line in enumerate(self._stable_lines()):
            screen.blit(small_font.render(line, True, (198, 216, 218)), (right.left + 22, right.top + 64 + index * 32))

        panel = pygame.Rect(58, 576, 862, 44)
        pygame.draw.rect(screen, (26, 34, 42), panel, border_radius=6)
        pygame.draw.rect(screen, (94, 112, 130), panel, width=2, border_radius=6)
        screen.blit(body_font.render("Choices", True, (246, 238, 210)), (panel.left + 18, panel.top + 8))
        screen.blit(small_font.render(self._selection_text(), True, (172, 218, 232)), (panel.left + 120, panel.top + 13))

        for row_index, row in enumerate(self._rows()):
            rect = self._option_rect(row_index)
            selected = row_index == self._selected_row
            color = (64, 78, 90) if selected else (34, 42, 50)
            border = (246, 214, 110) if selected else (82, 98, 110)
            pygame.draw.rect(screen, color, rect, border_radius=6)
            pygame.draw.rect(screen, border, rect, width=2, border_radius=6)
            label = small_font.render(row[0], True, (238, 242, 232))
            value = small_font.render(row[1], True, (172, 218, 232))
            screen.blit(label, (rect.left + 16, rect.top + 5))
            screen.blit(value, (rect.left + 170, rect.top + 5))

    def _season_lines(self) -> tuple[str, ...]:
        next_race = next_championship_race(self._calendar, self._progress.career_races_completed)
        profile = self._career_profile()
        contract = self._active_contract()
        lines = [
            career_title(self._progress.career_points, self._progress.career_races_completed, len(self._calendar)),
            f"Energy: {self._progress.career_energy}/{MAX_CAREER_ENERGY} | Rewards: {self._progress.career_rewards}",
            f"Condition: {self._condition_status()} | Injury risk: {self._condition_risk()}%",
            f"Reputation: {profile.reputation} | Prize money: {profile.prize_money}",
            f"Contract: {contract.sponsor_id} | Win pays {contract.prize_for_rank(1)}",
            f"Selected contract: {self._selected_contract().sponsor_id} | {self._contract_status(self._selected_contract())}",
            f"Projected win net after staff upkeep: {self._projected_contract_win_net()}",
            f"Signed: {self._progress.active_career_contract_id or 'none'}",
            f"Training level: {self._progress.horse_training_levels.get(self._selection.player_horse_id, 0)}",
            f"Difficulty: {self._selection.difficulty_id}",
        ]
        if next_race is None:
            lines.append("Next race: season complete.")
        else:
            lines.append(championship_title(self._calendar, self._progress.career_races_completed, self._progress.career_points))
            lines.append(f"Next race track: {next_race.track_id} | weather: {next_race.weather_id}")
        return tuple(lines)

    def _stable_lines(self) -> tuple[str, ...]:
        stable = next((item for item in self._stables if item.stable_id == self._selection.stable_id), None)
        stable_state = self._stable_management_state()
        if stable is None:
            return (
                f"Stable ID: {self._selection.stable_id}",
                "Unknown stable.",
                f"Funds: {stable_state.funds}",
                "Choose race, training, or rest.",
            )
        return (
            stable.name,
            f"Focus: {stable.focus}",
            f"Funds: {stable_state.funds} | Weekly cost: {stable_state.weekly_cost()}",
            f"Next race upkeep warning: {stable_state.weekly_cost()} rewards",
            f"Rest recovery: +{self._rest_energy_gain()} energy",
            f"Rest health: -{self._rest_energy_gain() * 20} fatigue | injury -{self._rest_energy_gain()} day(s)",
            f"Training bonus: {stable_state.training_effect_bonus('speed'):.2f} | Vet recovery: {stable_state.vet_recovery_bonus():.2f}",
            "Staff tradeoff: trainers improve training; vets reduce condition risk; upkeep lowers race net.",
            f"Upgrades: {len(self._progress.stable_upgrade_ids)} owned",
            f"Staff: {len(self._progress.stable_staff_ids)} hired",
            f"Supplies: {stable_state.supplies.feed_units} feed, {stable_state.supplies.medicine_units} medicine",
            stable.description,
            "Race for points, train for pace, rest for energy.",
        )

    def _rows(self) -> tuple[tuple[str, str], ...]:
        return (
            ("Career race", "run the next championship event"),
            ("Career training", "spend one energy"),
            ("Career rest", "recover one energy"),
            ("Choose contract", "cycle available sponsors"),
            ("Sign contract", "persist selected sponsor"),
            ("Choose upgrade", "cycle stable facilities"),
            ("Buy upgrade", "spend rewards on selected facility"),
            ("Choose staff", "cycle stable staff"),
            ("Hire staff", "spend rewards on selected staff"),
            ("Back", "return to the main menu"),
        )

    def _option_rect(self, row_index: int) -> pygame.Rect:
        return pygame.Rect(58, 270 + row_index * 30, 862, 26)

    def _career_profile(self) -> CareerProfile:
        reputation = self._progress.career_points + self._progress.wins * 3 + self._progress.podiums
        return CareerProfile(reputation=reputation, prize_money=self._progress.career_rewards)

    def _active_contract(self) -> CareerContract:
        if self._progress.active_career_contract_id:
            for contract in DEFAULT_CAREER_CONTRACTS:
                if contract.contract_id == self._progress.active_career_contract_id:
                    return contract
        return self._selected_contract()

    def _available_contracts(self) -> tuple[CareerContract, ...]:
        profile = self._career_profile()
        available = tuple(contract for contract in DEFAULT_CAREER_CONTRACTS if contract.is_available(profile.reputation))
        return available or (DEFAULT_CAREER_CONTRACTS[0],)

    def _best_available_contract(self) -> CareerContract:
        return self._available_contracts()[-1]

    def _selected_contract(self) -> CareerContract:
        return DEFAULT_CAREER_CONTRACTS[self._contract_index % len(DEFAULT_CAREER_CONTRACTS)]

    def _cycle_contract(self, direction: int) -> None:
        self._contract_index = (self._contract_index + direction) % len(DEFAULT_CAREER_CONTRACTS)

    def _initial_contract_index(self) -> int:
        if self._progress.active_career_contract_id:
            for index, contract in enumerate(DEFAULT_CAREER_CONTRACTS):
                if contract.contract_id == self._progress.active_career_contract_id:
                    return index
        best = self._best_available_contract()
        return next((index for index, contract in enumerate(DEFAULT_CAREER_CONTRACTS) if contract.contract_id == best.contract_id), 0)

    def _contract_status(self, contract: CareerContract) -> str:
        if self._progress.active_career_contract_id == contract.contract_id:
            return "signed"
        if contract.is_available(self._career_profile().reputation):
            return "available"
        return f"locked, reputation {contract.required_reputation} required"

    def _projected_contract_win_net(self) -> int:
        return max(0, self._active_contract().prize_for_rank(1) - self._stable_management_state().weekly_cost())

    def _rest_energy_gain(self) -> int:
        return stable_rest_energy_gain(self._progress.stable_upgrade_ids, self._progress.stable_staff_ids)

    def _condition_status(self) -> str:
        return career_condition_status(self._progress.career_fatigue, self._progress.career_injury_days)

    def _condition_risk(self) -> int:
        return career_condition_risk(
            self._progress.career_fatigue,
            self._progress.career_energy,
            self._progress.stable_staff_ids,
        )

    def _next_upgrade(self) -> StableUpgrade | None:
        for upgrade in CAREER_HUB_UPGRADES:
            if upgrade.upgrade_id not in self._progress.stable_upgrade_ids:
                return upgrade
        return None

    def _selected_upgrade(self) -> StableUpgrade:
        return CAREER_HUB_UPGRADES[self._upgrade_index % len(CAREER_HUB_UPGRADES)]

    def _cycle_upgrade(self, direction: int) -> None:
        self._upgrade_index = (self._upgrade_index + direction) % len(CAREER_HUB_UPGRADES)

    def _initial_upgrade_index(self) -> int:
        next_upgrade = self._next_upgrade()
        if next_upgrade is None:
            return 0
        return next((index for index, upgrade in enumerate(CAREER_HUB_UPGRADES) if upgrade.upgrade_id == next_upgrade.upgrade_id), 0)

    def _upgrade_status(self, upgrade: StableUpgrade) -> str:
        return "owned" if upgrade.upgrade_id in self._progress.stable_upgrade_ids else "available"

    def _next_staff_member(self) -> StaffMember | None:
        for staff_member in CAREER_HUB_STAFF:
            if staff_member.staff_id not in self._progress.stable_staff_ids:
                return staff_member
        return None

    def _selected_staff_member(self) -> StaffMember:
        return CAREER_HUB_STAFF[self._staff_index % len(CAREER_HUB_STAFF)]

    def _cycle_staff(self, direction: int) -> None:
        self._staff_index = (self._staff_index + direction) % len(CAREER_HUB_STAFF)

    def _initial_staff_index(self) -> int:
        next_staff = self._next_staff_member()
        if next_staff is None:
            return 0
        return next((index for index, staff_member in enumerate(CAREER_HUB_STAFF) if staff_member.staff_id == next_staff.staff_id), 0)

    def _staff_status(self, staff_member: StaffMember) -> str:
        return "hired" if staff_member.staff_id in self._progress.stable_staff_ids else "available"

    def _stable_management_state(self) -> StableManagementState:
        funds = self._progress.career_rewards + self._progress.career_points * 2
        upgrades = tuple(upgrade for upgrade in CAREER_HUB_UPGRADES if upgrade.upgrade_id in self._progress.stable_upgrade_ids)
        staff = tuple(staff_member for staff_member in CAREER_HUB_STAFF if staff_member.staff_id in self._progress.stable_staff_ids)
        supplies = SupplyInventory(feed_units=max(0, self._progress.career_energy + 1), medicine_units=max(0, self._progress.podiums))
        return StableManagementState(
            stable_id=self._selection.stable_id,
            funds=funds,
            upgrades=upgrades,
            staff=staff,
            supplies=supplies,
            horse_specializations={self._selection.player_horse_id: "speed"},
        )
