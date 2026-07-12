from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


class VoteKind(str, Enum):
    DAY_ELIMINATION = "day_elimination"
    WEREWOLF_KILL = "werewolf_kill"
    SEER_CHECK = "seer_check"
    WITCH_SAVE = "witch_save"
    WITCH_POISON = "witch_poison"


class TiePolicy(str, Enum):
    NO_ELIMINATION = "no_elimination"
    SEAT_ORDER = "seat_order"


class Visibility(str, Enum):
    PUBLIC = "public"
    WEREWOLF = "werewolf"
    PRIVATE = "private"


@dataclass(frozen=True)
class Vote:
    voter: int
    target: Optional[int]
    kind: VoteKind
    weight: int = 1
    reason: str = ""


@dataclass(frozen=True)
class VoteResolution:
    kind: VoteKind
    target: Optional[int]
    counts: Dict[int, int]
    tied_targets: List[int]
    policy: TiePolicy
    resolved: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "target": self.target,
            "counts": self.counts,
            "tied_targets": self.tied_targets,
            "policy": self.policy.value,
            "resolved": self.resolved,
            "reason": self.reason,
        }


@dataclass
class VoteSession:
    kind: VoteKind
    eligible_voters: List[int]
    eligible_targets: List[int]
    tie_policy: TiePolicy
    allow_abstain: bool = True
    votes: Dict[int, Vote] = field(default_factory=dict)

    def cast(self, voter: int, target: Optional[int], reason: str = "") -> bool:
        if voter not in self.eligible_voters:
            return False
        if target is None:
            if not self.allow_abstain:
                return False
            self.votes[voter] = Vote(voter=voter, target=None, kind=self.kind, reason=reason)
            return True
        if target not in self.eligible_targets:
            return False
        self.votes[voter] = Vote(voter=voter, target=target, kind=self.kind, reason=reason)
        return True

    def resolve(self) -> VoteResolution:
        counts: Dict[int, int] = {}
        for vote in self.votes.values():
            if vote.target is not None:
                counts[vote.target] = counts.get(vote.target, 0) + vote.weight

        if not counts:
            return VoteResolution(
                kind=self.kind,
                target=None,
                counts={},
                tied_targets=[],
                policy=self.tie_policy,
                resolved=False,
                reason="no_valid_votes",
            )

        max_votes = max(counts.values())
        tied_targets = sorted(target for target, count in counts.items() if count == max_votes)
        if len(tied_targets) == 1:
            return VoteResolution(
                kind=self.kind,
                target=tied_targets[0],
                counts=counts,
                tied_targets=[],
                policy=self.tie_policy,
                resolved=True,
                reason="majority_or_plurality",
            )

        if self.tie_policy == TiePolicy.NO_ELIMINATION:
            return VoteResolution(
                kind=self.kind,
                target=None,
                counts=counts,
                tied_targets=tied_targets,
                policy=self.tie_policy,
                resolved=False,
                reason="tie_no_elimination",
            )

        if self.tie_policy == TiePolicy.SEAT_ORDER:
            for voter in sorted(self.eligible_voters):
                vote = self.votes.get(voter)
                if vote and vote.target in tied_targets:
                    return VoteResolution(
                        kind=self.kind,
                        target=vote.target,
                        counts=counts,
                        tied_targets=tied_targets,
                        policy=self.tie_policy,
                        resolved=True,
                        reason=f"tie_resolved_by_lowest_seat_voter_{voter}",
                    )

        return VoteResolution(
            kind=self.kind,
            target=None,
            counts=counts,
            tied_targets=tied_targets,
            policy=self.tie_policy,
            resolved=False,
            reason="tie_unresolved",
        )


@dataclass(frozen=True)
class MemoryEvent:
    phase: str
    source: str
    content: str
    visibility: Visibility
    recipients: Optional[List[int]] = None


class MemoryInjector:
    def __init__(self, agents: Iterable[Any], game_state: Dict[str, Any]):
        self.agents = list(agents)
        self.game_state = game_state

    def inject(self, event: MemoryEvent, alive_only: bool = True) -> List[int]:
        recipients = self._resolve_recipients(event, alive_only)
        if not recipients:
            return []

        memory_text = self._format_memory(event)
        memory_update_info = {
            "memory_updates": {
                "short_memory_add": [memory_text],
                "prediction_adjust": [],
            }
        }
        for agent in self.agents:
            if agent.agent_id in recipients:
                agent.update_memory(memory_update_info, event.phase)
        return recipients

    def _resolve_recipients(self, event: MemoryEvent, alive_only: bool) -> List[int]:
        alive = set(self.game_state.get("alive_agents", []))
        if event.visibility == Visibility.PUBLIC:
            candidates = [agent.agent_id for agent in self.agents]
        elif event.visibility == Visibility.WEREWOLF:
            candidates = [agent.agent_id for agent in self.agents if agent.role == "werewolf"]
        else:
            candidates = list(event.recipients or [])

        if alive_only:
            candidates = [agent_id for agent_id in candidates if agent_id in alive]
        return sorted(set(candidates))

    def _format_memory(self, event: MemoryEvent) -> str:
        alive = self.game_state.get("alive_agents", [])
        eliminated = self.game_state.get("eliminated_agents", [])
        day = self.game_state.get("day")
        phase = self.game_state.get("phase")
        return (
            f"场上信息状态：第{day}天，当前阶段{phase}，"
            f"存活玩家{alive}，已淘汰玩家{eliminated}。\n"
            f"{event.source}：{event.content}"
        )
