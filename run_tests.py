import os
import django
from django.conf import settings
from django.test.utils import get_runner

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app_contratos.settings')
django.setup()

TestRunner = get_runner(settings)
test_runner = TestRunner(verbosity=2, interactive=False)
failures = test_runner.run_tests(['contratos.tests.test_envio_prestacao.AlterarStatusAjaxTests'])
import sys
sys.exit(failures)
