def chunk_list(values, size):
    if size <= 0:
        raise ValueError("size must be positive")
    chunks = []
    for i in range(0, len(values), size):
        chunks.append(values[i : i + size])
    return chunks


def main():
    data = [1, 2, 3, 4, 5, 6, 7]
    chunks = chunk_list(data, 3)
    print("Chunks:", chunks)


if __name__ == "__main__":
    main()
