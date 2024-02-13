from jinja2 import Template
import traceback
import json
import time
import io
import datetime
import os

from dust import Datatypes, ValueTypes, Operation, Committed
from dust.entity import UNIT_ENTITY, EntityTypes, EntityBaseMeta, Store, UnitMeta
from dust.events import FORMAT_DB_DATETIME

_sql_persister = None
_types_initiated = set()

UPDATE_BATCH = 500000

def init_sql_persist(unit_name, persist_class, meta_type_enums, deps_func):
    global _sql_persister
    global _types_initiated

    if not meta_type_enums in _types_initiated:
        print("Persist: Initiating {}/{}".format(unit_name, meta_type_enums.__name__))

        if _sql_persister is None:
            _sql_persister = persist_class()

        schemas = _sql_persister.generate_schema(unit_name, meta_type_enums)
        if schemas:
            print(f"{unit_name} meta has changed")
            for e in Store.access(Operation.VISIT, None):
                if e.get_meta_type_enum() == EntityTypes.unit and e.access(Operation.GET, None, UnitMeta.name) == f"{unit_name}_meta":
                    unit_meta_entity = e;
                    meta_persist_entities = [pe for pe in Store.access(Operation.WALK, None, [e]) if pe.unit == unit_meta_entity]
                    meta_persist_entities.append(unit_meta_entity)

                    # delete schema for unit_meta
                    delete_map = {}
                    # Delete entity_unit
                    print(f"Deleting meta in unit {e.global_id()}/{unit_name}")
                    _sql_persister._SqlPersist__prepare_delete_updating_meta_records(delete_map, "entity_unit", [("_global_id", "=", unit_meta_entity.global_id())])
                    _sql_persister._SqlPersist__prepare_delete_updating_meta_records(delete_map, "entity_unit_meta_types", [("_global_id", "=", unit_meta_entity.global_id())])
                    _sql_persister._SqlPersist__prepare_delete_updating_meta_records(delete_map, "entity_type_meta", [("_unit", "=", unit_meta_entity.global_id())])
                    _sql_persister._SqlPersist__prepare_delete_updating_meta_records(delete_map, "entity_type_meta_fields", [("_global_id", "like", f"{unit_name}_meta:%:type_meta")])
                    _sql_persister._SqlPersist__prepare_delete_updating_meta_records(delete_map, "entity_meta_field", [("_global_id", "like", f"{unit_name}_meta:%:meta_field")])
                    _sql_persister._SqlPersist__delete_updating_meta_records(delete_map)

                    persist_entities(meta_persist_entities)

        _types_initiated.add(meta_type_enums)

        if deps_func:
            unit_dependencies = deps_func()
            if unit_dependencies:
                for dep_unit_name, dep_meta_type_enums, dep_deps_func in unit_dependencies:
                    init_sql_persist(dep_unit_name, persist_class, dep_meta_type_enums, dep_deps_func)

    _sql_persister.print_table_alterations(unit_name)

def load_all():
    global _sql_persister
    return _sql_persister.load_all()    

def load_units():
    global _sql_persister
    return _sql_persister.load_units()    

def load_unit_type(unit_meta_type, where_filters=None, load_referenced=False, entity_filter_method=None):
    global _sql_persister
    return _sql_persister.load_type(unit_meta_type, where_filters=where_filters, load_referenced=load_referenced, entity_filter_method=entity_filter_method)    

def load_entity_ids_for_type(unit_meta_type):
    global _sql_persister
    return _sql_persister.load_entity_ids_for_type(unit_meta_type)    

def persist_entities(entities):
    global _sql_persister
    _sql_persister.persist_entities(entities)   

def  dump_database(stream):
    global _sql_persister
    _sql_persister.dump_database(stream)

BASE_FIELD_NAMES = [f"_{base_field.name}" for base_field in EntityTypes._entity_base.fields_enum if base_field != EntityBaseMeta.committed]
BASE_FIELD_NAMES.insert(0, "_global_id")
MULTIVALUE_BASE_FIELD_NAMES = ["_global_id", "_value_cnt"]

ALL_TABLES = {}

class SqlField():
    def __init__(self, field_name, field_type, primary_key=False, base_field=False):
        self.field_name = field_name
        self.field_type = field_type
        self.primary_key = primary_key
        self.base_field = base_field

class SqlTable():
    
    def __init__(self, table_name):
        self.table_name = table_name
        self.fields = []
        self.primary_keys = []
        self.value_tables_by_fields = {}
        self.multi_value_table = False

    def add_field(self, sql_field, sql_type, primary_key=False, base_field=False):
        field = SqlField(sql_field, sql_type, primary_key, base_field)
        self.fields.append(field)
        if primary_key:
            self.primary_keys.append(field)

