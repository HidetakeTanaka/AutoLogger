def find_word(text, word):
    if not text:
        return -1
    parts = text.split()
    for i, w in enumerate(parts):
        if w.lower() == word.lower():
            return i
    return -1


def main():
    sentence = "Python makes logging easier"
    index = find_word(sentence, "logging")
    print("Index:", index)


if __name__ == "__main__":
    main()
