def get_price(items, key):
    if key not in items:
        return None
    return items[key]


def main():
    prices = {"pen": 2, "book": 5}
    print(get_price(prices, "book"))


if __name__ == "__main__":
    main()
