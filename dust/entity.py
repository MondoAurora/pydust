import json
import os
import yaml
import traceback
import inspect
from enum import Enum
from collections import namedtuple
from datetime import datetime
from dust import Datatypes, ValueTypes, Operation, MetaProps, FieldProps
from importlib import import_module

_messages_create_message = None

UNIT_ENTITY = "entity"
UNIT_ENTITY_META = "entity_meta"

class UnitMeta(MetaProps):
    name = (Datatypes.STRING, ValueTypes.SINGLE, 1, 5)
    id_cnt = (Datatypes.INT, ValueTypes.SINGLE, 2, 6)
    meta_types = (Datatypes.ENTITY, ValueTypes.SET, 3, 7)

class TypeMeta(MetaProps):
    name = (Datatypes.STRING, ValueTypes.SINGLE, 1, 8)
    fields = (Datatypes.ENTITY, ValueTypes.SET, 2, 9)

class MetaField(MetaProps):
    name = (Datatypes.STRING, ValueTypes.SINGLE, 1, 10)
    global_name = (Datatypes.STRING, ValueTypes.SINGLE, 2, 11)
    order = (Datatypes.INT, ValueTypes.SINGLE, 3, 12)

class EntityBaseMeta(MetaProps):
    unit = (Datatypes.ENTITY, ValueTypes.SINGLE, 1, 13)
    meta_type = (Datatypes.ENTITY, ValueTypes.SINGLE, 2, 14)
    entity_id = (Datatypes.INT, ValueTypes.SINGLE, 3, 15)

class EntityTypes(FieldProps):
    type_meta = (UNIT_ENTITY_META, TypeMeta, 1)
    _entity_base = (UNIT_ENTITY_META, EntityBaseMeta, 2)
    unit = (UNIT_ENTITY_META, UnitMeta, 3)
    meta_field = (UNIT_ENTITY_META, MetaField, 4)


