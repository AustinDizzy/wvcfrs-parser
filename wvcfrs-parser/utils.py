import re

def extract_addr(addr : str) -> str | None:
    return addr.split(",")[0].strip()

def extract_city(addr : str) -> str | None:
    match = re.search(r'\, (.+?)\, [A-Z]{2} \d{5}\s*$', addr.strip(), re.IGNORECASE)
    if match:
        return match.group(1).strip().title()

def extract_state(addr: str) -> str | None:
    match = re.compile(r'\, ([A-Z]{2}) \d{5}\s*$', re.IGNORECASE).search(addr.strip())
    if match:
        return match.group(1).strip().upper()

def extract_zip(addr : str) -> str | None:
    match = re.search(r'(\d{5})\s*$', addr.strip())
    if match:
        return match.group(1).strip()