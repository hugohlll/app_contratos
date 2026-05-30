import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

# Add current path to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# Redirect stdout and stderr to a file
log_file = open('test_output.log', 'w')
sys.stdout = log_file
sys.stderr = log_file

print("Running test suite: contratos.tests.test_apontamentos")
TestRunner = get_runner(settings)
test_runner = TestRunner(verbosity=2, interactive=False)
failures = test_runner.run_tests(['contratos.tests.test_apontamentos'])

print(f"Total failures: {failures}")
log_file.close()
sys.exit(failures)
