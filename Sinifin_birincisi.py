class Student:
    def __init__(self, name: str, id: int, grades: list):
        self.name = name
        self.grades = grades
        self.id = id

    def __str__(self):
        return f"Name: {self.name:10} Id: {self.id:<4d} Average: {self.averageGrade():<8.2f} Grades: {self.grades} "

    def averageGrade(self):
        return sum(self.grades) / len(self.grades)
def generateRandomGrades(minGrade=0, maxGrade=100):
    import random
    n = random.randint(2, 4)
    return [random.randint(minGrade, maxGrade) for i in range(n)]
def createRandomStudents(listOfStudents: list, n=50):
    import random
    names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Heidi",
             "Ivan", "Jack", "Kate", "Liam", "Mia", "Nina", "Oliver", "Pam", "Quinn",
             "Rita", "Sam", "Tina", "Uma", "Vince", "Wendy", "Xander", "Yara", "Zoe"]
    for i in range(n):
        name = random.choice(names)
        grades = generateRandomGrades()
        listOfStudents.append(Student(name, i, grades))
def findStudentWithTheHighestAverageGrade(listOfStudents: list) -> Student:
    enIyiOgrenci = listOfStudents[0]
    enYuksek_ortalama = enIyiOgrenci.averageGrade()

    for student in listOfStudents[1:]:
        mevcut_ortalama = student.averageGrade()

        if mevcut_ortalama > enYuksek_ortalama:
            enIyiOgrenci = student
            enYuksek_ortalama = mevcut_ortalama

    return enIyiOgrenci
def main():
    listOfStudents = []
    createRandomStudents(listOfStudents, 50)
    for s in listOfStudents:
        print(s)
    student = findStudentWithTheHighestAverageGrade(listOfStudents)

    print("\n########################################################################")
    print(student)
    print("########################################################################\n")

if __name__ == "__main__":
    main()
