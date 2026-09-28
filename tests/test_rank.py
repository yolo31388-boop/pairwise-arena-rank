"""竞技场段位与赛季系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from arena.rank import ArenaRank, ArenaPlayer

class TestPromotionRequiresWinrate:
    def test_promotion_checks_winrate(self):
        ar = ArenaRank()
        ar.players["p1"] = ArenaPlayer("p1", rating=1500, wins=5, losses=95)
        assert ar.can_promote("p1") == False  # bug1: 胜率5%也能晋级

class TestMatchUsesHiddenRating:
    def test_match_uses_recent_performance(self):
        ar = ArenaRank()
        # p1显示分高但近期连输，隐藏分应该更低
        ar.players["p1"] = ArenaPlayer("p1", rating=2000, hidden_rating=1500)
        assert ar.match_rating("p1") == 1500  # bug2: 返回2000

class TestSeasonReset:
    def test_season_end_resets_ratings(self):
        ar = ArenaRank()
        ar.players["p1"] = ArenaPlayer("p1", rating=2000, tier="diamond")
        ar.end_season("s1")
        assert ar.players["p1"].rating < 2000  # bug3: 还是2000
        assert ar.players["p1"].tier == "bronze" or ar.players["p1"].rating == 1000

class TestDecay:
    def test_inactive_player_decays(self):
        ar = ArenaRank()
        ar.players["p1"] = ArenaPlayer("p1", rating=2000)
        ar.decay_threshold = 7
        ar.apply_decay("p1", 30)
        assert ar.players["p1"].rating < 2000  # bug4: 还是2000

class TestTeamRatingAverage:
    def test_team_rating_is_average(self):
        ar = ArenaRank()
        ar.players["p1"] = ArenaPlayer("p1", rating=2000)
        ar.players["p2"] = ArenaPlayer("p2", rating=1000)
        avg = ar.team_rating(["p1", "p2"])
        assert avg == 1500  # bug5: 只看p1返回2000

class TestPromotionBO5:
    def test_promotion_requires_3_wins(self):
        ar = ArenaRank()
        ar.players["p1"] = ArenaPlayer("p1", rating=1500, tier="bronze")
        ar.promotion_match("p1", True)
        assert ar.players["p1"].tier == "bronze"  # bug6: 赢一把就silver
        ar.promotion_match("p1", True)
        ar.promotion_match("p1", True)
        assert ar.players["p1"].tier == "silver"

class TestRewardAtSeasonEnd:
    def test_reward_based_on_end_tier(self):
        ar = ArenaRank()
        ar.players["p1"] = ArenaPlayer("p1", rating=1200, tier="silver", season_high=2000)
        reward = ar.get_season_reward_tier("p1")
        assert reward == "silver"  # bug7: 返回diamond（按历史最高）

class TestRatingSync:
    def test_display_and_hidden_synced(self):
        ar = ArenaRank()
        ar.players["p1"] = ArenaPlayer("p1", rating=1500, hidden_rating=1200)
        ar.sync_ratings("p1")
        assert ar.players["p1"].rating == ar.players["p1"].hidden_rating  # bug8: 不一致
