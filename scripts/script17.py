def factorial(n):
    if n < 0:
        raise ValueError("Negative not allowed")
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result


def main():
    value = 5
    print("Factorial:", factorial(value))


if __name__ == "__main__":
    main()
