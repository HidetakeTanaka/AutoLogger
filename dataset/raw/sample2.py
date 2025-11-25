def process_numbers(nums):
    total = 0
    for n in nums:
        total += n
    if total > 50:
        print("The total is larger than 50!!")
    return total


def safe_division(a,b):
    try:
        result = a / b
    except ZeroDivisionError:
        result = None 
        print("Cannot devide by zero...")
    return result


def outer_function(x):
    def inner_function(y):
        return y * 2
    return inner_function(x)
