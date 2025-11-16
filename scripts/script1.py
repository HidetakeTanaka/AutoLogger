def to_celsius(f):
    if f < -459.67:
        raise ValueError("Below absolute zero")
    return (f - 32) * 5/9

def main():
    temp_f = 96
    temp_c = to_celsius(temp_f)
    print("Celsius:", temp_c)

if __name__ == "__main__":
    main()
