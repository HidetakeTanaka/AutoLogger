import numpy as np
import matplotlib.pyplot as plt


def cubic_function(x):
    """Compute f(x) = x^3 for an array of values."""
    return x ** 3


def generate_values(start, end, steps=100):
    """Generate evenly spaced x values."""
    if steps <= 0:
        raise ValueError("Number of steps must be positive")
    return np.linspace(start, end, steps)


def plot_function(x, y):
    """Plot a cubic function."""
    plt.plot(x, y, label="y = x^3")
    plt.title("Cubic Function: f(x) = x^3")
    plt.xlabel("x")
    plt.ylabel("f(x)")
    plt.grid(True)
    plt.legend()
    plt.show()


def main():
    try:
        x = generate_values(-10, 10, 100)
        y = cubic_function(x)
        plot_function(x, y)
    except Exception as e:
        # Handles any unexpected runtime errors
        print("An error occurred:", e)


if __name__ == "__main__":
    main()
