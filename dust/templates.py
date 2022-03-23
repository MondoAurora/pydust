import traceback
from jinja2 import Template

from dust import Datatypes, ValueTypes, Operation, MetaProps, FieldProps
from dust.entity import Store, Entity

UNIT_TEMLATES = "templates"
UNIT_TEMLATES_META = "templates_meta"

class TemplateMeta(MetaProps):
    name = (Datatypes.STRING, ValueTypes.SINGLE, 1, 2)
    text = (Datatypes.STRING, ValueTypes.MAP, 2, 3)

class TemplateTypes(FieldProps):
    template = (UNIT_TEMLATES_META, TemplateMeta, 1)

Store.create_unit(UNIT_TEMLATES)
Store.load_types_from_enum(TemplateTypes)

def create_template(name, text):
	template = Store.access(Operation.GET, None, UNIT_TEMLATES, None, TemplateTypes.template)
	template.access(Operation.SET, name, TemplateMeta.name)
	template.access(Operation.SET, text, TemplateMeta.text)
	return template

def render_template(template, **kwargs):
	try: 
		template = Template(template.access(Operation.GET, None, TemplateMeta.text))
		return template.render(**kwargs)
	except:
		traceback.print_exc()


