def find_max(nums):
    if not nums:
        return None
    return max(nums)


def main():
    arr = [2, 9, 4]
    print(find_max(arr))


if __name__ == "__main__":
    main()
