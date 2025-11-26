import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 - needed for 3D plots


def surface_function(x, y):
    """Compute f(x, y) = 0.5(x - 3)^2 + 0.3(y + 1)^2."""
    return 0.5 * (x - 3) ** 2 + 0.3 * (y + 1) ** 2


def generate_grid(start=-10, end=10, steps=100):
    """Generate a meshgrid of x and y values."""
    if steps <= 0:
        raise ValueError("Steps must be positive")
    x = np.linspace(start, end, steps)
    y = np.linspace(start, end, steps)
    return np.meshgrid(x, y)


def plot_surface(X, Y, Z):
    """Create a 3D surface plot."""
    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(X, Y, Z, cmap="viridis")
    ax.set_title("Surface Plot of f(x, y) = 0.5(x-3)^2 + 0.3(y+1)^2")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("f(x, y)")
    plt.show()


def main():
    try:
        X, Y = generate_grid(-10, 10, 100)
        Z = surface_function(X, Y)
        plot_surface(X, Y, Z)
    except Exception as e:
        print("An error occurred:", e)


if __name__ == "__main__":
    main()
