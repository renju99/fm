# Python
from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)

class MaintenanceReport(models.AbstractModel):
    _name = 'report.fm.report_asset_maintenance_template'
    _description = 'Asset Maintenance Report Template'

    @api.model
    def _get_report_values(self, docids, data=None):
        assets = self.env['facilities.asset'].browse(docids)
        return {
            'docs': assets,
        }