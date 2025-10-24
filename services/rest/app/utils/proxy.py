import re
from typing import List


PROXY_PATTERN = re.compile(
    r"^(?:(?P<scheme>[a-zA-Z][\w+\-.]*):\/\/)?"
    r"(?P<login>[^:@\s]+):(?P<password>[^@\s]+)"
    r"@(?P<host>[^:\s]+):(?P<port>\d+)$"
)


def parse_proxy_lines(raw_data: str) -> List[str]:
    """Normalize and validate raw proxy lines."""
    if raw_data is None:
        return []

    normalized = raw_data.replace("\r\n", "\n").split("\n")
    parsed: list[str] = []

    for raw_line in normalized:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('"') and line.endswith('"') and len(line) > 1:
            line = line[1:-1]

        if not PROXY_PATTERN.fullmatch(line):
            raise ValueError(f"Некорректный формат прокси: {line}")

        parsed.append(line)

    return parsed
