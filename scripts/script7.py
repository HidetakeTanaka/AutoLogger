def safe_div(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        return None


def main():
    result = safe_div(10, 0)
    print("Result:", result)


if __name__ == "__main__":
    main()
