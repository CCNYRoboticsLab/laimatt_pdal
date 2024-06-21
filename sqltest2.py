import mysql.connector


def test_insert_data(mysql_connection):
    cursor = mysql_connection.cursor()
    cursor.execute("INSERT INTO users (name, email) VALUES (%s, %s)", ("John Doe", "john@example.com"))
    mysql_connection.commit()
    cursor.execute("SELECT * FROM users WHERE name=%s", ("John Doe",))
    result = cursor.fetchone()
    assert result is not None
    # Clean up (delete the inserted row)
    cursor.execute("DELETE FROM users WHERE name=%s", ("John Doe",))
    mysql_connection.commit()
    

mydb = mysql.connector.connect(
    host="localhost",
    user="root",  # Your MySQL username
    password="",  # Your MySQL password (if any)
    port=3308,  # Your MySQL port
    unix_socket="/opt/lampp/var/mysql/mysql.sock"
)

cursor = mydb.cursor()

# Now you can execute SQL queries:
cursor.execute("USE sample")
cursor.execute("SHOW TABLES")
test = cursor.fetchall()
print(test)

cursor.execute("INSERT INTO patch_crack (center_lat, center_long, center_alt, file_path) VALUES ('%s', '%s', '%s', 'Stavanger')")
mydb.commit()

# Close the connection when done
mydb.close()
