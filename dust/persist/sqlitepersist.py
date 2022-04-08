import pysqlite3
import traceback

from dust.persist.sqlpersist import SqlPersist

from dust import Datatypes, ValueTypes, Operation, MetaProps, FieldProps

SQL_TYPE_MAP = {
    Datatypes.INT: "INTEGER",
    Datatypes.NUMERIC: "REAL",
    Datatypes.BOOL: "INTEGER",
    Datatypes.STRING: "TEXT",
    Datatypes.BYTES: "BLOB",
    Datatypes.JSON: "TEXT",
    Datatypes.ENTITY: "TEXT"
}

CREATE_TABLE_TEMPLATE = "\
CREATE TABLE IF NOT EXISTS {{sql_table.table_name}} (\n\
    {% for field in sql_table.fields %}\
    {{ field.field_name }} {{ field.field_type }}{% if field.primary_key %} PRIMARY KEY{% endif %}{% if not loop.last %},{% endif %}\n\
    {% endfor %}\
)\n\
"

DB_FILE = "dust.db"

class SqlitePersist(SqlPersist):
    def __init__(self):
        super().__init__(self.__create_connection)

    def __create_connection(self):
        conn = None
        try:
            conn = pysqlite3.connect(DB_FILE)
        except Exception as e:
            print(e)

        return conn

    def table_exits(self, table_name, conn):
        try:

            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            rows = cur.fetchall()

            for row in rows:
                if row[0] == table_name:
                    return True
        except:
            traceback.print_exc()

        return False

    def sql_type(self, datatype, valuetype):
        if valuetype == ValueTypes.SINGLE:
            return SQL_TYPE_MAP[datatype]
        else:
            return "TEXT"

    def create_table_template(self):
        return CREATE_TABLE_TEMPLATE 
