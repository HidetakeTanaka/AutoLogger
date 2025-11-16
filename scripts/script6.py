def reverse(s):
    if not s:
        return s
    return s[::-1]


def main():
    print(reverse("hello"))


if __name__ == "__main__":
    main()
