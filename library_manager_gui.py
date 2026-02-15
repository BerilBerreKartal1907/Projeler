import tkinter as tk
from tkinter import messagebox
from dataclasses import dataclass
from typing import List


@dataclass
class Book:
    title: str
    author: str
    year: int

    def __str__(self) -> str:
        return f"Title: {self.title} | Author: {self.author} | Year: {self.year}"


class Library:
    def __init__(self):
        self.books: List[Book] = []

    def add_book(self, book: Book) -> None:
        self.books.append(book)

    def delete_book_by_title(self, title: str) -> bool:
        title = title.strip().lower()
        for b in self.books:
            if b.title.strip().lower() == title:
                self.books.remove(b)
                return True
        return False

    def search_by_title(self, title: str) -> List[Book]:
        title = title.strip().lower()
        return [b for b in self.books if b.title.strip().lower() == title]

    def search_by_author(self, author: str) -> List[Book]:
        author = author.strip().lower()
        return [b for b in self.books if b.author.strip().lower() == author]

    def list_all(self) -> List[Book]:
        return self.books


class LibraryApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Library Manager (Tkinter)")
        self.library = Library()

        tk.Label(root, text="Library Manager", font=("Arial", 16)).pack(pady=10)

        tk.Button(root, text="Add Book", command=self.open_add_book, width=24).pack(pady=5)
        tk.Button(root, text="Delete Book", command=self.open_delete_book, width=24).pack(pady=5)
        tk.Button(root, text="Search by Title", command=self.open_search_title, width=24).pack(pady=5)
        tk.Button(root, text="Search by Author", command=self.open_search_author, width=24).pack(pady=5)
        tk.Button(root, text="List All Books", command=self.open_list_all, width=24).pack(pady=5)
        tk.Button(root, text="Exit", command=root.quit, width=24).pack(pady=5)

    # ---------- Helpers ----------
    def _new_window(self, title: str) -> tk.Toplevel:
        win = tk.Toplevel(self.root)
        win.title(title)
        win.resizable(False, False)
        return win

    def _require_nonempty(self, value: str, field_name: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"{field_name} cannot be empty.")
        return value

    # ---------- Add ----------
    def open_add_book(self):
        win = self._new_window("Add Book")

        tk.Label(win, text="Title:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        ent_title = tk.Entry(win, width=30)
        ent_title.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(win, text="Author:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        ent_author = tk.Entry(win, width=30)
        ent_author.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(win, text="Year:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        ent_year = tk.Entry(win, width=30)
        ent_year.grid(row=2, column=1, padx=10, pady=5)

        def add():
            try:
                title = self._require_nonempty(ent_title.get(), "Title")
                author = self._require_nonempty(ent_author.get(), "Author")

                # allow letters + spaces + dots for author names
                if not all(ch.isalpha() or ch in " .'-" for ch in author):
                    messagebox.showwarning("Invalid", "Author name contains invalid characters.")
                    return

                year_text = self._require_nonempty(ent_year.get(), "Year")
                if not year_text.isdigit():
                    messagebox.showwarning("Invalid", "Year must be numeric.")
                    return
                year = int(year_text)

                self.library.add_book(Book(title=title, author=author, year=year))
                messagebox.showinfo("Success", f"'{title}' added successfully.")
                win.destroy()
            except ValueError as e:
                messagebox.showwarning("Error", str(e))

        tk.Button(win, text="Add", command=add, width=18).grid(row=3, column=0, columnspan=2, pady=10)

    # ---------- Delete ----------
    def open_delete_book(self):
        win = self._new_window("Delete Book")

        tk.Label(win, text="Title:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        ent_title = tk.Entry(win, width=30)
        ent_title.grid(row=0, column=1, padx=10, pady=5)

        def delete():
            title = ent_title.get().strip()
            if not title:
                messagebox.showwarning("Error", "Please enter a book title.")
                return

            if self.library.delete_book_by_title(title):
                messagebox.showinfo("Success", f"'{title}' deleted.")
                win.destroy()
            else:
                messagebox.showwarning("Not found", f"'{title}' not found.")

        tk.Button(win, text="Delete", command=delete, width=18).grid(row=1, column=0, columnspan=2, pady=10)

    # ---------- Search ----------
    def open_search_title(self):
        win = self._new_window("Search by Title")

        tk.Label(win, text="Title:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        ent_title = tk.Entry(win, width=30)
        ent_title.grid(row=0, column=1, padx=10, pady=5)

        def search():
            title = ent_title.get().strip()
            if not title:
                messagebox.showwarning("Error", "Please enter a title.")
                return
            results = self.library.search_by_title(title)
            self._show_results("Results", results)

        tk.Button(win, text="Search", command=search, width=18).grid(row=1, column=0, columnspan=2, pady=10)

    def open_search_author(self):
        win = self._new_window("Search by Author")

        tk.Label(win, text="Author:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        ent_author = tk.Entry(win, width=30)
        ent_author.grid(row=0, column=1, padx=10, pady=5)

        def search():
            author = ent_author.get().strip()
            if not author:
                messagebox.showwarning("Error", "Please enter an author.")
                return
            results = self.library.search_by_author(author)
            self._show_results("Results", results)

        tk.Button(win, text="Search", command=search, width=18).grid(row=1, column=0, columnspan=2, pady=10)

    # ---------- List / Results ----------
    def _show_results(self, title: str, books: List[Book]):
        win = self._new_window(title)

        if not books:
            tk.Label(win, text="No results found.").pack(padx=10, pady=10)
            return

        listbox = tk.Listbox(win, width=70, height=10)
        listbox.pack(padx=10, pady=10)
        for b in books:
            listbox.insert(tk.END, str(b))

    def open_list_all(self):
        books = self.library.list_all()
        self._show_results("All Books", books)


def main():
    root = tk.Tk()
    LibraryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
