import sqlite3

connection = sqlite3.connect("students.db")

cursor = connection.cursor()


table_info = """
CREATE TABLE IF NOT EXISTS student(
name TEXT,
city TEXT,
score INT,
remarks TEXT,
gender TEXT
);
"""

cursor.execute(table_info)
cursor.execute("DELETE FROM student")

# Students without major column
cursor.execute("INSERT INTO student VALUES ('Maryam',    'Karachi',   20,  'A', 'Female')")
cursor.execute("INSERT INTO student VALUES ('Ali',      'Multan',    30,  'B', 'Male')")
cursor.execute("INSERT INTO student VALUES ('Hamza',    'Lahore',    40,  'C', 'Male')")
cursor.execute("INSERT INTO student VALUES ('Qasim',     'Karachi',    0,  'B', 'Male')")
cursor.execute("INSERT INTO student VALUES ('Khan',     'Lahore',   100,  'A', 'Male')")
cursor.execute("INSERT INTO student VALUES ('Qasim',    'Karachi',   90,  'A', 'Male')")
cursor.execute("INSERT INTO student VALUES ('Ayan',  'Multan',     2,  'B', 'Male')")
cursor.execute("INSERT INTO student VALUES ('Muhammad', 'Lahore',     4,  'A', 'Male')")
cursor.execute("INSERT INTO student VALUES ('Alina',    'Karachi',   25,  'C', 'Female')")
cursor.execute("INSERT INTO student VALUES ('Ayesha',   'Karachi',   20,  'A', 'Female')")
cursor.execute("INSERT INTO student VALUES ('Saleha',    'Karachi',   88,  'B', 'Female')")
cursor.execute("INSERT INTO student VALUES ('Noor',     'Multan',    55,  'A', 'Female')")
cursor.execute("INSERT INTO student VALUES ('Shazia',   'Lahore',    40,  'C', 'Female')")
cursor.execute("INSERT INTO student VALUES ('Bilal',    'Islamabad', 75,  'A', 'Male')")
cursor.execute("INSERT INTO student VALUES ('Usman',    'Peshawar',  60,  'B', 'Male')")
cursor.execute("INSERT INTO student VALUES ('Zara',     'Islamabad', 95,  'A', 'Female')")
cursor.execute("INSERT INTO student VALUES ('Hina',     'Peshawar',  45,  'C', 'Female')")
cursor.execute("INSERT INTO student VALUES ('Farhan',   'Quetta',    80,  'A', 'Male')")
cursor.execute("INSERT INTO student VALUES ('Sana',     'Quetta',    35,  'B', 'Female')")
cursor.execute("INSERT INTO student VALUES ('Tariq',    'Islamabad', 70,  'B', 'Male')")
cursor.execute("INSERT INTO student VALUES ('Maira',    'Peshawar',  50,  'C', 'Female')")
print("Inserted records are:")

data = cursor.execute("SELECT * FROM student")

for row in data:
    print(row)

connection.commit()