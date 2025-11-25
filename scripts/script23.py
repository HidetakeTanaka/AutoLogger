def normalize(values):
    if not values:
        return []
    total = sum(values)
    if total == 0:
        return values
    return [v / total for v in values]


def main():
    scores = [3, 4, 5]
    norm = normalize(scores)
    print("Normalized:", norm)


if __name__ == "__main__":
    main()
