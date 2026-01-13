from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError

class FacilityReportWizard(models.TransientModel):
    _name = 'facility.report.wizard'
    _description = 'Facility Report Wizard with Date Range'

    facility_id = fields.Many2one('facilities.facility', string='Facility', required=True)
    date_from = fields.Date('Date From', required=True, default=lambda self: (datetime.now() - timedelta(days=30)).date())
    date_to = fields.Date('Date To', required=True, default=lambda self: datetime.now().date())
    
    @api.onchange('date_from', 'date_to')
    def _onchange_dates(self):
        """Validate date range"""
        if self.date_from and self.date_to and self.date_from > self.date_to:
            return {
                'warning': {
                    'title': _('Invalid Date Range'),
                    'message': _('Start date must be before or equal to end date.')
                }
            }

    def action_generate_facility_report(self):
        """Generate facility report with date range filtering"""
        # Validate date range
        if self.date_from > self.date_to:
            raise UserError(_("Start date must be before or equal to end date."))
        
        # Store the wizard data in context for the report
        return {
            'type': 'ir.actions.report',
            'report_type': 'qweb-pdf',
            'report_name': 'fm.facility_workorder_report',
            'data': {
                'facility_id': self.facility_id.id,
                'date_from': self.date_from,
                'date_to': self.date_to,
                'wizard_id': self.id,
            }
        }