import numpy as np
import matplotlib.pyplot as plt


def reciprocal_function(x):
    """Compute f(x) = 1/x safely for an array of values."""
    # Avoid division by zero by replacing 0 with a very small number
    x_safe = np.where(x == 0, 1e-8, x)
    return 1 / x_safe


def generate_values(start, end, steps=100):
    """Generate evenly spaced x values."""
    if steps <= 0:
        raise ValueError("Steps must be positive")
    return np.linspace(start, end, steps)


def plot_function(x, y):
    """Plot the reciprocal function with labels and grid."""
    plt.plot(x, y, label="y = 1/x")
    plt.title("Reciprocal Function: f(x) = 1/x")
    plt.xlabel("x")
    plt.ylabel("f(x)")
    plt.grid(True)
    plt.legend()
    plt.show()


def main():
    try:
        x = generate_values(-10, 10, 100)
        y = reciprocal_function(x)
        plot_function(x, y)
    except Exception as e:
        print("An error occurred:", e)


if __name__ == "__main__":
    main()
