from enum import Enum
from jinja2 import Template
import traceback

from dust import Datatypes, ValueTypes, Operation, MetaProps, FieldProps
from dust.entity import EntityTypes, EntityBaseMeta, Store

_sql_persister = None

def init_sql_persist(unit_name, persist_class, meta_type_enums):
    global _sql_persister
    if _sql_persister is None:
        _sql_persister = persist_class()

    _sql_persister.generate_schema(unit_name, meta_type_enums)

class SqlField():
    def __init__(self, field_name, field_type, primary_key=False):
        self.field_name = field_name
        self.field_type = field_type
        self.primary_key = primary_key

class SqlTable():
    def __init__(self, table_name):
        self.table_name = table_name
        self.fields = []

    def add_field(self, sql_field, sql_type):
        self.fields.append(SqlField(sql_field, sql_type, sql_field == "_global_id"))

class SqlPersist():
    def __init__(self, create_connection):
        self.__create_connection = create_connection

    def table_exits(self, table_name, conn):
        pass 

    def sql_type(self, datatype, valuetype):
        pass

    def create_table_template(self):
        pass 

    def __render_tempate(self, template_func, **kwargs):
        try: 
            template = Template(template_func())
            return template.render(**kwargs)
        except:
            traceback.print_exc()

    def table_schema(self, table_name, fields_enum, conn=None):
        if not self.__table_exists_internal(table_name, conn):
            sql_table = SqlTable(table_name)
            sql_table.add_field("_global_id", "TEXT")
            for base_field in EntityTypes._entity_base.fields_enum:
                sql_table.add_field(base_field.name, self.sql_type(base_field.datatype, base_field.valuetype))
            for field in fields_enum:
                sql_table.add_field(field.name, self.sql_type(field.datatype, field.valuetype))
            return self.__render_tempate(self.create_table_template, sql_table=sql_table)

    def __table_exists_internal(self, table_name, conn=None):
        if conn is None:
            with self.__create_connection():
                self.table_exits(table_name, conn)
        else:
            self.table_exits(table_name, conn)

    def generate_schema(self, unit_name, unit_meta_enums, conn=None):
        schema = []
        if conn is None:
            conn = self.__create_connection()

        with conn:
            for unit_meta in unit_meta_enums:
                if unit_meta.type_name[0] != "_":
                    table_name = "{}_{}".format(unit_name, unit_meta.type_name)
                    tbl_schema_string = self.table_schema(table_name, unit_meta.fields_enum, conn)
                    if not tbl_schema_string is None:
                        schema.append(tbl_schema_string)

        for sch in schema:
            print(sch)

        return schema
