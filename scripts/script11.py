import numpy as np
import matplotlib.pyplot as plt


def quadratic_function(x):
    """Return the value of a quadratic function y = x^2."""
    return x ** 2


def plot_quadratic(x, y):
    """Plot the quadratic curve."""
    plt.plot(x, y, label="y = x^2")
    plt.title("Quadratic Function Plot")
    plt.xlabel("x")
    plt.ylabel("f(x)")
    plt.grid(True)
    plt.legend()
    plt.show()


def main():
    x = np.linspace(-10, 10, 100)
    y = quadratic_function(x)
    plot_quadratic(x, y)


if __name__ == "__main__":
    main()
