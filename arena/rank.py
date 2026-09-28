"""竞技场段位与赛季系统 - 含8个bug"""
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

class ArenaRank:
    def __init__(self):
        self.players: dict[str, ArenaPlayer] = {}
        self.season_end_time: float = 0
        self.decay_threshold = 0  # bug4: 无衰减

    def can_promote(self, pid: str) -> bool:
        # bug1: 只看积分不看胜率
        p = self.players[pid]
        return p.rating >= 1500

    def match_rating(self, pid: str) -> int:
        # bug2: 只看显示分
        return self.players[pid].rating

    def end_season(self, season_id: str):
        # bug3: 不结算不重置
        pass

    def apply_decay(self, pid: str, days_inactive: int):
        # bug4: 无衰减
        pass

    def team_rating(self, players: list[str]) -> int:
        # bug5: 只看队长
        if not players:
            return 0
        return self.players[players[0]].rating

    def promotion_match(self, pid: str, win: bool) -> bool:
        # bug6: 赢一把就晋级
        p = self.players[pid]
        if win:
            p.tier = "silver"
            return True
        return False

    def get_season_reward_tier(self, pid: str) -> str:
        # bug7: 按历史最高
        return self.players[pid].season_high and "diamond" or "bronze"

    def sync_ratings(self, pid: str):
        # bug8: 显示分和隐藏分不一致
        pass