class Store():
    @staticmethod
    def load_unit_types(filenames):
        for filename in filenames:
            with open(filename, "r") as tf:
                loaded__meta_types = yaml.load(tf, Loader=yaml.FullLoader)["types"]

            Store.load_types_from_dict(loaded__meta_types)

    @staticmethod
    def create_unit(unit_name):
        entity_map = globals()["_entity_map"]
        enum_map = globals()["_enum_map"]

        if not unit_name in [UNIT_ENTITY, UNIT_ENTITY_META] and not unit_name in enum_map:
            unit = Store.access(Operation.GET, None, UNIT_ENTITY, None, EntityTypes.unit)
            enum_map[unit_name] = unit
            enum_map[unit] = unit_name
            unit.access(Operation.SET, 0, UnitMeta.id_cnt)
            unit.access(Operation.SET, unit_name, UnitMeta.name)
        
        elif not ( UNIT_ENTITY+":2:"+EntityTypes.unit.name ) in entity_map:
            unit = Store._create_entity(None, 1, None)
            unit.unit = unit
            enum_map[UNIT_ENTITY] = unit
            enum_map[unit] = UNIT_ENTITY

            unit_meta = Store._create_entity(unit, 2, None)
            enum_map[UNIT_ENTITY_META] = unit_meta
            enum_map[unit_meta] = UNIT_ENTITY_META

            cnt = 0
            types = {}
            for entity_type in EntityTypes:
                cnt += 1
                et = Store._create_entity(unit_meta, entity_type.id_value, None)
                enum_map[entity_type] = et
                enum_map[et] = entity_type
                if entity_type.id_value > cnt:
                    cnt = entity_type.id_value

            unit.meta_type = enum_map[EntityTypes.unit]
            unit_meta.meta_type = enum_map[EntityTypes.unit]
            enum_map[EntityTypes.unit].meta_type = enum_map[EntityTypes.type_meta]

            Store._add_entity_to_store(unit)
            Store._add_entity_to_store(unit_meta)

            for entity_type in [EntityTypes.type_meta, EntityTypes.unit, EntityTypes._entity_base, EntityTypes.meta_field]:
                et = enum_map[entity_type]
                et.meta_type = enum_map[EntityTypes.type_meta]
                enum_map[et.global_id()] = entity_type
                Store._add_entity_to_store(et)
                et.access(Operation.SET, entity_type.name, TypeMeta.name)

            unit.access(Operation.SET, 2, UnitMeta.id_cnt)
            unit.access(Operation.SET, UNIT_ENTITY, UnitMeta.name)

            unit_meta.access(Operation.SET, cnt, UnitMeta.id_cnt)
            unit_meta.access(Operation.SET, UNIT_ENTITY_META, UnitMeta.name)

            return unit_meta

        else:
            unit = enum_map[unit_name]

        return unit

    @staticmethod
    def _get_base_fields():
        fields = []
        for base_field in EntityBaseMeta:
            fields.append(Store._global_field_name(UNIT_ENTITY_META, EntityTypes._entity_base.name, base_field.name))

        return tuple(fields)

    @staticmethod
    def _create_entity(unit, entity_id, meta_type):
        enum_map = globals()["_enum_map"]

        if unit and not isinstance(unit, Entity):
            unit = enum_map[unit]
        if meta_type and not isinstance(meta_type, Entity):
            meta_type = enum_map[meta_type]

        e = Entity(unit, entity_id, meta_type)

        if unit and meta_type:
            Store._add_entity_to_store(e)

        return e

    def _add_entity_to_store(e):
        entity_map = globals()["_entity_map"]

        unit_field, meta_type_field, entity_id_field = Store._get_base_fields()

        entity_map[e.global_id()] = ({
            unit_field: e.unit.global_id(), 
            entity_id_field: e.entity_id, 
            meta_type_field: e.meta_type.global_id()
        }, e)


    @staticmethod
    def increment_unit_counter(unit_name):
        unit = globals()["_enum_map"][unit_name]
        return unit.access(Operation.CHANGE, 1, UnitMeta.id_cnt)

    @staticmethod
    def load_types_from_enum(e):
        entity_map = globals()["_entity_map"]
        #meta_ref = globals()["_meta_ref"]
        enum_map = globals()["_enum_map"]
        unit_meta_types = {}
        for meta_type in e:
            for field in meta_type.fields_enum:
                global_name = Store._global_field_name(meta_type.unit_name, meta_type.name, field.name)
                enum_map[global_name] = {"datatype": field.value[0], "valuetype": field.value[1], "id": field.id_value, "order": field.order_value, "_enum": field}
                enum_map[field] = global_name

        for base_field in EntityBaseMeta:
            global_name = Store._global_field_name(base_field.unit, EntityTypes._entity_base, base_field.name)
            enum_map[global_name] = {"datatype": base_field.value[0], "valuetype": base_field.value[1], "id": field.id_value, "order": base_field.order_value, "_enum": base_field}
            enum_map[base_field] = global_name

        for meta_type in e:
            unit = Store.create_unit(meta_type.unit_name)

            if meta_type in enum_map:
                field_meta_type = enum_map[meta_type]
            else:
                cnt = unit.access(Operation.GET, 0, UnitMeta.id_cnt)
                if meta_type.id_value > cnt:
                    unit.access(Operation.SET, meta_type.id_value, UnitMeta.id_cnt)
                field_meta_type = Store.access(Operation.GET, None, meta_type.unit_name, meta_type.id_value, EntityTypes.type_meta)
                field_meta_type.access(Operation.SET, meta_type.name, TypeMeta.name)
                enum_map[meta_type] = field_meta_type
                enum_map[field_meta_type] = meta_type
                enum_map[field_meta_type.global_id()] = meta_type

            field_config = {}

            max_order = 0
            field_entities = []
            max_id_value = 0
            for field in meta_type.fields_enum:
                global_name = Store._global_field_name(meta_type.unit_name, meta_type.name, field.name)

                field_entity = Store.access(Operation.GET, None, meta_type.unit_name, field.id_value, EntityTypes.meta_field)
                field_entity.access(Operation.SET, field.name, MetaField.name)
                field_entity.access(Operation.SET, field.order_value, MetaField.order)
                field_entity.access(Operation.SET, global_name, MetaField.global_name)
                field_entities.append(field_entity)

                if field.id_value > max_id_value:
                    max_id_value = field.id_value


            for field_entity in field_entities:
                field_meta_type.access(Operation.ADD, field_entity, TypeMeta.fields)

            if max_id_value > 0:
                cnt = unit.access(Operation.GET, 0, UnitMeta.id_cnt)
                if max_id_value > cnt:
                    unit.access(Operation.SET, max_id_value, UnitMeta.id_cnt)

            unit_meta_types.setdefault(unit, []).append(field_meta_type)

        for unit, field_meta_types in unit_meta_types.items():
            for field_meta_type in field_meta_types:
                unit.access(Operation.ADD, field_meta_type, UnitMeta.meta_types)
            
    @staticmethod
    def access(operation, value, *path):
        entities = globals()["_entity_map"]
        enum_map = globals()["_enum_map"]

        local_ref = None
        last_obj = None
        remaining_path = None
        idx = 0
        last_global_id = None
        last_entity_path = []

        if len(path) > 0:
            unit, entity_id, meta_type = Entity._resolve_global_id(path[0])
            if entity_id is None:
                # path is done with 3 parts
                if len(path) > 2 and ( path[1] is None or isinstance(path[1], int) ) and isinstance( path[2], FieldProps ):
                    if path[1] is None:
                        entity_id = Store.increment_unit_counter(path[0])
                    else:
                        entity_id = path[1]
                    local_ref = Entity._ref(path[0], entity_id, path[2])
                    idx = 3
            else:
                # found entity id on path[0]
                local_ref = path[0]
                idx = 1

        if idx < len(path):
            remaining_path = path[idx:]
        else:
            remaining_path = []

        #print("Access 1: local_ref={}, path={}".format(local_ref, path))
        if local_ref:
            if not local_ref in entities:
                last_obj = Store._create_entity(path[0], entity_id, path[2])
            else:
                last_obj = entities[local_ref][1]
            last_global_id = last_obj.global_id()

        path_length = len(remaining_path)
        if last_obj and path_length == 0:
            if _messages_create_message:
                _create_message(MessageType.ENTITY_ACCESS, {"path": last_entity_path, "op": operation}, [last_global_id])
            return last_obj
        else:
            rv = None

            if last_obj is None:
                last_obj = [e[1] for e in entities.values()]
                parent = last_obj

            for last_idx in range(path_length):
                key = remaining_path[last_idx]
                #print("{}: Access 2: key={}".format(last_obj, key))

                if last_obj is None:
                    last_obj = Store._access_data_create_container(parent, remaining_path[last_idx - 1], key)
                elif isinstance(last_obj, Entity):
                    last_global_id = last_obj.global_id()
                    last_entity_path = path[last_idx:]

                if isinstance(last_obj, str):
                    unit, entity_id, meta_type = Entity._resolve_global_id(last_obj)
                    if entity_id:
                        parent = entities[last_obj][1]
                    else:
                        parent = last_obj
                else:
                    parent = last_obj

                last_obj = Store._access_data_get_value(parent, key, None)
                last_idx += 1

            if operation == Operation.SET or operation == Operation.ADD or operation == Operation.CHANGE:
                rv = Store._access_data_set_value(parent, remaining_path[last_idx - 1], value, operation)
                if _messages_create_message:
                    _create_message(MessageType.ENTITY_ACCESS, {"path": last_entity_path, "op": operation}, [last_global_id])

            elif operation == Operation.GET:
                if _messages_create_message:
                    _create_message(MessageType.ENTITY_ACCESS, {"path": last_entity_path, "op": operation}, [last_global_id])
                rv = last_obj

            elif operation == Operation.VISIT:
                if _messages_create_message:
                    _create_message(MessageType.ENTITY_ACCESS, {"path": last_entity_path, "op": operation}, [last_global_id])
                rv = last_obj

            return rv


    def _access_data_create_container(obj, field, key):
        if isinstance(obj, Entity):
            entities = globals()["_entity_map"]
            enum_map = globals()["_enum_map"]

            global_field_name = enum_map[field]
            field_config = enum_map[global_field_name]

            e_map = entities[obj.global_id()][0]
            if field_config["valuetype"] == ValueTypes.SET:
                e_map[global_field_name] = set()
            elif field_config["valuetype"] == ValueTypes.LIST:
                e_map[global_field_name] = []
                return e_map[global_name]

    def _access_data_set_value(obj, field, value, operation):
        if isinstance(obj, Entity):
            entities = globals()["_entity_map"]
            enum_map = globals()["_enum_map"]

            e_map = entities[obj.global_id()][0]
            global_field_name = enum_map[field]
            field_config = enum_map[global_field_name]

            e_map = entities[obj.global_id()][0]

            if field.datatype == Datatypes.ENTITY and isinstance(value, Entity):
                if field.valuetype == ValueTypes.LIST:
                    e_map.setdefault(global_field_name, []).append(value.global_id())
                elif field.valuetype == ValueTypes.SET:
                    e_map.setdefault(global_field_name, set()).add(value.global_id())
                else:
                    e_map[global_field_name] = value.global_id()
            else:
                if field.valuetype == ValueTypes.LIST and not isinstance(value, list):
                    e_map.setdefault(global_field_name, []).append(value)
                elif field.valuetype == ValueTypes.SET and not isinstance(value, set):
                    if isinstance(value, list) or isinstance(value, set):
                        e_map.setdefault(global_field_name, set()).update(value)
                    else:
                        e_map.setdefault(global_field_name, set()).add(value)
                else:
                    if operation == Operation.CHANGE:
                        e_map[global_field_name] += value
                        value = e_map[global_field_name]
                    else:
                        e_map[global_field_name] = value

            return value


    def _access_data_get_value(obj, key, default_value):
        entities = globals()["_entity_map"]
        enum_map = globals()["_enum_map"]

        if isinstance(obj, Entity):
            global_name = enum_map[key]
            e_map = entities[obj.global_id()][0]
            if global_name in e_map:
                unit, entity_id, meta_type = Entity._resolve_global_id(e_map[global_name])
                if entity_id:
                    return entities[e_map[global_name]][1]
                else:
                    return e_map[global_name]


        elif isinstance(obj, list):
            if isinstance(key, int) and key < len(obj):
                return obj[key]

        elif isinstance(obj, dict):
            if key in obj:
                return obj[key]

        elif isinstance(obj, set):
            raise Exception("Not possible to request path element on sets.")

        return default_value

    @staticmethod
    def _access(operation, value, *path):
        entities = globals()["_entity_map"]
        enum_map = globals()["_enum_map"]

        if operation == Operation.VISIT:
            if len(path) == 3:
                # Allow range in entity_id ?
                global_id = Entity._ref(path[0], entity_id, path[1].name)
                if global_id in entities:
                    return entities[global_id][1]
                else:
                    return value
            elif len(path) < 3:
                def unit_filter(e, *path):
                    return e.unit.access(Operation.GET, None, UnitMeta.name) == path[0]

                def type_filter(e, *path):
                    return e.unit.access(Operation.GET, None, UnitMeta.name) == path[0] and \
                           e.meta_type.access(Operation.GET, None, TypeMeta.name) == path[1].name
                
                entity_filter = None
                if len(path) == 2:
                    entity_filter = type_filter
                if len(path) == 1:
                    entity_filter = unit_filter

                array = []
                for e_map_tuple in filter(entity_filter, entities.values()):
                    array.append(e_map_tuple[1])

                return array


        entity_id = path[1]
        if path[1] == None:
            entity_id = Store.increment_unit_counter(path[0])

        global_id = Entity._ref(path[0], entity_id, path[2])
        if not global_id in entities:
            Store._create_entity(path[0], entity_id, path[2])
        if operation == Operation.GET:
            if len(path) == 3:
                return entities[global_id][1]
            else:
                global_field_name = Store._global_field_name(path[0], path[2].name, path[3].name)
                value = entities[global_id][0][global_field_name]

                field_config = Store._get_field_config(path[0], path[2], path[3])
                if field_config["datatype"] == Datatypes.ENTITY:
                    if value in entities:
                        return entities[value][1]
                    else:
                        parts = value.split(":")
                        return Store._create_entity(parts[0], int(parts[1]), parts[2])
                else:
                    return value

        elif operation == Operation.SET:
            global_field_name = Store._global_field_name(path[0], path[2].name, path[3].name)
            if isinstance(value, Entity):
                entities[global_id][0][global_field_name] = value.global_id()
            else:
                entities[global_id][0][global_field_name] = value

        elif operation == Operation.CHANGE:
            global_field_name = Store._global_field_name(path[0], path[2].name, path[3].name)
            entities[global_id][0][global_field_name] += value
            return entities[global_id][0][global_field_name]

        elif operation == Operation.ADD:
            global_field_name = Store._global_field_name(path[0], path[2].name, path[3].name)
            field_config = Store._get_field_config(path[0], path[2], path[3])
            if isinstance(value, Entity):
                if field_config["valuetype"] == ValueTypes.SET:
                    if not global_field_name in entities[global_id][0]:
                        entities[global_id][0][global_field_name] = []
                    if not value.global_id() in entities[global_id][0][global_field_name]:
                        entities[global_id][0][global_field_name].append(value.global_id())
                    #entities[global_id][0].setdefault(global_field_name, set()).add(value.global_id())
                else:
                    entities[global_id][0].setdefault(global_field_name, []).append(value.global_id())
            else:
                if field_config["valuetype"] == ValueTypes.SET:
                    if not global_field_name in entities[global_id][0]:
                        entities[global_id][0][global_field_name] = []
                    if not value in entities[global_id][0][global_field_name]:
                        entities[global_id][0][global_field_name].append(value)
                    #entities[global_id][0].setdefault(global_field_name, set()).add(value)
                else:
                    entities[global_id][0].setdefault(global_field_name, []).append(value)

    @staticmethod
    def _get_field_config(unit_name, meta_type, field):
        enum_map = globals()["_enum_map"]
        if isinstance(meta_type, Enum) and meta_type in [EntityTypes.type_meta, EntityTypes.meta_field]:
            return enum_map[UNIT_ENTITY_META+":"+meta_type.name+":"+field.name]
        elif isinstance(meta_type, str) and meta_type in [EntityTypes.type_meta.name, EntityTypes.meta_field.name]:
            return enum_map[UNIT_ENTITY_META+":"+meta_type+":"+field]
        elif isinstance(meta_type, Enum) and isinstance(field, Enum):
            return enum_map[unit_name+":"+meta_type.name+":"+field.name]
        else:
            return enum_map[unit_name+":"+meta_type+":"+field]

    @staticmethod
    def _global_field_name(unit, meta_type, field_name):
        if isinstance(unit, Entity) and isinstance(meta_type, Entity):
            return  enum_map[unit]+":"+enum_map[meta_type].name+":"+field_name
        else:
            return "{}:{}:{}".format(unit, meta_type, field_name)

    @staticmethod
    def to_json(*path):
        entities = Store.access(Operation.VISIT, None, *path)
        json_array = []
        for e in entities:
            json_array.append(e.to_json())
        return json_array

    @staticmethod
    def from_json(objects):
        entities = []
        for e_map in objects:
            entities.append(Entity.from_json(e_map))

        return entities


