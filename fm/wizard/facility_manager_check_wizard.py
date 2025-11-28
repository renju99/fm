from odoo import models, fields, api, _
from odoo.exceptions import UserError

class FacilityManagerCheckWizard(models.TransientModel):
    _name = 'facility.manager.check.wizard'
    _description = 'Facility Manager Check Wizard'

    permit_id = fields.Many2one('facilities.workorder.permit', string='Permit', required=True)
    status_info = fields.Text(string='Status Information', readonly=True)
    facility_name = fields.Char(string='Facility Name', readonly=True)
    manager_name = fields.Char(string='Manager Name', readonly=True)
    has_user_account = fields.Boolean(string='Has User Account', readonly=True)
    user_name = fields.Char(string='User Name', readonly=True)
    recommendations = fields.Text(string='Recommendations', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            permit = self.env['facilities.workorder.permit'].browse(self.env.context.get('active_id'))
            if permit:
                res['permit_id'] = permit.id
                # Get status information
                status_info = permit.get_facility_manager_status()
                res['status_info'] = status_info.get('details', '')
                res['facility_name'] = status_info.get('facility_name', '')
                res['manager_name'] = status_info.get('manager_name', '')
                res['has_user_account'] = status_info.get('status') == 'success'
                res['user_name'] = status_info.get('user_name', '')
                
                # Generate recommendations
                recommendations = []
                if status_info.get('status') == 'error':
                    if 'No facility associated' in status_info.get('message', ''):
                        recommendations.append("• Ensure the work order has an asset assigned")
                        recommendations.append("• Ensure the asset is assigned to a facility")
                    elif 'No facility manager assigned' in status_info.get('message', ''):
                        recommendations.append("• Go to the facility and assign a manager")
                        recommendations.append("• Navigate to Facilities > [Facility Name] > Basic Information > Manager")
                    elif 'no user account' in status_info.get('message', ''):
                        recommendations.append("• Ensure the facility manager has a user account")
                        recommendations.append("• Go to Employees > [Manager Name] > HR Settings > User")
                        recommendations.append("• Create a new user account if none exists")
                else:
                    recommendations.append("• Facility manager is properly configured")
                    recommendations.append("• You should be able to send the permit for approval")
                
                res['recommendations'] = '\n'.join(recommendations)
        
        return res

    def action_open_facility(self):
        """Open the facility form to fix manager assignment."""
        self.ensure_one()
        if self.permit_id.workorder_id and self.permit_id.workorder_id.asset_id and self.permit_id.workorder_id.asset_id.facility_id:
            facility = self.permit_id.workorder_id.asset_id.facility_id
            return {
                'type': 'ir.actions.act_window',
                'name': _('Facility'),
                'res_model': 'facilities.facility',
                'res_id': facility.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {'type': 'ir.actions.act_window_close'}

    def action_open_manager(self):
        """Open the employee form to fix user account assignment."""
        self.ensure_one()
        if self.permit_id.workorder_id and self.permit_id.workorder_id.asset_id and self.permit_id.workorder_id.asset_id.facility_id:
            facility = self.permit_id.workorder_id.asset_id.facility_id
            if facility.manager_id:
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Employee'),
                    'res_model': 'hr.employee',
                    'res_id': facility.manager_id.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        return {'type': 'ir.actions.act_window_close'}

    def action_refresh_status(self):
        """Refresh the status information."""
        self.ensure_one()
        # Recompute the default values
        default_values = self.default_get(self._fields.keys())
        for field, value in default_values.items():
            if field in self._fields:
                setattr(self, field, value)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facility Manager Status'),
            'res_model': 'facility.manager.check.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }