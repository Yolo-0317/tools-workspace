"""Free-chat opening rotation."""

import teaching.free_chat_kickoffs as kickoffs
from teaching.free_chat_kickoffs import FREE_CHAT_KICKOFFS, pick_free_kickoff


def test_free_kickoff_round_robin():
    kickoffs._free_kickoff_cursor = 0
    n = len(FREE_CHAT_KICKOFFS)
    assert n >= 10

    first_cycle = [pick_free_kickoff() for _ in range(n)]
    assert len(set(first_cycle)) == n

    second_cycle = [pick_free_kickoff() for _ in range(n)]
    assert second_cycle == first_cycle
