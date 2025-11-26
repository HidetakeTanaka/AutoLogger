def clamp(value, low, high):
    if low > high:
        raise ValueError("low cannot be greater than high")
    if value < low:
        return low
    if value > high:
        return high
    return value


def main():
    v = 15
    clamped = clamp(v, 0, 10)
    print("Clamped:", clamped)


if __name__ == "__main__":
    main()