class SqlPersist():
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.__persisted_types = set()
        self.__unit_meta_unit = {}

    def table_exits(self, table_name, conn):
        pass 

    def sql_type(self, datatype, valuetype, primary_key=False):
        pass

    def create_table_template(self, sql_table):
        pass 

    def alter_table_template(self):
        pass 

    def delete_table_template(self):
        pass 

    def alter_table(self, sql, conn):
        pass

    def insert_into_table_template(self):
        pass

    def select_template(self, where_filters):
        pass

    def update_template(self):
        pass

    def delete_template(self, where_filters):
        pass

    def convert_value_to_db(self, field, value):
        pass

    def create_cursor(self, conn):
        pass

    def close_cursor(self, conn):
        pass

    def create_exectute_params(self):
        pass

    def add_execute_param(self, values, name, value, operator="=", named_param=True):
        pass

    def map_value_to_db(self, field, entity):
        value = entity.access(Operation.GET, None, field)
        if value is None:
            return None 
        else:
            if field.valuetype == ValueTypes.SINGLE:
                return self.convert_value_to_db(field, value)

            elif field.valuetype == ValueTypes.SET:
                return [self.convert_value_to_db(field, v) for v in value]

            elif field.valuetype == ValueTypes.LIST and field.datatype != Datatypes.JSON:
                return [self.convert_value_to_db(field, v) for v in value]

            elif field.valuetype == ValueTypes.MAP or field.valuetype == ValueTypes.LIST:
                return json.dumps(value)

    def map_value_from_db(self, field, value):
        if value is None:
            return None

        else:
            if field.valuetype in [ValueTypes.SINGLE, ValueTypes.SET, ValueTypes.LIST] and field.datatype != Datatypes.JSON:
                return self.convert_value_from_db(field, value)

            elif field.valuetype == ValueTypes.MAP or field.valuetype == ValueTypes.LIST:
                return json.loads(value)

    def load_all(self):
        entities = []
        for unit_meta in self.__persisted_types:
            entities.extend(self.load_type(unit_meta))

        return entities

    def load_units(self):
        entities = []
        for unit_meta in EntityTypes:
            entities.extend(self.load_type(unit_meta))

        return entities

    def load_type(self, unit_meta, where_filters=None, load_referenced=False, entity_filter_method=None):
        entities = []

        if unit_meta.type_name[0] != "_":
            entities = self.load_entities(unit_meta, where_filters=where_filters, conn=None, entity_filter_method=entity_filter_method)

        if load_referenced:
            loaded_global_ids = set()
            requested_global_ids = set()
            loaded_global_ids.update([e.global_id() for e in entities])

            while True:
                walked_entities = Store.access(Operation.WALK, None, list(entities))
                load_map = {}

                for entity in walked_entities:
                    if entity.get_meta_type_enum() in self.__persisted_types and entity.committed == Committed.CREATED:
                        if not entity.global_id() in loaded_global_ids and not entity.global_id() in requested_global_ids:
                            load_map.setdefault(entity.get_meta_type_enum(), []).append(entity.entity_id)
                            requested_global_ids.add(entity.global_id())

                if not load_map:
                    break

                for meta_type, global_ids in load_map.items():
                    # Sub entities are always loaded, so do not apply entity_filter_method
                    loaded = self.load_entities(meta_type, where_filters=[("_entity_id", "in", global_ids)])
                    loaded_global_ids.update([e.global_id() for e in loaded])

        return entities

    def load_entity_ids_for_type(self, meta_type, where_filters=None, conn=None):
        entity_ids = []

        close_connection = ( conn is None )
        if conn is None:
            conn = self._create_connection()

        try:
            sql_tables = self.__sql_tables(self.__table_name(meta_type), meta_type.fields_enum)

            try:
                select_sql = self.__render_tempate(self.select_template, where_filters, sql_table=sql_tables[0], where_filters=where_filters)

                c = self._create_cursor(conn)

                print("{} with {}".format(select_sql, where_filters))
                if where_filters:
                    values = self.create_exectute_params()
                    for f in where_filters:
                        self.add_execute_param(values, f[0], f[2], f[1])
                    c.execute(select_sql, values)
                else:
                    c.execute(select_sql)

                rows = c.fetchall()
                for row in rows:
                    entity_ids.append(row[3])
            finally:
                self._close_cursor(c)

        finally:
            if close_connection:
                self._close_connection(conn)

        return entity_ids

    def load_entities(self, meta_type, where_filters=None, conn=None, entity_filter_method=None):
        entities = {}

        close_connection = ( conn is None )
        if conn is None:
            conn = self._create_connection()

        try:
            sql_tables = self.__sql_tables(self.__table_name(meta_type), meta_type.fields_enum)

            try:
                select_sql = self.__render_tempate(self.select_template, where_filters, sql_table=sql_tables[0], where_filters=where_filters)

                c = self._create_cursor(conn)

                #print("{} with {}".format(select_sql, where_filters))
                if where_filters:
                    values = self.create_exectute_params()
                    for f in where_filters:
                        self.add_execute_param(values, f[0], f[2], f[1])
                    c.execute(select_sql, values)
                else:
                    c.execute(select_sql)

                global_ids = set()

                rows = c.fetchall()
                for row in rows:
                    #print(row[0])
                    global_ids.add(row[0])
                    unit_global_id = row[1]
                    meta_type_global_id = row[2]
                    entity_id = row[3]
                    unit_entity = Store.access(Operation.GET, None, row[1])
                    meta_type_entity = Store.access(Operation.GET, None, row[2])
                    #print("{}:{}:{}".format(unit_entity, row[3], meta_type_entity))
                    entity = Store.access(Operation.GET, None, unit_entity, row[3], meta_type_entity)

                    index = 4 # 0 - global_id 1-3: base fields
                    for field in meta_type.fields_enum:
                        if not field.valuetype in [ValueTypes.LIST, ValueTypes.SET] or field.valuetype == ValueTypes.LIST and field.datatype == Datatypes.JSON:
                            value = self.map_value_from_db(field, row[index])
                            if not value is None:
                                entity.access(Operation.SET, value, field)

                            index += 1

                    entity.set_committed()
                    if entity_filter_method is None or entity_filter_method(entity):
                        entities[row[0]] = entity
                    elif entity_filter_method is not None:
                        entity.delete()
                        global_ids.remove(row[0])
            finally:
                self._close_cursor(c)

            # Do multivalue fields
            for field in meta_type.fields_enum:
                if field.valuetype in [ValueTypes.LIST, ValueTypes.SET] and field.datatype != Datatypes.JSON:
                    multivalue_sql_table = None
                    for stbl in sql_tables:
                        if stbl.table_name == "{}_{}".format(sql_tables[0].table_name, field.name):
                            multivalue_sql_table = stbl
                            break
                    multivalue_select_sql = self.__render_tempate(self.select_template, None, sql_table=multivalue_sql_table, filtwhere_filtersers=None)
                    try:
                        c = self._create_cursor(conn)
                        #print("{}".format(multivalue_select_sql))
                        c.execute(multivalue_select_sql)
                        rows = c.fetchall()
                        for row in rows:
                            if row[0] in global_ids:
                                entities[row[0]].access(Operation.ADD, self.map_value_from_db(field, row[2]), field)
                                entities[row[0]].set_committed()

                    finally:
                        self._close_cursor(c)
        finally:
            if close_connection:
                self._close_connection(conn)

        return entities.values()
    
    def __delete_updating_meta_records(self, delete_map):
        conn = None
        try:
            conn = self._create_connection()
            conn.autocommit = False
            committed_entities = []
            return_value = self.__update_entity_values(conn, delete_map, "delete", committed_entities)
            delete_map.clear()
            conn.commit()
            print("Committing meta deletion")
        except:
            traceback.print_exc()
            conn.rollback()
            return_value = False
        finally:
            self._close_connection(conn)

        return return_value

    def __prepare_delete_updating_meta_records(self, delete_map, table_name, where_filters):
        delete_sql = self.__render_tempate(self.delete_template, where_filters, sql_table=table_name, where_filters=where_filters)
        #print(delete_sql)
        delete_values = self.create_exectute_params(named_param=True)
        for where_filter in where_filters:
            self.add_execute_param(delete_values, name=where_filter[0], value=where_filter[2], operator=where_filter[1], named_param=True)
        delete_map[delete_sql] = [(None, delete_values)]

    def __prepare_update_entity_multivalues(self, entity, sql_tables, multivalues, update_map, delete_map=None):
        if len(sql_tables) > 1:
            for idx, sql_table in enumerate(sql_tables[1:], start=1):
                if not delete_map is None:
                    delete_sql = self.__render_tempate(self.delete_template, sql_table=sql_table)
                    delete_values = self.create_exectute_params(named_param=False)
                    self.add_execute_param(delete_values, "_global_id", entity.global_id(), named_param=False)
                    delete_map.setdefault(delete_sql, []).append((None, tuple(delete_values)))

                field_name, multivalues_array = multivalues[sql_table.table_name]
                if multivalues_array:
                    insert_sql = self.__render_tempate(self.insert_into_table_template, sql_table=sql_table)
                    for value_cnt, value in enumerate(multivalues_array):
                        values = self.create_exectute_params(named_param=False)
                        self.add_execute_param(values, "_global_id", entity.global_id(), named_param=False)
                        self.add_execute_param(values, "_value_cnt", value_cnt, named_param=False)
                        self.add_execute_param(values, "_"+field_name+"_value", value, named_param=False)
                        update_map.setdefault(insert_sql, []).append((None, tuple(values)))

    def __prepare_insert_entity(self, entity, insert_map):
        meta_type = entity.get_meta_type_enum()
        if meta_type in self.__persisted_types:
            sql_tables = self.__sql_tables(self.__table_name(meta_type), meta_type.fields_enum)
            multivalues = {}

            insert_sql = self.__render_tempate(self.insert_into_table_template, sql_table=sql_tables[0])
            values = self.create_exectute_params(named_param=False)
            self.add_execute_param(values, "_global_id", entity.global_id(), named_param=False)
            self.add_execute_param(values, "_unit", entity.unit.global_id(), named_param=False)
            self.add_execute_param(values, "_meta_type", entity.meta_type.global_id(), named_param=False)
            self.add_execute_param(values, "_entity_id", entity.entity_id, named_param=False)
            for field in meta_type.fields_enum:
                if not field.valuetype in [ValueTypes.LIST, ValueTypes.SET] or field.datatype == Datatypes.JSON and field.valuetype == ValueTypes.LIST:
                    self.add_execute_param(values, "_"+field.name, self.map_value_to_db(field, entity), named_param=False)
                else:
                    multivalue_tablename = "{}_{}".format(sql_tables[0].table_name, field.name)
                    multivalues[multivalue_tablename] = (field.name, self.map_value_to_db(field, entity))

            insert_map.setdefault(insert_sql, []).append((entity, tuple(values)))
            self.__prepare_update_entity_multivalues(entity, sql_tables, multivalues, insert_map)


    def __prepare_update_entity(self, entity, update_map, delete_map):
        meta_type = entity.get_meta_type_enum()
        if meta_type in self.__persisted_types:
            sql_tables = self.__sql_tables(self.__table_name(meta_type), meta_type.fields_enum)

            update_sql = self.__render_tempate(self.update_template, sql_table=sql_tables[0])
            values = self.create_exectute_params(named_param=False)

            multivalues = {}

            for field in meta_type.fields_enum:
                if not field.valuetype in [ValueTypes.LIST, ValueTypes.SET] or field.datatype == Datatypes.JSON and field.valuetype == ValueTypes.LIST:
                    self.add_execute_param(values, "_"+field.name, self.map_value_to_db(field, entity), named_param=False)
                else:
                    multivalue_tablename = "{}_{}".format(sql_tables[0].table_name, field.name)
                    multivalues[multivalue_tablename] = (field.name, self.map_value_to_db(field, entity))

            self.add_execute_param(values, "_global_id", entity.global_id(), named_param=False)

            update_map.setdefault(update_sql, []).append((entity, tuple(values)))
            self.__prepare_update_entity_multivalues(entity, sql_tables, multivalues, update_map, delete_map)

    def __is_entity_protected(self, e):
        meta_type = e.get_meta_type_enum()

        protected_unit_names = set()
        for type_initiated in _types_initiated:
            for type_initiated_meta_type in type_initiated:
                protected_unit_names.add(type_initiated_meta_type.unit_name)

        if meta_type == EntityTypes.unit:
            if e.access(Operation.GET, None, UnitMeta.name) in protected_unit_names:
                print(f"Protected unit, not updating: {e.unit.access(Operation.GET, None, UnitMeta.name)}")
                return True
        elif meta_type in [EntityTypes.meta_field, EntityTypes.type_meta]:
            if e.unit.access(Operation.GET, None, UnitMeta.name) in protected_unit_names:
                print(f"Protected {meta_type} in unit {e.unit.access(Operation.GET, None, UnitMeta.name)}. Not updating!")
                return True

        return False

    def persist_entities(self, entities):
        conn = None
        cnt = 0
        return_value = True
        committed_entities = []
        try:
            print("Persist {} entities".format(len(entities)))
            conn = self._create_connection()
            conn.autocommit = False

            update_map = {}
            delete_map = {}
            cnt = 0
            for e in entities:
                if self.__is_entity_protected(e):
                    continue
                if e.committed == Committed.UPDATED:
                    self.__prepare_update_entity(e, update_map, delete_map)
                    cnt += 1
                
                if cnt % UPDATE_BATCH == 0:
                    print("Update: {}".format(cnt))
                    if return_value and delete_map:
                        return_value = self.__update_entity_values(conn, delete_map, "delete", committed_entities)
                        delete_map.clear()
                    if return_value and update_map:
                        return_value = self.__update_entity_values(conn, update_map, "update", committed_entities)
                        update_map.clear()
                    if not return_value:
                        raise Exception("Update failed")
                    cnt = 0

            if return_value and ( update_map or delete_map ):
                print("Update: {}".format(cnt))
                if return_value and delete_map:
                    return_value = self.__update_entity_values(conn, delete_map, "delete", committed_entities)
                    delete_map.clear()
                if return_value and update_map:
                    return_value = self.__update_entity_values(conn, update_map, "update", committed_entities)
                    update_map.clear()
                if not return_value:
                    raise Exception("Update failed")

            insert_map = {}
            cnt = 0
            for e in entities:
                if self.__is_entity_protected(e):
                    continue
                if e.committed == Committed.CREATED:
                    self.__prepare_insert_entity(e, insert_map)
                    cnt += 1

                if return_value and insert_map and cnt % UPDATE_BATCH == 0:
                    print("Insert: {}".format(cnt))
                    return_value = self.__update_entity_values(conn, insert_map, "insert", committed_entities)
                    insert_map.clear()
                    if not return_value:
                        raise Exception("Insert failed")
                    cnt = 0

            if return_value and insert_map:
                cnt = len(insert_map)
                print("Insert: {}".format(cnt))
                return_value = self.__update_entity_values(conn, insert_map, "insert", committed_entities)
                insert_map.clear()
                if not return_value:
                    raise Exception("Insert failed")


            if return_value:
                conn.commit()
                print("Committing {} entities".format(len(committed_entities)))
                for e in committed_entities:
                    e.set_committed()
            else:
                conn.rollback()

        except:
            traceback.print_exc()
            conn.rollback()
            return_value = False
        finally:
            self._close_connection(conn)

        return return_value

    def __update_entity_values(self, conn, map, update_type, committed_entities):
        print("Start executing {}: {}".format(update_type, len(map.keys())))
        sorted_keys = sorted(map, key=lambda k: len(map[k]))
        for sql in sorted_keys:
            try:
                value_array = map[sql]
                c = self._create_cursor(conn, prepared=True, buffered=False)
                start = time.time()
                print("SQL: {}, number of values: {}".format(sql, len(value_array)))
                for entity, values in value_array:
                    #if " entity_" in sql:
                    #    print(str(values))
                    c.execute(sql, values)
                    if entity:
                        committed_entities.append(entity)
                end = time.time()
                print("Finished executing in {}".format(end-start))

            except:
                raise Exception("Update failed for sql {} - {}".format(sql, map[sql]))
            finally:
                self._close_cursor(c)

        return True

    def __render_tempate(self, template_func, *args, **kwargs):
        try: 
            template = Template(template_func(*args))
            return template.render(**kwargs)
        except:
            traceback.print_exc()

    def __table_name(self, unit_meta):
        return "{}_{}".format(self.__unit_meta_unit[unit_meta], unit_meta.type_name)

    def __sql_tables(self, table_name, fields_enum):
        sql_tables = []
        sql_table = SqlTable(table_name)
        sql_tables.append(sql_table)
        sql_table.add_field("_global_id", self.sql_type(Datatypes.STRING, ValueTypes.SINGLE, primary_key=True), primary_key=True, base_field=True)
        for base_field in EntityTypes._entity_base.fields_enum:
            if base_field != EntityBaseMeta.committed:
                sql_table.add_field("_"+base_field.name, self.sql_type(base_field.datatype, base_field.valuetype), base_field=True)
        for field in fields_enum:
            if field.valuetype in [ValueTypes.LIST, ValueTypes.SET] and field.datatype != Datatypes.JSON:
                multivalue_sql_table = SqlTable("{}_{}".format(table_name, field.name))
                multivalue_sql_table.add_field("_global_id", self.sql_type(Datatypes.STRING, ValueTypes.SINGLE, primary_key=True), primary_key=True, base_field=True)
                multivalue_sql_table.add_field("_value_cnt", self.sql_type(Datatypes.INT, ValueTypes.SINGLE), primary_key=True, base_field=True)
                multivalue_sql_table.add_field("_"+field.name+"_value", self.sql_type(field.datatype, ValueTypes.SINGLE))
                multivalue_sql_table.multi_value_table = True
                sql_tables.append(multivalue_sql_table)
                sql_table.value_tables_by_fields[field] = multivalue_sql_table
            else:
                sql_table.add_field("_"+field.name, self.sql_type(field.datatype, field.valuetype))

        return sql_tables

    def table_schemas(self, unit_meta, conn=None):

        table_schemas = []
        table_name = self.__table_name(unit_meta)

        created_tables = set()

        sql_tables = self.__sql_tables(table_name, unit_meta.fields_enum)
        for sql_table in sql_tables:
            if not self.__table_exists_internal(sql_table.table_name, conn):
                table_schemas.append(self.__render_tempate(self.create_table_template, sql_table, sql_table=sql_table))
                created_tables.add(sql_table)

        self.get_table_scema_changes(unit_meta, sql_tables, conn)

        for sql_table in sql_tables:
            if sql_table in created_tables:
                continue
            if sql_table.table_name in ALL_TABLES and ALL_TABLES[sql_table.table_name]["meta_sync_status"] == "VISITED":
                if ALL_TABLES[sql_table.table_name]["table_alterations"]:
                    # Add table alterations, so they can be executed
                    for table_alteration in ALL_TABLES[sql_table.table_name]["table_alterations"]:
                        match table_alteration["operation"]:
                            case "DELETE_MULTIVALUE_TABLE" | "DELETE_TABLE":
                                table_schemas.append(self.__render_tempate(self.delete_table_template, sql_table=sql_table))
                            case "CREATE_MULTIVALUE_TABLE":
                                table_schemas.append(self.__render_tempate(self.create_table_template, sql_table, sql_table=sql_table))

                if ALL_TABLES[sql_table.table_name]["field_alterations"]:
                    # Add table alterations, so they can be executed
                    field_modifications = []
                    for field_alterations in ALL_TABLES[sql_table.table_name]["field_alterations"]:
                        if "field_enum" in field_alterations:
                            field_enum = field_alterations["field_enum"]
                        match field_alterations["operation"]:
                            case "CHANGE_DATATYPE":
                                field_modifications.append(f"MODIFY {field_alterations['field_name']} {self.sql_type(Datatypes[field_enum['datatype']], ValueTypes[field_enum['valuetype']], False)}")
                            case "DELETE":
                                field_modifications.append(f"DROP {field_alterations['field_name']}")
                            case "ADD":
                                field_modifications.append(f"ADD {field_alterations['field_name']} {self.sql_type(Datatypes[field_enum['datatype']], ValueTypes[field_enum['valuetype']], False)}")

                    table_schemas.append(self.__render_tempate(self.alter_table_template, sql_table=sql_table, field_modifications=field_modifications))

                ALL_TABLES[sql_table.table_name]["meta_sync_status"] = "SQL_GENERATED"

        return table_schemas
    
    def __compare_table_fields_with_metadata(self, cursor, sql_table, multivalue_table, unit_meta, field_enum=None):
        table_exists = True
        table_specs = None
        try:
            if not ALL_TABLES:
                cursor.execute("SHOW TABLES")
                tables = []
                for table in cursor.fetchall():
                    ALL_TABLES.setdefault(table[0], {"table_name": table[0], "fields": [], "table_alterations": [], "field_alterations": [], "meta_sync_status": None})

                for table, table_specs in ALL_TABLES.items():
                    _multivalue_table = True
                    cursor.execute("DESCRIBE `" + table + "`;")
                    for field in cursor.fetchall():
                        if field[0] != "_global_id" and field[0] in BASE_FIELD_NAMES:
                            _multivalue_table = False
                        table_specs["fields"].append(field)

                    table_specs["multivalue_table"] = _multivalue_table

            table_specs = ALL_TABLES[sql_table.table_name]
            
        except:
            # Table does not exist
            table_exists = False
            table_specs = ALL_TABLES.setdefault(sql_table.table_name, {"table_name": sql_table.table_name, "fields": [], "table_alterations": [], "field_alterations": [], "meta_sync_status": None})

        if table_exists:
            existing_fields = []
            for field in table_specs["fields"]:
                if field[0] not in BASE_FIELD_NAMES:
                    existing_fields.append(field[0])
                    global_field_name = f"{unit_meta.unit_name}:{unit_meta.name}:{field[0][1:]}"
                
                    primary_key = field[3] == "YES"
                    if multivalue_table:
                        if field[0] not in MULTIVALUE_BASE_FIELD_NAMES:
                            sql_type = self.sql_type(field_enum.datatype, field_enum.valuetype, primary_key)
                            if sql_type.lower() != field[1].lower():
                                table_specs["field_alterations"].append({"operation": "CHANGE_DATATYPE", "field_name": field[0], "global_field_name": global_field_name, "field_enum": field_enum.to_json()})
                    else:
                        try:
                            meta_field = unit_meta.fields_enum[field[0][1:]]
                            sql_type = self.sql_type(meta_field.datatype, meta_field.valuetype, primary_key)
                            # Only existing fields get here, so if data type is changing or ValueType.SINGLE -> [ValueTypes.LIST, ValueTypes.SET] is possible, except if it is a JSON field
                            if sql_type.lower() != field[1].lower() or (meta_field.valuetype in [ValueTypes.LIST, ValueTypes.SET] and meta_field.datatype != Datatypes.JSON) :
                                if meta_field.valuetype == ValueTypes.SINGLE:
                                    table_specs["field_alterations"].append({"operation": "CHANGE_DATATYPE", "field_name": field[0], "global_field_name": global_field_name, "field_enum": meta_field.to_json()})
                                else:
                                    table_specs["field_alterations"].append({"operation": "DELETE", "field_name": field[0], "global_field_name": global_field_name, "field_enum": meta_field.to_json()})
                        except KeyError:
                            # field does not exist, delete it
                            table_specs["field_alterations"].append({"operation": "DELETE", "field_name": field[0], "global_field_name": global_field_name})

            if not multivalue_table:
                for meta_field in unit_meta.fields_enum:
                    if not f"_{meta_field.name}" in existing_fields and meta_field.valuetype not in [ValueTypes.LIST, ValueTypes.SET]:
                        global_field_name = f"{unit_meta.unit_name}:{unit_meta.name}:{meta_field.name}"
                        sql_type = self.sql_type(meta_field.datatype, meta_field.valuetype, primary_key)
                        table_specs["field_alterations"].append({"operation": "ADD", "field_name": f"_{meta_field.name}", "global_field_name": global_field_name, "field_enum": meta_field.to_json()})
        else:
            global_field_name = f"{unit_meta.unit_name}:{unit_meta.name}:{field_enum.name}"
            sql_type = self.sql_type(field_enum.datatype, field_enum.valuetype, False)
            table_specs["table_alterations"].append({"operation": "CREATE_MULTIVALUE_TABLE", "field_name": f"_{field_enum.name}", "global_field_name": global_field_name, "field_enum": field_enum.to_json()})

        if ALL_TABLES[sql_table.table_name]["meta_sync_status"] is None:
            ALL_TABLES[sql_table.table_name]["meta_sync_status"] = "VISITED"

    def print_table_alterations(self, unit_name, only_alter=True):
       table_alerations = [{"table_name": f["table_name"], "table_alterations": f["table_alterations"], "meta_sync_status": f["meta_sync_status"]} for f in ALL_TABLES.values() if ( not only_alter or f["table_alterations"] ) and f["table_name"].startswith(f"{unit_name}_")]
       if table_alerations:
            print(json.dumps(table_alerations, indent=4))
    

    def get_table_scema_changes(self, unit_meta, sql_tables, conn=None):
        close_connection = conn is None
        try:
            if conn is None:
                conn = self._create_connection()
            c = self._create_cursor(conn, buffered=False)
            # Get fields:
            self.__compare_table_fields_with_metadata(c, sql_tables[0], False, unit_meta)

            for field, multivalue_sql_table in sql_tables[0].value_tables_by_fields.items():
                self.__compare_table_fields_with_metadata(c, multivalue_sql_table, True, unit_meta, field)

            self._close_cursor(c)

        except:
            traceback.print_exc()
        finally:
            if close_connection:
                self._close_connection(conn)

    def __table_exists_internal(self, table_name, conn=None):
        if conn is None:
            try:
                conn = self._create_connection()
                return self.table_exits(table_name, conn)
            finally:
                self._close_connection(conn)
        else:
            return self.table_exits(table_name, conn)

    def __generate_base_schema(self, conn=None):
        return self.generate_schema(UNIT_ENTITY, EntityTypes, conn)
        #self.generate_schema(UNIT_EVENTS, EventTypes, conn)

    def generate_schema(self, unit_name, unit_meta_enums, conn = None):
        close_connection = ( conn is None )
        schema = []

        if conn is None:
            conn = self._create_connection()

        try:
            for unit_meta in unit_meta_enums:
                self.__unit_meta_unit[unit_meta] = unit_name
                self.__persisted_types.add(unit_meta)
                if unit_meta.type_name[0] != "_":
                    table_name = self.__table_name(unit_meta)
                    tbl_schema_strings = self.table_schemas(unit_meta, conn)
                    for tbl_schema_string in tbl_schema_strings:
                        if not tbl_schema_string is None:
                            print(tbl_schema_string)
                            schema.append(tbl_schema_string)
                            self.alter_table(tbl_schema_string, conn)
            if not EntityTypes.unit in self.__persisted_types:
                schema.extend(self.__generate_base_schema(conn))

            for table_specs in ALL_TABLES.values():
                if table_specs["table_name"].startswith(f"{unit_name}_") and table_specs["meta_sync_status"] is None:
                    sql_table = SqlTable(table_specs["table_name"])
                    tbl_schema_string = self.__render_tempate(self.delete_table_template, sql_table=sql_table)
                    print(tbl_schema_string)
                    schema.append(tbl_schema_string)
                    self.alter_table(tbl_schema_string, conn)
                    #table_specs["table_alterations"].append({"table_name": table_specs["table_name"], "operation": "DELETE_MULTIVALUE_TABLE" if table_specs["multivalue_table"] else "DELETE_TABLE"})
                    #table_specs["meta_sync_status"] = "VISITED"
        finally:
            if close_connection:
                self._close_connection(conn)

        #for sch in schema:
        #    print(sch)

        return schema
    
    def dump_database(self, stream):
        conn = self._create_connection()

        try:

            c = self._create_cursor(conn, buffered=False)

            try:
                max_packet_size = int(os.environ.get("MYSQL_MAX_ALLOWED_PACKET_SIZE", 16 * 1024 * 1024))
            except:
                max_packet_size = 16 * 1024 * 1024
            
            mysql_version = ""

            c.execute("SHOW VARIABLES LIKE 'version'")
            for vars in c.fetchall():
                mysql_version = vars[1]

            stream.write("-- MySQL dump (pydust)\n"+
                         "--\n"+
                         f"-- Host: {os.environ.get('HOSTNAME')}    Database: {os.environ.get('MYSQL_DB')}\n"+
                         "-- ------------------------------------------------------\n"+
                         f"-- Server version	{mysql_version}\n\n")

            stream.write("/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;\n"+
                         "/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;\n"+
                         "/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;\n"+
                         "/*!50503 SET NAMES utf8mb4 */;\n"+
                         "/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;\n"+
                         "/*!40103 SET TIME_ZONE='+00:00' */;\n"+
                         "/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;\n"+
                         "/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;\n"+
                         "/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;\n"+
                         "/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;\n\n")

            c.execute("SHOW TABLES")
            tables = []
            for table in c.fetchall():
                tables.append(table[0])

            # Lower the packet size slightly, just in case
            max_packet_size -= 1000

            for table in tables:
                stream.write("--\n"+
                         f"-- Table structure for table `{table}`\n"+
                         "--\n\n")
                stream.write("DROP TABLE IF EXISTS `" + str(table) + "`;\n")

                stream.write("/*!40101 SET @saved_cs_client     = @@character_set_client */;\n"+
                         "/*!50503 SET character_set_client = utf8mb4 */;")

                c.execute("SHOW CREATE TABLE `" + str(table) + "`;")
                stream.write("\n" + str(c.fetchone()[1]) + ";\n");

                stream.write("/*!40101 SET character_set_client = @saved_cs_client */;\n\n")

                stream.write("--\n"+
                         f"-- Dumping data for table `{table}`\n"+
                         "--\n\n"+
                         f"LOCK TABLES `{table}` WRITE;\n"+
                         f"/*!40000 ALTER TABLE `entity_meta_field` DISABLE KEYS */;\n")

                # Get fields:
                c.execute("DESCRIBE `" + str(table) + "`;")
                fields = []
                for field in c.fetchall():
                    field_type = field[1]
                    if field_type.lower() in ["binary", "varbinary", "blob", "mediumblob", "longblob"]:
                        fields.append((f"HEX({field[0]})", field[0], True)) 
                    else:
                        fields.append((field[0], field[0], False)) 


                c.execute("SELECT {} FROM `{}`;".format(",".join(f[0] for f in fields), table))
                row = c.fetchone()

                row_index = 0
                packet_length  = 0

                empty_table = True

                if row is not None:
                    empty_table = False
                    insert_str = "INSERT INTO `{}` ({}) VALUES ".format(table, ",".join(f[1] for f in fields))
                    packet_length = len(insert_str)
                    stream.write(insert_str)
                    first_row = True

                while row is not None:
                    row_stream = io.StringIO("")

                    if not first_row:
                        row_stream.write(",")

                    row_stream.write("(")
                    first = True
                    for field_idx in range(len(fields)):
                        field = fields[field_idx]
                        if not first:
                            row_stream.write(",");
                        if row[field_idx] is None:
                            row_stream.write("NULL")
                        elif field[2]:
                            row_stream.write(f"UNHEX(\"{row[field_idx]}\")")
                        elif isinstance(row[field_idx], str):
                            escaped_value = row[field_idx].replace('\\','\\\\').replace('"','\\"')
                            row_stream.write(f"\"{escaped_value}\"")
                        else:
                            row_stream.write(f"\"{row[field_idx]}\"")
                        first = False
                    row_stream.write(")")

                    row_str = row_stream.getvalue()
                    if packet_length + len(row_str) > max_packet_size:
                        stream.write(";\n")
                        insert_str = "INSERT INTO `{}` ({}) VALUES ".format(table, ",".join(f[1] for f in fields))
                        packet_length = len(insert_str)
                        stream.write(insert_str)
                        if not first_row:
                            row_str = row_str[1:]
                    
                    stream.write(row_str)
                    packet_length += len(row_str)
                    first_row = False

                    row = c.fetchone()
                    row_index += 1

                if not empty_table:
                    stream.write(";\n")

                stream.write(f"/*!40000 ALTER TABLE `{table}` ENABLE KEYS */;\n"+
                         "UNLOCK TABLES;\n\n")

            stream.write("/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;\n"+
                         "/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;\n"+
                         "/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;\n"+
                         "/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;\n"+
                         "/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;\n"+
                         "/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;\n"+
                         "/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;\n\n"+
                         f"-- Dump completed on {datetime.datetime.strftime(datetime.datetime.now(), FORMAT_DB_DATETIME)}\n")

            self._close_cursor(c)
        except:
            traceback.print_exc()
        finally:
            self._close_connection(conn)