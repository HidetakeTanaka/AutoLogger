def is_palindrome(s):
    cleaned = "".join(ch.lower() for ch in s if ch.isalnum())
    return cleaned == cleaned[::-1]


def main():
    word = "Racecar"
    if is_palindrome(word):
        print("Palindrome")
    else:
        print("Not palindrome")


if __name__ == "__main__":
    main()
