def filter_positive(nums):
    result = []
    for n in nums:
        if n > 0:
            result.append(n)
    return result


def main():
    values = [-3, 0, 4, 7]
    positives = filter_positive(values)
    print("Positive numbers:", positives)


if __name__ == "__main__":
    main()
