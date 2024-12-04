def createRandomString(n1=3, maxLen1=23, n2=5, maxLen2=59) -> str:
    import random
    import string
    s1 = []
    s2 = []
    for i in range(n1):
        s1.append(''.join(random.choices(string.ascii_lowercase, k=random.randint(1, maxLen1))))
    for i in range(n2):
        s2.append(''.join(random.choices(string.ascii_lowercase, k=random.randint(1, maxLen2))))

    s = s1 + s2
    random.shuffle(s)

    return ' '.join(s)

def bulusmaZamani():
    random_string = createRandomString()
    words = random_string.split()

    min_uzunluk = min(len(word) for word in words) #saat için bu uzunluk
    max_uzunluk = max(len(word) for word in words) #dakika için bu uzunluk

    bulusma_saat = min_uzunluk
    bulusma_dakika = max_uzunluk

    return f'{bulusma_saat}:{bulusma_dakika}'

print(bulusmaZamani())
