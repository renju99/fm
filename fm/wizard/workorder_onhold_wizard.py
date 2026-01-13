# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WorkorderOnholdWizard(models.TransientModel):
    _name = 'workorder.onhold.wizard'
    _description = 'Work Order On-Hold Request Wizard'

    workorder_id = fields.Many2one(
        'facilities.workorder',
        string='Work Order',
        required=True,
        readonly=True
    )
    
    onhold_reason = fields.Selection([
        ('waiting_materials', 'Waiting for Materials'),
        ('waiting_parts', 'Waiting for Parts'),
        ('waiting_tools', 'Waiting for Tools/Equipment'),
        ('waiting_permits', 'Waiting for Permits/Approvals'),
        ('weather_conditions', 'Weather Conditions'),
        ('safety_concerns', 'Safety Concerns'),
        ('resource_unavailable', 'Resource Unavailable'),
        ('technical_issues', 'Technical Issues'),
        ('customer_request', 'Customer Request'),
        ('other', 'Other')
    ], string='Reason for On-Hold', required=True, 
       help='Select the reason for putting this work order on hold')
    
    onhold_comment = fields.Text(
        string='Additional Comments',
        required=True,
        help='Provide detailed explanation for the on-hold request'
    )
    
    estimated_delay_days = fields.Integer(
        string='Estimated Delay (Days)',
        help='How many days do you expect this delay to last?'
    )

    def action_submit_onhold_request(self):
        """Submit the on-hold request to facilities manager"""
        self.ensure_one()
        
        # Update workorder with on-hold request details
        self.workorder_id.write({
            'onhold_reason': self.onhold_reason,
            'onhold_comment': self.onhold_comment,
            'onhold_request_date': fields.Datetime.now(),
            'onhold_approval_state': 'pending'
        })
        
        # Create activity for facilities manager
        facilities_managers = self.env.ref('fm.group_facilities_manager').users
        if facilities_managers:
            self.workorder_id.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=facilities_managers[0].id,
                summary=_('On-Hold Request for Work Order %s') % self.workorder_id.name,
                note=_('Technician has requested to put work order on hold.\n\nReason: %s\nComments: %s\nEstimated delay: %s days') % (
                    dict(self._fields['onhold_reason'].selection).get(self.onhold_reason),
                    self.onhold_comment,
                    self.estimated_delay_days or 'Not specified'
                )
            )
        
        # Post message in workorder chatter
        self.workorder_id.message_post(
            body=_("On-hold request submitted by %s<br/><strong>Reason:</strong> %s<br/><strong>Comments:</strong> %s") % (
                self.env.user.name,
                dict(self._fields['onhold_reason'].selection).get(self.onhold_reason),
                self.onhold_comment
            )
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('On-Hold Request Submitted'),
                'message': _('Your on-hold request has been submitted to the facilities manager for approval.'),
                'type': 'success',
                'sticky': False,
            }
        }
