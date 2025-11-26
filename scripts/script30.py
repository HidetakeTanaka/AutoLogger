def remove_duplicates(items):
    seen = set()
    result = []
    for x in items:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result


def main():
    data = [1, 2, 2, 3, 1, 4]
    unique = remove_duplicates(data)
    print("Unique:", unique)


if __name__ == "__main__":
    main()
