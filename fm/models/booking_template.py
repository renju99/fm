from odoo import models, fields, api, _


class FacilitiesBookingTemplate(models.Model):
    _name = 'facilities.booking.template'
    _description = 'Booking Template'
    _order = 'name'

    name = fields.Char('Template Name', required=True)
    booking_type = fields.Selection([
        ('meeting', 'Meeting'),
        ('event', 'Event'),
        ('training', 'Training'),
        ('workshop', 'Workshop'),
        ('conference', 'Conference'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    ], string='Booking Type', default='meeting', required=True)
    
    purpose = fields.Char('Purpose')
    attendees = fields.Integer('Number of Attendees')
    notes = fields.Html('Notes')
    department_id = fields.Many2one('hr.department', string='Department')
    
    # Equipment and capacity
    required_equipment_ids = fields.Many2many('facilities.room.equipment', string='Required Equipment', default=lambda self: [(6, 0, [])])
    required_capacity = fields.Integer('Required Capacity', default=1)
    
    # Settings
    is_external_guest = fields.Boolean('Has External Guests')
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], default='normal', string='Priority')
    
    notification_settings = fields.Html('Notification Settings', default='{"email": true, "sms": false, "app": true}')
    auto_check_in = fields.Boolean('Auto Check-in', default=False)
    auto_check_out = fields.Boolean('Auto Check-out', default=False)
    
    # Usage tracking
    usage_count = fields.Integer('Usage Count', default=0)
    last_used = fields.Datetime('Last Used')
    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)
    
    # Active flag
    active = fields.Boolean('Active', default=True)

    def action_use_template(self):
        """Create a new booking from this template"""
        self.ensure_one()
        
        # Update usage statistics
        self.write({
            'usage_count': self.usage_count + 1,
            'last_used': fields.Datetime.now()
        })
        
        booking_data = {
            'template_id': self.id,
            'booking_type': self.booking_type,
            'purpose': self.purpose,
            'attendees': self.attendees,
            'notes': self.notes,
            'department_id': self.department_id.id if self.department_id else False,
            'required_equipment_ids': [(6, 0, self.required_equipment_ids.ids)],
            'required_capacity': self.required_capacity,
            'is_external_guest': self.is_external_guest,
            'priority': self.priority,
            'notification_settings': self.notification_settings,
            'auto_check_in': self.auto_check_in,
            'auto_check_out': self.auto_check_out,
        }
        
        booking = self.env['facilities.space.booking'].create(booking_data)
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Booking from Template',
            'res_model': 'facilities.space.booking',
            'res_id': booking.id,
            'view_mode': 'form',
            'target': 'current',
        }