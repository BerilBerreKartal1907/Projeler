from __future__ import annotations

from dataclasses import dataclass
from typing import List
import random


@dataclass
class Student:
    name: str
    student_id: int
    grades: List[int]

    @property
    def average(self) -> float:
        return sum(self.grades) / len(self.grades) if self.grades else 0.0

    def __str__(self) -> str:
        return (
            f"Name: {self.name:<10} "
            f"Id: {self.student_id:<4d} "
            f"Average: {self.average:<8.2f} "
            f"Grades: {self.grades}"
        )


def generate_random_grades(min_grade: int = 0, max_grade: int = 100) -> List[int]:
    count = random.randint(2, 4)
    return [random.randint(min_grade, max_grade) for _ in range(count)]


def create_random_students(n: int = 50) -> List[Student]:
    names = [
        "Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Heidi",
        "Ivan", "Jack", "Kate", "Liam", "Mia", "Nina", "Oliver", "Pam", "Quinn",
        "Rita", "Sam", "Tina", "Uma", "Vince", "Wendy", "Xander", "Yara", "Zoe"
    ]
    return [
        Student(
            name=random.choice(names),
            student_id=i,
            grades=generate_random_grades()
        )
        for i in range(n)
    ]


def find_top_student(students: List[Student]) -> Student:
    if not students:
        raise ValueError("Student list is empty.")
    return max(students, key=lambda s: s.average)


def main() -> None:
    students = create_random_students(50)

    for s in students:
        print(s)

    top_student = find_top_student(students)

    print("\n" + "#" * 72)
    print("Top student by average grade:")
    print(top_student)
    print("#" * 72 + "\n")


if __name__ == "__main__":
    main()
