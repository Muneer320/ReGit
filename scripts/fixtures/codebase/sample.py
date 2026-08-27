"""Small source fixture for ReGit codebase ingestion."""


def deterministic_score(values: list[int]) -> float:
    """Return a stable normalized score for a sequence."""
    if not values:
        return 0.0
    return sum(values) / len(values)


if __name__ == "__main__":
    print(deterministic_score([1, 2, 3]))
