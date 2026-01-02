import re
from typing import List


ACCOUNT_PATTERN = re.compile(
    r"^(?P<login>[^:\s]+):(?P<password>[^:\s]+):(?P<twofa>[A-Z0-9\s]+)$",
    re.IGNORECASE,
)


def parse_account_lines(raw_data: str) -> List[str]:
    """Нормализуем строки аккаунтов и убираем пробелы из кодов 2FA."""
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

        match = ACCOUNT_PATTERN.fullmatch(line)
        if not match:
            raise ValueError(f"Некорректный формат аккаунта: {line}")

        login = match.group("login")
        password = match.group("password")
        twofa = match.group("twofa").replace(" ", "")

        parsed.append(f"{login}:{password}:{twofa}")

    return parsed
