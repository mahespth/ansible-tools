
import jinja2
jinja2.__version__

from jinja2 import Template
template = Template('''\
 {% set ns = namespace(items=0) %}
 {% for line in range(3) %}
     {% set ns.items = ns.items + line %}
 {% endfor %}

 {{ ns.items }}
 ''')
template.render().strip()
