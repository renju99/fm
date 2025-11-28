# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CreateMaintenanceScheduleWizard(models.TransientModel):
    _name = 'create.maintenance.schedule.wizard'
    _description = 'Create Maintenance Schedule Wizard'

    maintenance_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection'),
    ], string='Maintenance Type', required=True, default='preventive')

    interval_number = fields.Integer(string='Repeat Every', default=1, required=True)
    interval_type = fields.Selection([
        ('daily', 'Day(s)'),
        ('weekly', 'Week(s)'),
        ('monthly', 'Month(s)'),
        ('quarterly', 'Quarter(s)'),
        ('yearly', 'Year(s)'),
    ], string='Recurrence', default='monthly', required=True)

    asset_ids = fields.Many2many('facilities.asset', string='Assets', required=True)
    create_for_all = fields.Boolean(string='Create for all assets without schedules', default=False)

    @api.onchange('create_for_all')
    def _onchange_create_for_all(self):
        if self.create_for_all:
            # Find all assets without maintenance schedules of the selected type
            assets_without_schedules = self.env['facilities.asset'].search([
                ('active', '=', True),
                ('state', 'in', ['active', 'draft'])
            ]).filtered(lambda a: not a.maintenance_ids.filtered(
                lambda m: m.maintenance_type == self.maintenance_type and m.active
            ))
            self.asset_ids = assets_without_schedules
        else:
            self.asset_ids = False

    def action_create_schedules(self):
        """Create maintenance schedules for selected assets."""
        if not self.asset_ids:
            raise UserError(_("Please select assets to create maintenance schedules for."))

        created_count = 0
        for asset in self.asset_ids:
            try:
                # Check if asset already has a schedule of this type
                existing_schedule = asset.maintenance_ids.filtered(
                    lambda m: m.maintenance_type == self.maintenance_type and m.active
                )
                
                if not existing_schedule:
                    self.env['asset.maintenance.schedule'].create({
                        'name': f'{self.interval_type.title()} {self.maintenance_type.title()} - {asset.name}',
                        'asset_id': asset.id,
                        'maintenance_type': self.maintenance_type,
                        'interval_number': self.interval_number,
                        'interval_type': self.interval_type,
                        'status': 'planned',
                        'active': True,
                    })
                    created_count += 1
                    asset.message_post(
                        body=f"Maintenance schedule created: {self.interval_type.title()} {self.maintenance_type.title()}"
                    )
            except Exception as e:
                raise UserError(_("Failed to create maintenance schedule for asset %s: %s") % (asset.name, str(e)))


        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Maintenance Schedules Created'),
                'message': _('%d maintenance schedules created successfully.') % created_count,
                'type': 'success',
                'sticky': False,
            }
        }