class Entity():
    def __init__(self, unit, entity_id, meta_type):
        self.unit = unit
        self.entity_id = entity_id
        self.meta_type = meta_type

    def access(self, operation, value, *path):
        enum_map = globals()["_enum_map"]
        return Store.access(operation, value, enum_map[self.unit], self.entity_id, enum_map[self.meta_type], *path)

    @staticmethod
    def _ref(unit, entity_id, meta_type):
        enum_map = globals()["_enum_map"]
        if isinstance(unit, Entity) and isinstance(meta_type, Entity):
            return  enum_map[unit]+":"+str(entity_id)+":"+enum_map[meta_type].name
        else:
            return  unit+":"+str(entity_id)+":"+meta_type.name

    def global_id(self):
        return  Entity._ref(self.unit, self.entity_id, self.meta_type)

    def _resolve_global_id(value):
        if isinstance(value, str):
            enum_map = globals()["_enum_map"]
            parts = value.split(":")
            entity_id = None
            try:
                entity_id = int(parts[1])
            except:
                pass
            if len(parts) == 3 and not entity_id is None:
                entity = globals()["_entity_map"].get(value, (None, None))[1]
                unit = enum_map.get(parts[0], None)
                if unit and isinstance(unit, Entity) and enum_map[unit.meta_type] == EntityTypes.unit:
                    if entity.meta_type and isinstance(entity.meta_type, Entity) and entity.meta_type in enum_map:
                        return (unit, entity_id, entity.meta_type)

        return (None, None, None)

    def get_meta_type_enum(self):
        enum_map = globals()["_enum_map"]
        return _enum_map[self.meta_type]

    def __to_json(self, json_map):
        entity_value_map = globals()["_entity_map"][self.global_id()][0]
        enum_map = globals()["_enum_map"]

        for field, value in entity_value_map.items():
            parts = field.split(":")
            field_config = Store._get_field_config(parts[0], parts[1], parts[2])

            if field_config["valuetype"] in [ValueTypes.SET, ValueTypes.LIST] and ( isinstance(value, list) or isinstance(value, set) ):
                json_map[field] = []
                for element in value:
                    json_map[field].append(element)
            else:
                json_map[field] = value

    def to_json(self):
        json_map = {}
        self.__to_json(json_map)
        return json_map

    @staticmethod
    def from_json(e_map):
        entity_map = globals()["_entity_map"]
        enum_map = globals()["_enum_map"]

        unit_field, meta_type_field, entity_id_field = Store._get_base_fields()

        unit_parts = e_map[unit_field].split(":")

        unit = Store.access(Operation.GET, None, UNIT_ENTITY, int(unit_parts[1]), EntityTypes.unit)
        unit_name = unit.access(Operation.GET, None, UnitMeta.name)
        meta_type = enum_map[e_map[meta_type_field]]

        e = Store.access(Operation.GET, None, unit_name, int(e_map[entity_id_field]), meta_type)

        for field, value in e_map.items():
            if not field in [unit_field, meta_type_field, entity_id_field]:
                field_parts = field.split(":")
                field_config = Store._get_field_config(field_parts[0], field_parts[1], field_parts[2])
                if field_config["valuetype"] in [ValueTypes.SET, ValueTypes.LIST] and ( isinstance(value, list) or isinstance(value, set) ):
                    for element in value:
                        e.access(Operation.ADD, element, field_config["_enum"])
                else:
                    e.access(Operation.SET, value, field_config["_enum"])

        return e

