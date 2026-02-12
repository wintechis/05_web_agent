"""Domain value objects for benchmark tasks and evaluation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Path:
    """Immutable list of URIs representing a path through a knowledge graph."""

    uris: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.uris, tuple):
            object.__setattr__(self, "uris", tuple(self.uris))

    @property
    def length(self) -> int:
        """Number of nodes (URIs) in the path."""
        return len(self.uris)

    def __len__(self) -> int:
        return self.length

    def __iter__(self):
        return iter(self.uris)


@dataclass
class TaskEntry:
    """Single task with gold and predicted paths for evaluation."""

    task_id: str
    question_text: str
    gold_path: Path
    predicted_path: Path

    @property
    def start_uri(self) -> str | None:
        """First URI in gold path."""
        return self.gold_path.uris[0] if self.gold_path.uris else None

    @property
    def target_uri(self) -> str | None:
        """Last URI in gold path."""
        return self.gold_path.uris[-1] if self.gold_path.uris else None


@dataclass
class TaskResult:
    """Result of evaluating a single task."""

    task_id: str
    predicted_length: int
    valid_edges: bool
    success: bool
    start_uri: str | None
    target_uri: str | None
    prefix_ratio: float
    prefix_valid_edges: list[dict[str, str]]


@dataclass
class EvaluationMetrics:
    """Aggregate metrics from benchmark evaluation."""

    csr: float  # Claimed Success Rate
    tsr: float  # True Success Rate
    po: float   # Path Optimality
    ppm: float  # Path Prefix Match
