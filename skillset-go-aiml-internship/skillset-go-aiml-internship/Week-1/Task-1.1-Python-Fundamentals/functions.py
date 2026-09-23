def calculate_average(marks):
    return sum(marks) / len(marks)


def find_grade(average):
    if average >= 90:
        return "A+"
    elif average >= 80:
        return "A"
    elif average >= 70:
        return "B"
    elif average >= 60:
        return "C"
    elif average >= 40:
        return "D"
    else:
        return "F"


marks = [85, 78, 92, 88]

average = calculate_average(marks)
grade = find_grade(average)

print("Marks:", marks)
print("Average:", average)
print("Grade:", grade)