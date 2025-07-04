import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# --- Delete old quizzes for Unit 1 ---
cursor.execute("DELETE FROM quizzes WHERE unit_id = 1")
conn.commit()
print("Old quiz data for Unit 1 deleted.\n")

# --- Confirm it's deleted ---
cursor.execute("SELECT * FROM quizzes WHERE unit_id = 1")
remaining_quizzes = cursor.fetchall()
print("Remaining quizzes for Unit 1:", remaining_quizzes)

# --- Optional: print all users ---
cursor.execute("SELECT * FROM users")
users = cursor.fetchall()
print("\nUsers:")
for user in users:
    print(user)

# --- Optional: print all progress ---
cursor.execute("SELECT * FROM progress")
progress = cursor.fetchall()
print("\nProgress:")
for p in progress:
    print(p)

# --- Optional: print all feedback ---
cursor.execute("SELECT * FROM feedback")
feedbacks = cursor.fetchall()
print("\nFeedback:")
for f in feedbacks:
    print(f)

conn.close()
