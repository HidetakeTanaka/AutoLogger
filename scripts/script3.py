def count_lines(path):
    with open(path) as f:
        return sum(1 for _ in f)


def main():
    try:
        print("Lines:", count_lines("data.txt"))
    except FileNotFoundError:
        print("File missing.")


if __name__ == "__main__":
    main()
