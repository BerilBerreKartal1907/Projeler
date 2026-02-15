import random
import string
from typing import List


def create_random_string(
    n1: int = 3,
    max_len1: int = 23,
    n2: int = 5,
    max_len2: int = 59
) -> str:
    """
    Creates a shuffled string made of random lowercase words.
    """

    words: List[str] = []

    for _ in range(n1):
        words.append(
            ''.join(random.choices(string.ascii_lowercase, k=random.randint(1, max_len1)))
        )

    for _ in range(n2):
        words.append(
            ''.join(random.choices(string.ascii_lowercase, k=random.randint(1, max_len2)))
        )

    random.shuffle(words)
    return ' '.join(words)


def generate_meeting_time() -> str:
    """
    Generates a pseudo meeting time based on word lengths.
    Shortest word -> hour
    Longest word -> minute
    """

    random_string = create_random_string()
    words = random_string.split()

    hour = min(len(w) for w in words)
    minute = max(len(w) for w in words)

    return f"{hour:02d}:{minute:02d}"


if __name__ == "__main__":
    print(generate_meeting_time())
