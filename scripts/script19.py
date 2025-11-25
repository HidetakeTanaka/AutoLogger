def safe_get(d, key, default=None):
    try:
        return d[key]
    except KeyError:
        return default


def main():
    config = {"host": "localhost", "port": 8080}
    host = safe_get(config, "host", "unknown")
    timeout = safe_get(config, "timeout", 30)
    print("Host:", host)
    print("Timeout:", timeout)


if __name__ == "__main__":
    main()
