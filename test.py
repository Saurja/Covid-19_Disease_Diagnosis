import sqlite3 as sql

con = sql.connect('patientData.db')
cursor = con.cursor()
# cursor.execute("SELECT * from PatientRecords.COLUMNS")
cursor.execute("SELECT * FROM PatientRecords")
col_name_list = [tuple[0] for tuple in cursor.description]

print(col_name_list)