# script29.py
def median(values):
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return sorted_vals[mid]
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2


def main():
    nums = [7, 1, 5, 3]
    m = median(nums)
    print("Median:", m)


if __name__ == "__main__":
    main()
