"""竞技场段位与赛季系统。

修复点：
1. 晋升同时要求积分达标与胜率达标，无法靠堆场次上分；
2. 匹配基于近期表现加权的隐藏分，而非显示段位；
3. 赛季结束强制结算，新赛季积分按比例继承、段位从青铜重新打起；
4. 长期不活跃触发周期性积分衰减，且有衰减下限；
5. 组队匹配使用全队平均隐藏分，并叠加队长近期状态权重；
6. 晋级赛为 BO5，先取 3 胜者晋级，失败有保护（不扣分不掉段）；
7. 赛季奖励按赛季结束时的段位结算，而非历史最高；
8. 显示分与隐藏分保持同步，变化时同步更新并产生变化动画。
"""
from collections import deque
from dataclasses import dataclass, field
import time

TIERS = ["bronze", "silver", "gold", "platinum", "diamond", "king"]

BASE_RATING = 1000
PROMOTION_RATING = 1500
PROMOTION_WINRATE = 0.5

SEASON_INHERIT_RATIO = 0.5

DECAY_STEP = 50
DECAY_FLOOR = 1000

RECENT_WINDOW = 10
FORM_WEIGHT = 10
FORM_CAP = 200

BO5_WINS = 3
BO5_LOSSES = 3


@dataclass
class ArenaPlayer:
    pid: str
    rating: int = 1000
    hidden_rating: int | None = None
    wins: int = 0
    losses: int = 0
    tier: str = "bronze"
    promotion_wins: int = 0
    promotion_losses: int = 0
    season_high: int = 0
    protected: bool = False
    recent_results: deque = field(default_factory=lambda: deque(maxlen=RECENT_WINDOW))

    def __post_init__(self):
        if self.hidden_rating is None:
            self.hidden_rating = self.rating
        if self.season_high < self.rating:
            self.season_high = self.rating

    @property
    def total_games(self) -> int:
        return self.wins + self.losses

    @property
    def winrate(self) -> float:
        return self.wins / self.total_games if self.total_games else 0.0


class ArenaRank:
    def __init__(self):
        self.players: dict[str, ArenaPlayer] = {}
        self.season_end_time: float = 0
        self.current_season: str | None = None
        self.decay_threshold = 0
        self.season_rewards: dict[str, str] = {}
        self.animations: list[dict] = []

    def can_promote(self, pid: str) -> bool:
        p = self.players[pid]
        if p.tier == TIERS[-1]:
            return False
        return (
            p.rating >= PROMOTION_RATING
            and p.total_games > 0
            and p.winrate >= PROMOTION_WINRATE
        )

    def _recent_form(self, p: ArenaPlayer) -> int:
        results = list(p.recent_results)
        if not results:
            return 0
        net = sum(1 if win else -1 for win in results)
        return max(-FORM_CAP, min(FORM_CAP, net * FORM_WEIGHT))

    def match_rating(self, pid: str) -> int:
        p = self.players[pid]
        return int(p.hidden_rating) + self._recent_form(p)

    def record_match(self, pid: str, win: bool, opponent_rating: int, k: int = 32) -> int:
        p = self.players[pid]
        expected = 1.0 / (1.0 + 10 ** ((opponent_rating - p.hidden_rating) / 400.0))
        score = 1.0 if win else 0.0
        delta = int(round(k * (score - expected)))
        p.hidden_rating = max(0, p.hidden_rating + delta)
        if win:
            p.wins += 1
        else:
            p.losses += 1
        p.recent_results.append(win)
        p.season_high = max(p.season_high, p.hidden_rating)
        self._apply_rating(p, p.hidden_rating, "match")
        return delta

    def end_season(self, season_id: str):
        for pid, p in self.players.items():
            self.season_rewards[pid] = p.tier
            inherited = int(
                BASE_RATING + (p.rating - BASE_RATING) * SEASON_INHERIT_RATIO
            )
            inherited = max(BASE_RATING, inherited)
            p.tier = "bronze"
            p.wins = 0
            p.losses = 0
            p.promotion_wins = 0
            p.promotion_losses = 0
            p.protected = False
            p.recent_results.clear()
            self._apply_rating(p, inherited, "season_reset", new_hidden=inherited)
        self.current_season = season_id
        self.season_end_time = time.time()

    def apply_decay(self, pid: str, days_inactive: int):
        if self.decay_threshold <= 0 or days_inactive < self.decay_threshold:
            return
        p = self.players[pid]
        cycles = days_inactive // self.decay_threshold
        decayed = max(DECAY_FLOOR, p.rating - cycles * DECAY_STEP)
        if decayed != p.rating:
            self._apply_rating(p, decayed, "decay", new_hidden=decayed)

    def team_rating(self, players: list[str]) -> int:
        if not players:
            return 0
        ratings = [self.match_rating(pid) for pid in players]
        base = sum(ratings) / len(ratings)
        captain = self.players[players[0]]
        form = self._recent_form(captain)
        captain_factor = 1.0 + max(-0.05, min(0.05, form / FORM_CAP * 0.05))
        return int(round(base * captain_factor))

    def promotion_match(self, pid: str, win: bool) -> bool:
        p = self.players[pid]
        tier_index = TIERS.index(p.tier)
        if tier_index >= len(TIERS) - 1:
            return False
        if win:
            p.promotion_wins += 1
        else:
            p.promotion_losses += 1
        if p.promotion_wins >= BO5_WINS:
            p.tier = TIERS[tier_index + 1]
            p.promotion_wins = 0
            p.promotion_losses = 0
            p.protected = False
            self._log_animation(p, "promotion", p.rating, p.rating)
            return True
        if p.promotion_losses >= BO5_LOSSES:
            p.promotion_wins = 0
            p.promotion_losses = 0
            p.protected = True
            self._log_animation(p, "promotion_failed", p.rating, p.rating)
        return False

    def get_season_reward_tier(self, pid: str) -> str:
        return self.season_rewards.get(pid, self.players[pid].tier)

    def sync_ratings(self, pid: str):
        p = self.players[pid]
        if p.rating != p.hidden_rating:
            self._apply_rating(p, p.hidden_rating, "sync")

    def _apply_rating(self, p: ArenaPlayer, new_rating: int, kind: str, new_hidden: int | None = None):
        old_rating = p.rating
        if new_hidden is not None:
            p.hidden_rating = new_hidden
        p.rating = int(new_rating)
        if old_rating != p.rating:
            self._log_animation(p, kind, old_rating, p.rating)

    def _log_animation(self, p: ArenaPlayer, kind: str, old: int, new: int):
        self.animations.append(
            {
                "pid": p.pid,
                "kind": kind,
                "old": old,
                "new": new,
                "delta": new - old,
                "ts": time.time(),
            }
        )

    def take_animations(self, pid: str | None = None) -> list[dict]:
        if pid is None:
            taken = self.animations
            self.animations = []
            return taken
        taken = [event for event in self.animations if event["pid"] == pid]
        self.animations = [event for event in self.animations if event["pid"] != pid]
        return taken
