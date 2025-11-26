import numpy as np
import matplotlib.pyplot as plt


def sine_function(x):
    """Compute f(x) = sin(x) for an array of values."""
    return np.sin(x)


def generate_values(start, end, steps=100):
    """Generate evenly spaced x values."""
    if steps <= 0:
        raise ValueError("Steps must be positive")
    return np.linspace(start, end, steps)


def plot_sine(x, y):
    """Plot the sine function with proper labels and styling."""
    plt.plot(x, y, label="y = sin(x)")
    plt.title("Sine Function: f(x) = sin(x)")
    plt.xlabel("x")
    plt.ylabel("f(x)")
    plt.grid(True)
    plt.legend()
    plt.show()


def main():
    try:
        x = generate_values(-10, 10, 100)
        y = sine_function(x)
        plot_sine(x, y)
    except Exception as e:
        print("An error occurred:", e)


if __name__ == "__main__":
    main()
