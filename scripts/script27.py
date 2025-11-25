# script27.py
def count_vowels(s):
    vowels = set("aeiouAEIOU")
    count = 0
    for ch in s:
        if ch in vowels:
            count += 1
    return count


def main():
    text = "AutoLogger project"
    v = count_vowels(text)
    print("Vowels:", v)


if __name__ == "__main__":
    main()
