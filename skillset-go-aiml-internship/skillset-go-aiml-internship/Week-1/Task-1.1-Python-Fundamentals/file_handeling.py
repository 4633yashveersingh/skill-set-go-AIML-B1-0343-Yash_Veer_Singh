# Writing data to a file

with open("student.txt", "w") as file:
    file.write("Name: Yash\n")
    file.write("Course: CSAIML\n")
    file.write("Subject: Python Fundamentals\n")

print("Data written successfully.")


# Reading data from the file

with open("student.txt", "r") as file:
    data = file.read()

print("\nFile Content:")
print(data)