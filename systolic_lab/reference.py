"""Independent mathematical oracle; no simulator scheduling or tile helpers."""


def matmul(a: list[list[int]], b: list[list[int]]) -> list[list[int]]:
    """Compute dot products directly using Python's exact integer arithmetic."""
    columns = list(zip(*b))
    return [[sum(x * y for x, y in zip(row, column, strict=True))
             for column in columns] for row in a]