_entity_map = {}
_enum_map = {}

Store.load_types_from_enum(EntityTypes)
_messages_module = import_module("dust.messages")
MessageType = getattr(_messages_module, "MessageType")
MessageTypes = getattr(_messages_module, "MessageTypes")
_messages_create_message = getattr(_messages_module, "create_message")
_UNIT_MESSAGE = _messages_module.UNIT_MESSAGES

def _create_message(message_type, message_params, entities):
    if _messages_create_message and message_params["op"] in [Operation.ADD, Operation.SET, Operation.DEL, Operation.CHANGE]:
        params = {}
        if entities and not entities[0] is None:
            enum_map = globals()["_enum_map"]
            unit, _, _ = Entity._resolve_global_id(entities[0])
            unit_name = enum_map[unit]
            if unit_name in [_UNIT_MESSAGE, UNIT_ENTITY] or unit_name.endswith("_meta"):
                return

        params["op"] = message_params["op"].name
        params["path"] = []
        for path_element in message_params["path"]:
            if isinstance(path_element, Enum):
                params["path"].append(path_element.name)
            elif isinstance(path_element, Entity):
                params["path"].append(path_element.global_id())

        _messages_create_message(message_type, params, entities)

if __name__ == '__main__':
    print(json.dumps(_entity_map, indent=4))
    print(str(_meta_ref))
