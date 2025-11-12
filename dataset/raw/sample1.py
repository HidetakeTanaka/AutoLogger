def foo(x, y):
    result = x + y
    if result > 0:
        return result
    else:
        raise ValueError("This is negative!")
    