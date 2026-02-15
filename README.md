# Market Sales Simulation

This project simulates a simple market sales system using Python.
It focuses on object-oriented programming and basic data handling concepts.

## Features
- Reads product prices from a CSV file
- Creates sales receipts (Fis)
- Calculates total sales amounts
- Uses clean and modular OOP design

## Technologies
- Python
- CSV file handling
- Object-Oriented Programming

## Example
The system can simulate sales like:
- elma x2
- süt x1

And produces a receipt with total cost and timestamp.

## Learning Outcomes
- OOP design in Python
- Data structure usage (dict, list)
- Clean code and readability

**Note:** This project is for learning purposes and is open to further development.

--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

## Square Number Calculator

This Python program calculates the square of numbers entered by the user.  
The user is prompted to input several numbers, and the program displays the square of each one.

### Features
- Takes numerical input from the user  
- Calculates the square of each number  
- Displays results in a clear format  

### Technologies Used
- Python 3

### Purpose
This project was created to practice basic Python concepts such as user input, variables, functions, and arithmetic operations.

### Possible Improvements
- Using loops instead of repetitive code  
- Input validation to prevent invalid entries  
- Allowing the user to choose how many numbers to calculate  

**Note:** This is a beginner-level project developed for learning and practice purposes.

--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

## Solar Energy System Simulation (Python)

This project is a simple object-oriented Python simulation that models a residential solar energy system.

It calculates:
- Roof area based on house dimensions and latitude
- Optimal panel tilt angle
- Number of solar panels that can be installed
- Total system cost
- Total energy production considering panel efficiency

### Project Structure
- **House**: Represents the physical properties of a house (dimensions, latitude)
- **SolarPanel**: Stores panel specifications such as power, size, efficiency, and cost
- **SolarEnergySystem**: Performs all calculations and combines house and panel data

### Concepts Used
- Python (Object-Oriented Programming)
- Class & Object design
- Mathematical calculations with `math` module
- Real-world system modeling

### Possible Improvements
- Adding monthly or yearly energy production estimation
- Including weather and sunlight duration data
- Creating a graphical user interface (GUI)
- Exporting results to a CSV or JSON file

### Purpose
This project was developed to practice object-oriented design and apply mathematical logic to a real-life engineering problem.

--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

## Pool Tile Calculator (Python)

This project calculates the optimal square tile size and the total number of tiles required
to cover all surfaces of a rectangular swimming pool without cutting any tiles.

The solution uses mathematical logic based on the Greatest Common Divisor (GCD) to ensure
that the selected tile size perfectly fits the pool dimensions.

### Project Overview
- Determines the largest possible square tile size using GCD
- Calculates the total surface area of the pool (floor, ceiling, and side walls)
- Computes the required number of tiles based on surface area

### Concepts Used
- Python functions and modular design
- Mathematical problem solving
- Greatest Common Divisor (GCD)
- Clean and readable code structure
- Type hints for better code clarity

### Possible Improvements
- Supporting rectangular (non-square) tile sizes
- Adding unit selection (meters, centimeters)
- Creating a simple user interface
- Visualizing pool surfaces and tile placement

### Purpose
This project was developed to practice algorithmic thinking and apply mathematical concepts
to a real-world engineering problem.

--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

## Text Tools GUI (Tkinter)

A desktop GUI application built with **Python Tkinter** that performs common text-processing tasks such as:
- Displaying letters line by line
- Reversing text (full and word-by-word)
- Replacing characters
- Splitting and joining words
- Counting vowels
- Measuring typing speed (time + characters per second)

### Concepts Used
- Python Tkinter (GUI development)
- Functions and string manipulation
- Basic state management (timer)
- Clean and user-friendly UI structure

### Possible Improvements
- Add file import/export (TXT)
- Support for multiple languages and custom vowel sets
- Word/character statistics dashboard

--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

## 🎱 Bouncing Balls Animation (Tkinter)

A Python desktop application built with **Tkinter** that simulates bouncing balls inside a canvas.
Users can dynamically add balls, change their size and color, and control animation speed.

### 🔹 Features
- Add multiple balls with random velocity
- Size and color selection
- Speed control with upper/lower limits
- Keyboard shortcuts (start/stop, reset, speed up/down)
- Optional background image support (works even without Pillow)

### 🛠️ Concepts Used
- Tkinter GUI development
- OOP (Ball & App classes)
- Basic animation loop using `after()`
- Event handling (keyboard shortcuts)
- Clean UI layout with `ttk`

### 🚀 Possible Improvements
- Ball-to-ball collision detection
- Saving/loading configurations
- FPS indicator and performance tuning
- Sound effects or themes
