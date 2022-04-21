from enum import Enum
from jinja2 import Template
import traceback
import json

from dust import Datatypes, ValueTypes, Operation, MetaProps, FieldProps
from dust.entity import UNIT_ENTITY, EntityTypes, EntityBaseMeta, Store, UnitMeta
from dust.events import UNIT_EVENTS, EventTypes

_sql_persister = None
_types_initiated = set()

def init_sql_persist(unit_name, persist_class, meta_type_enums, deps_func):
    global _sql_persister
    global _types_initiated

    if not meta_type_enums in _types_initiated:
        print("Persist: Initiating {}/{}".format(unit_name, meta_type_enums.__name__))
        _types_initiated.add(meta_type_enums)

        if _sql_persister is None:
            _sql_persister = persist_class()

        _sql_persister.generate_schema(unit_name, meta_type_enums)

        if deps_func:
            unit_dependencies = deps_func()
            if unit_dependencies:
                for dep_unit_name, dep_meta_type_enums, dep_deps_func in unit_dependencies:
                    init_sql_persist(dep_unit_name, persist_class, dep_meta_type_enums, dep_deps_func)

def load_all():
    global _sql_persister
    return _sql_persister.load_all()    

def persist_entities(entities):
    global _sql_persister
    _sql_persister.persist_entities(entities)    

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
        self.__persisted_types = set()
        self.__unit_meta_unit = {}

    def table_exits(self, table_name, conn):
        pass 

    def sql_type(self, datatype, valuetype):
        pass

    def create_table_template(self):
        pass 

    def create_table(self, sql, conn):
        pass

    def insert_into_table_template(self):
        pass

    def select_template(self, filters):
        pass

    def convert_value_to_db(self, field, value):
        pass

    def map_value_to_db(self, field, entity):
        value = entity.access(Operation.GET, None, field)
        if value is None:
            return None 
        else:
            if field.valuetype == ValueTypes.SINGLE:
                return self.convert_value_to_db(field, value)

            elif field.valuetype == ValueTypes.SET:
                return json.dumps([self.convert_value_to_db(field, v) for v in value])

            elif field.valuetype == ValueTypes.LIST:
                return json.dumps([self.convert_value_to_db(field, v) for v in value])

            elif field.valuetype == ValueTypes.MAP:
                return json.dumps(value)

    def map_value_from_db(self, field, value):
        if value is None:
            return None

        else:
            if field.valuetype == ValueTypes.SINGLE:
                return self.convert_value_from_db(field, value)

            elif field.valuetype == ValueTypes.SET:
                return set([self.convert_value_from_db(field, v) for v in json.loads(value)])

            elif field.valuetype == ValueTypes.LIST:
                return [self.convert_value_from_db(field, v) for v in json.loads(value)]

            elif field.valuetype == ValueTypes.MAP:
                return json.loads(value)

    def load_all(self):
        entities = []
        for unit_meta in self.__persisted_types:
            if unit_meta.type_name[0] != "_":
                entities.extend(self.load_entities(unit_meta, filters=None, conn=None))

        return entities

    def load_entities(self, meta_type, filters=None, conn=None):
        entities = []

        close_connection = ( conn is None )
        if conn is None:
            conn = self.__create_connection()

        try:
            try:
                sql_table = self.__sql_table(self.__table_name(meta_type), meta_type.fields_enum)
                select_sql = self.__render_tempate(self.select_template, filters, sql_table=sql_table, filters=filters)

                c = conn.cursor()

                print("{} with {}".format(select_sql, filters))
                if filters:
                    c.execute(select_sql, tuple([f[2] for f in filters]))
                else:
                    c.execute(select_sql)

                rows = c.fetchall()
                for row in rows:
                    print(row[0])
                    unit_global_id = row[1]
                    meta_type_global_id = row[2]
                    entity_id = row[3]
                    unit_entity = Store.access(Operation.GET, None, row[1])
                    meta_type_entity = Store.access(Operation.GET, None, row[2])
                    #print("{}:{}:{}".format(unit_entity, row[3], meta_type_entity))
                    entity = Store.access(Operation.GET, None, unit_entity, row[3], meta_type_entity)
                    entity.set_committed()

                    index = 4 # 0 - global_id 1-3: base fields
                    for field in meta_type.fields_enum:
                        value = self.map_value_from_db(field, row[index])
                        if value:
                            if field.valuetype in [ValueTypes.SET, ValueTypes.LIST]:
                                for v in value:
                                    entity.access(Operation.ADD, v, field)
                            else:
                                entity.access(Operation.SET, value, field)

                        index += 1

                    entities.append(entities)
            finally:
                c.close()
        finally:
            if close_connection:
                conn.close()

        return entities


    def insert_entity(self, entity, conn=None):
        return_value = False

        close_connection = ( conn is None )
        if conn is None:
            conn = self.__create_connection()

        meta_type = entity.get_meta_type_enum()
        if meta_type in self.__persisted_types:
            sql_table = self.__sql_table(self.__table_name(meta_type), meta_type.fields_enum)

            insert_sql = self.__render_tempate(self.insert_into_table_template, sql_table=sql_table)
            values = []
            values.append(entity.global_id())
            values.append(entity.unit.global_id())
            values.append(entity.meta_type.global_id())
            values.append(entity.entity_id)
            for field in meta_type.fields_enum:
                values.append(self.map_value_to_db(field, entity))

            try:
                try:
                    c = conn.cursor()
                    #print("Inserting {} with {}".format(values, insert_sql))
                    c.execute(insert_sql, values)

                    return_value = True
                finally:
                    c.close()
            finally:
                if close_connection:
                    conn.close()

        return False

    def persist_entities(self, entities):
        conn = self.__create_connection()
        with conn:
            for e in entities:
                self.insert_entity(e, conn)

    def __render_tempate(self, template_func, *args, **kwargs):
        try: 
            template = Template(template_func(*args))
            return template.render(**kwargs)
        except:
            traceback.print_exc()

    def __table_name(self, unit_meta):
        return "{}_{}".format(self.__unit_meta_unit[unit_meta], unit_meta.type_name)

    def __sql_table(self, table_name, fields_enum):
        sql_table = SqlTable(table_name)
        sql_table.add_field("_global_id", "TEXT")
        for base_field in EntityTypes._entity_base.fields_enum:
            if base_field != EntityBaseMeta.committed:
                sql_table.add_field(base_field.name, self.sql_type(base_field.datatype, base_field.valuetype))
        for field in fields_enum:
            sql_table.add_field(field.name, self.sql_type(field.datatype, field.valuetype))

        return sql_table

    def table_schema(self, unit_meta, conn=None):
        table_name = self.__table_name(unit_meta)
        if not self.__table_exists_internal(table_name, conn):
            sql_table = self.__sql_table(table_name, unit_meta.fields_enum)
            return self.__render_tempate(self.create_table_template, sql_table=sql_table)

    def __table_exists_internal(self, table_name, conn=None):
        if conn is None:
            with self.__create_connection():
                self.table_exits(table_name, conn)
        else:
            self.table_exits(table_name, conn)

    def __generate_base_schema(self, conn=None):
        self.generate_schema(UNIT_ENTITY, EntityTypes, conn)
        #self.generate_schema(UNIT_EVENTS, EventTypes, conn)

    def generate_schema(self, unit_name, unit_meta_enums, conn = None):
        close_connection = ( conn is None )
        schema = []

        if conn is None:
            conn = self.__create_connection()

        try:
            for unit_meta in unit_meta_enums:
                self.__unit_meta_unit[unit_meta] = unit_name
                self.__persisted_types.add(unit_meta)
                if unit_meta.type_name[0] != "_":
                    table_name = self.__table_name(unit_meta)
                    tbl_schema_string = self.table_schema(unit_meta, conn)
                    if not tbl_schema_string is None:
                        schema.append(tbl_schema_string)
                        self.create_table(tbl_schema_string, conn)
            if not EntityTypes.unit in self.__persisted_types:
                self.__generate_base_schema(conn)
        finally:
            if close_connection:
                conn.close()

        for sch in schema:
            print(sch)

        return schema
