def read_numbers(path):
    numbers = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            numbers.append(float(line))
    return numbers


def main():
    try:
        nums = read_numbers("numbers.txt")
        print("Count:", len(nums))
    except FileNotFoundError:
        print("numbers.txt missing")


if __name__ == "__main__":
    main()
