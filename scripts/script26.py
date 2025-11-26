def merge_dicts(a, b):
    merged = a.copy()
    merged.update(b)
    return merged


def main():
    d1 = {"a": 1, "b": 2}
    d2 = {"b": 3, "c": 4}
    result = merge_dicts(d1, d2)
    print("Merged:", result)


if __name__ == "__main__":
    main()
