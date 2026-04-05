import os


def _parse_env_value(raw_value):
    value = raw_value.strip()
    if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
        return value[1:-1]
    return value


def load_dotenv_file(path=None):
    path = path or os.path.join(os.getcwd(), ".env")
    if not os.path.exists(path):
        return False

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, raw_value = stripped.split("=", 1)
            key = key.strip()
            value = _parse_env_value(raw_value)
            if key and key not in os.environ:
                os.environ[key] = value

    return True
