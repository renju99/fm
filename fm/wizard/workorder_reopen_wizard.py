# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class WorkOrderReopenWizard(models.TransientModel):
    _name = 'workorder.reopen.wizard'
    _description = 'Work Order Reopen Wizard'

    workorder_id = fields.Many2one('facilities.workorder', string='Work Order', required=True)
    reason = fields.Text(string='Reason for Reopening', required=True, 
                        help="Please provide a detailed reason for reopening this work order.")
    affect_first_time_fix = fields.Boolean(
        string='Affects First Time Fix Rate', 
        default=True,
        help="Check this if reopening this work order affects the first time fix rate calculation."
    )
    reopen_date = fields.Datetime(string='Reopen Date', default=fields.Datetime.now, required=True)

    @api.model
    def default_get(self, fields_list):
        """Set default values for the wizard"""
        res = super().default_get(fields_list)
        if 'workorder_id' in fields_list and self.env.context.get('active_id'):
            res['workorder_id'] = self.env.context['active_id']
        return res

    def action_reopen_workorder(self):
        """Reopen the work order with the provided reason"""
        self.ensure_one()
        
        if not self.workorder_id:
            raise UserError(_("No work order selected."))
        
        if self.workorder_id.state != 'completed':
            raise UserError(_("Only completed work orders can be reopened."))
        
        if not self.reason.strip():
            raise ValidationError(_("Please provide a reason for reopening the work order."))
        
        # Check if user has permission to reopen (facilities manager)
        if not self.env.user.has_group('facilities_management.group_facilities_manager'):
            raise UserError(_("Only facilities managers can reopen work orders."))
        
        # Update work order state
        self.workorder_id.state = 'in_progress'
        
        # Update first time fix status if needed
        if self.affect_first_time_fix:
            self.workorder_id.first_time_fix = False
        
        # Create log entry
        log_message = _("Work order reopened by %s on %s.\nReason: %s") % (
            self.env.user.name,
            self.reopen_date.strftime('%Y-%m-%d %H:%M:%S'),
            self.reason
        )
        
        if self.affect_first_time_fix:
            log_message += _("\nNote: This reopening affects the first time fix rate.")
        
        self.workorder_id.message_post(
            body=log_message,
            message_type='notification'
        )
        
        # Create activity for the technician
        if self.workorder_id.technician_id and self.workorder_id.technician_id.user_id:
            self.workorder_id.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Work Order Reopened'),
                note=_('Work order %s has been reopened. Reason: %s') % (
                    self.workorder_id.name, self.reason
                ),
                user_id=self.workorder_id.technician_id.user_id.id,
                date_deadline=fields.Date.today()
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Work Order Reopened'),
                'message': _('Work order has been successfully reopened and is now in progress.'),
                'type': 'success',
            }
        }
