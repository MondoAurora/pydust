import pysqlite3
import traceback

from dust.persist.sqlpersist import SqlPersist

from dust import Datatypes, ValueTypes, Operation, MetaProps, FieldProps
from dust.entity import Entity

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

INSERT_INTO_TABLE_TEMPLATE = "\
INSERT INTO {{sql_table.table_name}} (\
{% for field in sql_table.fields %}\
{{ field.field_name }}{% if not loop.last %},{% endif %}\
{% endfor %}\
) VALUES (\
{% for field in sql_table.fields %}\
?{% if not loop.last %},{% endif %}\
{% endfor %}\
)\
"

SELECT_TEMPLATE = "\
SELECT \
{% for field in sql_table.fields %}\
{{ field.field_name }}{% if not loop.last %},{% endif %} \
{% endfor %}\
FROM {{sql_table.table_name}} \
{% if filters %}\
WHERE \
{% for filter in filters %}\
filter[0] filter[1] ? {% if not loop.last %}AND {% endif %}\
{% endfor %}\
{% endif %}\
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

    def create_table_template(self):
        return CREATE_TABLE_TEMPLATE 

    def create_table(self, sql, conn):
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
        except:
            traceback.print_exc()
        finally:
            cursor.close()

    def insert_into_table_template(self):
        return INSERT_INTO_TABLE_TEMPLATE

    def select_template(self, filters):
        return SELECT_TEMPLATE

    def convert_value_to_db(self, field, value):
        if field.datatype == Datatypes.BOOL:
            if value == True:
                return 1
            else:
                return 0
        elif field.datatype == Datatypes.ENTITY and isinstance(value, Entity):
            return value.global_id()
        else:
            return value

    def convert_value_from_db(self, field, value):
        if field.datatype == Datatypes.BOOL:
            if value == 1:
                return True
            else:
                return False
        else:
            return value

    def sql_type(self, datatype, valuetype):
        if valuetype == ValueTypes.SINGLE:
            return SQL_TYPE_MAP[datatype]
        else:
            return "TEXT"
