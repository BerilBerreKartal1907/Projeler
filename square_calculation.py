def calculate_square(number: float) -> float:
    """
    Returns the square of a given number.
    """
    return number ** 2


def main():
    print("Square Calculation Program")
    print("---------------------------")

    try:
        count = int(input("How many numbers do you want to calculate? "))

        for i in range(count):
            number = float(input(f"{i + 1}. number: "))
            square = calculate_square(number)
            print(f"{number}^2 = {square}")

    except ValueError:
        print("Please enter valid numeric values.")


if __name__ == "__main__":
    main()
