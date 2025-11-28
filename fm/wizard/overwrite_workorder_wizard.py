# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AssetMaintenanceScheduleOverwriteWizard(models.TransientModel):
    _name = 'asset.maintenance.schedule.overwrite.wizard'
    _description = 'Overwrite Work Order Wizard'

    schedule_id = fields.Many2one('asset.maintenance.schedule', string='Schedule', required=True)
    existing_workorder_id = fields.Many2one('facilities.workorder', string='Existing Work Order', required=True)
    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True)
    
    action = fields.Selection([
        ('overwrite', 'Overwrite Existing Work Order'),
        ('skip', 'Skip - Keep Existing Work Order'),
        ('create_new', 'Create New Work Order Anyway'),
    ], string='Action', default='overwrite', required=True)
    
    message = fields.Text(string='Message', readonly=True)

    @api.model
    def default_get(self, fields_list):
        """Set default message based on existing work order."""
        defaults = super().default_get(fields_list)
        
        if 'existing_workorder_id' in defaults and defaults.get('existing_workorder_id'):
            existing_wo = self.env['facilities.workorder'].browse(defaults['existing_workorder_id'])
            defaults['message'] = _(
                "A work order already exists for this schedule and asset:\n"
                "Work Order: %s\n"
                "Status: %s\n"
                "Created: %s\n\n"
                "What would you like to do?"
            ) % (
                existing_wo.name,
                existing_wo.state,
                existing_wo.create_date.strftime('%Y-%m-%d %H:%M') if existing_wo.create_date else 'N/A'
            )
        
        return defaults

    def action_confirm(self):
        """Execute the selected action."""
        self.ensure_one()
        
        if self.action == 'overwrite':
            # Cancel the existing work order and create a new one
            self.existing_workorder_id.action_cancel()
            self.existing_workorder_id.message_post(
                body=_("Work order cancelled due to overwrite from schedule: %s") % self.schedule_id.name
            )
            
            # Create new work order
            new_workorder = self.schedule_id._create_workorder_with_tasks(self.schedule_id, self.asset_id)
            
            return {
                'type': 'ir.actions.act_window',
                'name': 'New Work Order',
                'res_model': 'facilities.workorder',
                'view_mode': 'form',
                'res_id': new_workorder.id,
                'target': 'current',
            }
            
        elif self.action == 'create_new':
            # Create new work order without cancelling existing one
            new_workorder = self.schedule_id._create_workorder_with_tasks(self.schedule_id, self.asset_id)
            
            return {
                'type': 'ir.actions.act_window',
                'name': 'New Work Order',
                'res_model': 'facilities.workorder',
                'view_mode': 'form',
                'res_id': new_workorder.id,
                'target': 'current',
            }
            
        elif self.action == 'skip':
            # Just show the existing work order
            return {
                'type': 'ir.actions.act_window',
                'name': 'Existing Work Order',
                'res_model': 'facilities.workorder',
                'view_mode': 'form',
                'res_id': self.existing_workorder_id.id,
                'target': 'current',
            }
        
        return {'type': 'ir.actions.act_window_close'}
