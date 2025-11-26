import math


def circle_area(radius):
    if radius < 0:
        raise ValueError("radius must be non-negative")
    return math.pi * radius * radius


def main():
    r = 3
    area = circle_area(r)
    print("Area:", area)


if __name__ == "__main__":
    main()
