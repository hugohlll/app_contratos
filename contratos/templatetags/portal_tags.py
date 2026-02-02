from django import template
from contratos.utils import is_admin as utils_is_admin

register = template.Library()

@register.filter
def is_admin(user):
    return utils_is_admin(user)
