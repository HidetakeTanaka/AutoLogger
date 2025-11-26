def avg(nums):
    if not nums:
        return 0
    return sum(nums) / len(nums)

def main():
    values = [3, 7, 10]
    print("Average:", avg(values))

if __name__ == "__main__":
    main()
