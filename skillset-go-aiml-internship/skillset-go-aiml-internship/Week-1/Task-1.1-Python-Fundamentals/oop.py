class Student:

    def __init__(self, name, course, marks):
        self.name = name
        self.course = course
        self.marks = marks

    def calculate_average(self):
        return sum(self.marks) / len(self.marks)

    def display_details(self):
        print("Name:", self.name)
        print("Course:", self.course)
        print("Marks:", self.marks)
        print("Average:", self.calculate_average())


student1 = Student(
    "Yash",
    "CSAIML",
    [85, 78, 92, 88]
)

student1.display_details()