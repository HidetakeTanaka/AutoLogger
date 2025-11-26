def is_even(n):
    return n % 2 == 0


def main():
    num = 13
    if is_even(num):
        print("Even")
    else:
        print("Odd")


if __name__ == "__main__":
    main()
