from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FacilitiesBookingRejectWizard(models.TransientModel):
    _name = 'facilities.booking.reject.wizard'
    _description = 'Booking Rejection Wizard'

    booking_id = fields.Many2one('facilities.space.booking', string='Booking', required=True)
    rejection_reason = fields.Html('Rejection Reason', required=True)
    notify_user = fields.Boolean('Notify User', default=True,
                                help="Send email notification to the booking user")
    
    def action_reject_booking(self):
        """Reject the booking with the provided reason"""
        self.ensure_one()
        
        if not self.rejection_reason:
            raise UserError(_("Please provide a reason for rejection."))
        
        # Update booking
        self.booking_id.write({
            'state': 'cancelled',
            'rejection_reason': self.rejection_reason,
        })
        
        # Post message to chatter
        self.booking_id.message_post(
            body=_("Booking rejected by %s. Reason: %s") % (self.env.user.name, self.rejection_reason),
            message_type='comment'
        )
        
        # Send notification email if requested
        if self.notify_user:
            template = self.env.ref('fm.mail_template_space_booking_rejected', 
                                  raise_if_not_found=False)
            if template:
                template.send_mail(self.booking_id.id, force_send=True)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Booking Rejected'),
                'message': _('The booking has been rejected and the user has been notified.'),
                'type': 'success',
                'sticky': False,
            }
        }