# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WorkOrderStartPermitWizard(models.TransientModel):
    _name = 'facilities.workorder.start.permit.wizard'
    _description = 'Work Order Start Permit Wizard'

    workorder_id = fields.Many2one(
        'facilities.workorder',
        string='Work Order',
        required=True,
        readonly=True
    )
    
    requires_permit = fields.Boolean(
        string='Does this work order require a permit?',
        default=False,
        help='Select if this work order requires a work permit before starting'
    )
    
    permit_type = fields.Selection([
        ('electrical', 'Electrical'),
        ('mechanical', 'Mechanical'),
        ('hotwork', 'Hot Work'),
        ('confined', 'Confined Space'),
        ('general', 'General')
    ], string='Permit Type', help='Type of permit required')
    
    permit_notes = fields.Text(
        string='Permit Notes',
        help='Additional notes about the permit requirements'
    )
    
    def action_proceed_without_permit(self):
        """Proceed to start work order without permit"""
        self.ensure_one()
        
        # Update work order to indicate no permit required
        self.workorder_id.write({
            'permit_required': False,
            'permit_notes': 'No permit required - confirmed by user',
            'state': 'in_progress',
            'actual_start_date': fields.Datetime.now(),
        })
        
        # Post message to work order
        self.workorder_id.message_post(
            body=_('Work order started without permit - confirmed by %s') % self.env.user.name,
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Work Order Started'),
                'message': _('Work order has been started without permit requirement.'),
                'type': 'success',
            }
        }
    
    def action_create_permit_and_start(self):
        """Create permit and proceed to permit creation screen"""
        self.ensure_one()
        
        if not self.permit_type:
            raise UserError(_('Please select a permit type before proceeding.'))
        
        # Update work order to indicate permit is required
        self.workorder_id.write({
            'permit_required': True,
            'permit_notes': self.permit_notes or f'Permit type: {dict(self._fields["permit_type"].selection)[self.permit_type]}',
        })
        
        # Create a new permit
        permit_vals = {
            'name': f'Permit for {self.workorder_id.name}',
            'workorder_id': self.workorder_id.id,
            'permit_type': self.permit_type,
            'notes': self.permit_notes or f'Permit required for work order {self.workorder_id.name}',
            'requested_by_id': self.env.user.id,
            'issued_date': fields.Date.today(),
            'status': 'requested',
        }
        
        # Create the permit
        try:
            permit = self.env['facilities.workorder.permit'].create(permit_vals)
        except Exception as e:
            # Log the error and provide user feedback
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error('Failed to create permit for work order %s: %s', self.workorder_id.name, str(e))
            
            # Fallback: just update work order and show message
            self.workorder_id.message_post(
                body=_('Permit creation failed: %s - %s. Error: %s') % (
                    dict(self._fields["permit_type"].selection)[self.permit_type],
                    self.permit_notes or 'No additional notes',
                    str(e)
                ),
                message_type='notification'
            )
            
            raise UserError(_('Failed to create permit: %s\n\nPlease check the system configuration or contact your administrator.') % str(e))
        
        # Post message to work order
        self.workorder_id.message_post(
            body=_('Permit created: %s - %s') % (permit.name, permit.permit_type),
            message_type='notification'
        )
        
        # Return action to open permit form
        return {
            'name': _('Work Order Permit'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder.permit',
            'res_id': permit.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_workorder_id': self.workorder_id.id,
                'default_permit_type': self.permit_type,
            }
        }
