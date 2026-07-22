import duckdb

con = duckdb.connect("db/oee.db")

con.sql("SHOW TABLES").show()