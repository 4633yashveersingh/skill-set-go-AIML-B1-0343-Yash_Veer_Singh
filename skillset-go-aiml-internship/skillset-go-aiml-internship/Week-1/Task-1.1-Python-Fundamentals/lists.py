marks = [85, 78, 92, 67, 88]

print("Original marks:", marks)

marks.append(95)

print("After adding marks:", marks)
print("Highest marks:", max(marks))
print("Lowest marks:", min(marks))
print("Average:", sum(marks) / len(marks))

marks.sort()

print("Sorted marks:", marks)