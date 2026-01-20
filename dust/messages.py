import sys
import logging
import threading
import traceback
import time
from queue import Queue, Empty

from enum import Enum
from dust import Datatypes, ValueTypes, Operation, MetaProps, FieldProps
from dust.entity import Store, Entity, get_unit_deps_tuple

#PATH = "/var/local/beaconing/messagequeue"

UNIT_MESSAGES = "messages"
UNIT_MESSAGES_META = "messages_meta"
UNIT_ID = 5
UNIT_META_ID = 6

def get_unit_dependencies():
    return [
        get_unit_deps_tuple("dust.events", "UNIT_EVENTS", "EventTypes")
    ]

class MessageType(Enum):
    ENTITY_ACCESS = 0

class MessageMeta(MetaProps):
    message_type = (Datatypes.STRING, ValueTypes.SINGLE, 1, 100)
    message_params = (Datatypes.JSON, ValueTypes.MAP, 2, 101)
    datetime = (Datatypes.ENTITY, ValueTypes.SINGLE, 3, 102)
    entities = (Datatypes.ENTITY, ValueTypes.SET, 4, 103)
    callback_name = (Datatypes.STRING, ValueTypes.SINGLE, 1, 104)

class MessageQueueInfoMeta(MetaProps):
    chunksize = (Datatypes.INT, ValueTypes.SINGLE, 1, 200)
    size = (Datatypes.INT, ValueTypes.SINGLE, 2, 201)
    tail = (Datatypes.INT, ValueTypes.LIST, 3, 202)
    head = (Datatypes.INT, ValueTypes.LIST, 4, 203)

class MessageTypes(FieldProps):
    message = (UNIT_MESSAGES_META, MessageMeta, 1)
    message_queue_info = (UNIT_MESSAGES_META, MessageQueueInfoMeta, 2)

Store.create_unit(UNIT_MESSAGES, UNIT_ID)
Store.load_types_from_enum(MessageTypes, UNIT_META_ID)

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
_log.addHandler(handler)

def register_listener(name, entity_filter, cb):
    _listeners[name] = (entity_filter, cb)


def unregister_listener(name):
    if name in _listeners:
        del _listeners[name]

_stop = False
_queue = Queue()
_listeners = {}

def signal_finish():
    global _stop

    _queue.join()
    _stop = True
    _queue.put(Store.access(Operation.GET, None, UNIT_MESSAGES, None, MessageTypes.message))

def start_queue_processor(queue, log):
    global _stop

    while True:
        try:
            entity = _queue.get(block=False)
            if entity == None:
                time.sleep(0.5)
            else:
                _log.debug("Processing item: {}".format(entity.global_id()))
                try:
                    _listeners[entity.access(Operation.GET, None, MessageMeta.callback_name)][1](
                        entity.access(Operation.GET, None, MessageMeta.message_type),
                        entity.access(Operation.GET, None, MessageMeta.message_params),
                        entity.access(Operation.GET, None, MessageMeta.entities)
                    )
                except KeyError:
                    if entity.access(Operation.GET, None, MessageMeta.callback_name):
                        _log.error("Invalid callback registered: {}".format(entity.access(Operation.GET, None, MessageMeta.callback_name)))
            if _stop:
                break

        except Empty:
            time.sleep(0.5)
            if _stop:
                break
        except KeyboardInterrupt:
            _log.warning("Keyboard interrupt received")
            break
        except:
            traceback.print_exc()
        finally:
            _queue.task_done()

def create_message(message_type, message_params, entities):
    for callback_name, listener in _listeners.items():
        entity_filter, cb = listener
        if entity_filter(message_type, message_params, entities):
            message = Store.access(Operation.GET, None, UNIT_MESSAGES, None, MessageTypes.message)
            message.access(Operation.SET, message_type.name, MessageMeta.message_type)
            message.access(Operation.SET, callback_name, MessageMeta.callback_name)
            if message_params:
                message.access(Operation.SET, message_params, MessageMeta.message_params)
            if entities:
                for e in entities:
                    if e:
                        message.access(Operation.ADD, entities, MessageMeta.entities)
            _queue.put(message)


_queue_processor = threading.Thread(target=start_queue_processor, args=(_queue, _log, ), daemon=False)
_queue_processor.start()