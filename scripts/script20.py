# script20.py
def average_length(words):
    if not words:
        return 0.0
    total = sum(len(w) for w in words)
    return total / len(words)


def main():
    items = ["apple", "banana", "kiwi"]
    avg = average_length(items)
    print("Average length:", avg)


if __name__ == "__main__":
    main()
