import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solicitacao.settings')
django.setup()

from django.template.loader import get_template
from django.template.exceptions import TemplateSyntaxError

template_dir = 'contratos/templates'
for root, dirs, files in os.walk(template_dir):
    for f in files:
        if f.endswith('.html'):
            path = os.path.join(root, f)
            # convert to template name
            template_name = path.replace(template_dir + '/', '', 1)
            # Try loading
            try:
                get_template(template_name)
            except TemplateSyntaxError as e:
                print(f"Error in {template_name}: {e}")
            except Exception as e:
                pass
