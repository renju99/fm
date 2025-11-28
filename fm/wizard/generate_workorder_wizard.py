# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class GenerateWorkorderWizard(models.TransientModel):
    _name = 'generate.workorder.wizard'
    _description = 'Generate Work Order Wizard'

    schedule_id = fields.Many2one('asset.maintenance.schedule', string='Maintenance Schedule', required=True)
    lead_days = fields.Integer(
        string='Lead Days',
        default=30,
        required=True,
        help="Number of days ahead from current date to generate work orders"
    )
    overwrite_existing = fields.Boolean(
        string='Overwrite Existing Work Orders',
        default=False,
        help="If checked, existing work orders in the date range will be overwritten"
    )

    def action_generate_workorders(self):
        """Generate work orders with the specified lead days."""
        self.ensure_one()
        
        if self.lead_days <= 0:
            raise UserError(_("Lead days must be greater than 0."))
        
        # Call the schedule's generation method with lead days
        return self.schedule_id.action_generate_workorders_with_lead_days(
            lead_days=self.lead_days,
            overwrite_existing=self.overwrite_existing
        )
