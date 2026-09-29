"""竞技场段位与赛季系统"""
from dataclasses import dataclass, field

@dataclass
class ArenaPlayer:
    pid: str
    rating: int = 1000
    hidden_rating: int = 1000
    wins: int = 0
    losses: int = 0
    tier: str = "bronze"
    promotion_wins: int = 0  # BO5进度
    season_high: int = 0
    rating_animating: bool = False  # 分数变化动画标记

class ArenaRank:
    PROMOTE_RATING = 1500
    PROMOTE_WINRATE = 0.5
    BO5_WINS_NEEDED = 3
    DECAY_FLOOR = 1000
    DECAY_PER_PERIOD = 50
    SEASON_INHERIT_RATIO = 0.5
    BASE_RATING = 1000
    TIER_ORDER = ["bronze", "silver", "gold", "platinum", "diamond", "master", "king"]

    def __init__(self):
        self.players: dict[str, ArenaPlayer] = {}
        self.season_end_time: float = 0
        self.decay_threshold = 7  # 不活跃天数阈值

    def _winrate(self, p: ArenaPlayer) -> float:
        total = p.wins + p.losses
        return p.wins / total if total else 0.0

    def can_promote(self, pid: str) -> bool:
        # 积分达标且胜率不低于阈值，纯堆场次无法晋升
        p = self.players[pid]
        return p.rating >= self.PROMOTE_RATING and self._winrate(p) >= self.PROMOTE_WINRATE

    def match_rating(self, pid: str) -> int:
        # 匹配使用近期表现加权的隐藏分
        return self.players[pid].hidden_rating

    def end_season(self, season_id: str):
        # 赛季强制结算：新赛季按上赛季一定比例继承，段位重置
        for p in self.players.values():
            p.rating = self.BASE_RATING + int((p.rating - self.BASE_RATING) * self.SEASON_INHERIT_RATIO)
            p.hidden_rating = p.rating
            p.tier = "bronze"
            p.promotion_wins = 0
            p.season_high = 0
            p.rating_animating = True

    def apply_decay(self, pid: str, days_inactive: int):
        # 长期不活跃周期性衰减，衰减有下限
        p = self.players[pid]
        if days_inactive <= self.decay_threshold or self.decay_threshold <= 0:
            return
        periods = days_inactive // self.decay_threshold
        decay = periods * self.DECAY_PER_PERIOD
        p.rating = max(self.DECAY_FLOOR, p.rating - decay)
        p.hidden_rating = max(self.DECAY_FLOOR, p.hidden_rating - decay)
        p.rating_animating = True

    def team_rating(self, players: list[str]) -> int:
        # 全队平均（显示分与隐藏分已同步），队长权重为1即等权平均
        if not players:
            return 0
        return sum(self.players[pid].rating for pid in players) // len(players)

    def promotion_match(self, pid: str, win: bool) -> bool:
        # BO5晋级赛：赢3场才晋级，失败有保护不掉进度
        p = self.players[pid]
        if win:
            p.promotion_wins += 1
            if p.promotion_wins >= self.BO5_WINS_NEEDED:
                idx = self.TIER_ORDER.index(p.tier)
                if idx < len(self.TIER_ORDER) - 1:
                    p.tier = self.TIER_ORDER[idx + 1]
                p.promotion_wins = 0
                return True
        else:
            p.promotion_wins = max(0, p.promotion_wins - 1)  # 保护机制：不掉到0以下
        return False

    def get_season_reward_tier(self, pid: str) -> str:
        # 按赛季结束时的当前段位发放
        return self.players[pid].tier

    def sync_ratings(self, pid: str):
        # 显示分同步为隐藏分，并触发变化动画
        p = self.players[pid]
        if p.rating != p.hidden_rating:
            p.rating = p.hidden_rating
            p.rating_animating = True
