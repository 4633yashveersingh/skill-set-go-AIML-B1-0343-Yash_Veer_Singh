number = int(input("Enter a number: "))

print("\nMultiplication Table")

for i in range(1, 11):
    print(number, "x", i, "=", number * i)


print("\nNumbers from 1 to", number)

for i in range(1, number + 1):
    print(i, end=" ")