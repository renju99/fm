# models/__post_init__.py
from odoo import api, SUPERUSER_ID, fields


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Maintain existing technician assignment
    env['facilities.workorder'].search([]).write({
        'technician_id': env.ref('base.user_admin').employee_id.id
    })





