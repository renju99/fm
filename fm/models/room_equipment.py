from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class FacilitiesRoomEquipment(models.Model):
    _name = 'facilities.room.equipment'
    _description = 'Room Equipment'
    _order = 'name'

    name = fields.Char('Equipment Name', required=True)
    equipment_type = fields.Selection([
        ('av', 'Audio/Visual'),
        ('computing', 'Computing'),
        ('furniture', 'Furniture'),
        ('communication', 'Communication'),
        ('safety', 'Safety'),
        ('other', 'Other'),
    ], string='Equipment Type', required=True, default='other')
    
    description = fields.Html('Description')
    manufacturer = fields.Char('Manufacturer')
    model = fields.Char('Model')
    serial_number = fields.Char('Serial Number')
    
    # Status and availability
    status = fields.Selection([
        ('available', 'Available'),
        ('maintenance', 'Under Maintenance'),
        ('broken', 'Broken'),
        ('retired', 'Retired'),
    ], string='Status', default='available')
    
    # Location
    room_ids = fields.Many2many('facilities.room', string='Available in Rooms')
    is_portable = fields.Boolean('Portable Equipment', default=False, 
                                help="Can be moved between rooms")
    current_location = fields.Many2one('facilities.room', string='Current Location')
    
    # Specifications
    specifications = fields.Html('Technical Specifications')
    capacity = fields.Char('Capacity/Size')
    power_requirements = fields.Char('Power Requirements')
    
    # Maintenance
    last_maintenance = fields.Date('Last Maintenance')
    next_maintenance = fields.Date('Next Maintenance')
    maintenance_notes = fields.Html('Maintenance Notes')
    
    # Usage tracking
    total_bookings = fields.Integer('Total Bookings', compute='_compute_usage_stats', store=True)
    last_used = fields.Datetime('Last Used', compute='_compute_usage_stats', store=True)
    
    # Cost
    purchased_date = fields.Date('Purchase Date', help="Date when the equipment was purchased")
    purchase_cost = fields.Float('Purchase Cost')
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    
    # Images
    image = fields.Binary('Equipment Image')
    image_filename = fields.Char('Image Filename')
    
    # Active flag
    active = fields.Boolean('Active', default=True)

    @api.depends('room_ids')
    def _compute_usage_stats(self):
        for equipment in self:
            bookings = self.env['facilities.space.booking'].search([
                ('required_equipment_ids', 'in', equipment.id),
                ('state', 'in', ['confirmed', 'completed'])
            ])
            
            equipment.total_bookings = len(bookings)
            equipment.last_used = max(bookings.mapped('end_datetime')) if bookings else False

    def action_schedule_maintenance(self):
        """Schedule maintenance for this equipment"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Schedule Equipment Maintenance',
            'res_model': 'facilities.equipment.maintenance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_equipment_id': self.id}
        }

    def action_view_bookings(self):
        """View all bookings that use this equipment"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Bookings using {self.name}',
            'res_model': 'facilities.space.booking',
            'view_mode': 'list,form',
            'domain': [('required_equipment_ids', 'in', self.id)],
            'context': {'search_default_confirmed': 1}
        }

    @api.model
    def send_maintenance_reminders(self):
        """Send maintenance reminders for equipment due for maintenance"""
        from datetime import datetime
        
        equipment_needing_maintenance = self.search([
            ('next_maintenance', '<=', datetime.now() + timedelta(days=7)),
            ('status', '=', 'available'),
            ('active', '=', True)
        ])
        
        for equipment in equipment_needing_maintenance:
            # Create activity for facility manager
            equipment.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=f'Equipment maintenance due: {equipment.name}',
                note=f'Equipment {equipment.name} is due for maintenance on {equipment.next_maintenance}.',
            )

    @api.constrains('status', 'current_location')
    def _check_location_status(self):
        for equipment in self:
            if equipment.status in ['broken', 'maintenance'] and equipment.current_location:
                # Check if there are any confirmed bookings using this equipment
                conflicting_bookings = self.env['facilities.space.booking'].search([
                    ('required_equipment_ids', 'in', equipment.id),
                    ('state', 'in', ['confirmed', 'in_progress']),
                    ('start_datetime', '>', fields.Datetime.now())
                ])
                
                if conflicting_bookings:
                    raise ValidationError(
                        _("Cannot set equipment '%s' to %s status. "
                          "It has upcoming bookings that depend on it.") % 
                        (equipment.name, equipment.status))


class FacilitiesRoom(models.Model):
    _inherit = 'facilities.room'
    
    # Add new fields to room model
    capacity = fields.Integer('Capacity', help="Maximum number of people")
    hourly_rate = fields.Float('Hourly Rate', help="Cost per hour for booking this room")
    equipment_ids = fields.Many2many('facilities.room.equipment', string='Fixed Equipment',
                                   help="Equipment permanently installed in this room")
    
    # Room features
    has_projector = fields.Boolean('Has Projector')
    has_whiteboard = fields.Boolean('Has Whiteboard')
    has_wifi = fields.Boolean('Has WiFi')
    has_ac = fields.Boolean('Has Air Conditioning')
    has_video_conf = fields.Boolean('Has Video Conferencing')
    
    # Accessibility
    wheelchair_accessible = fields.Boolean('Wheelchair Accessible')
    
    # Policies
    booking_policy = fields.Html('Booking Policy')
    cancellation_policy = fields.Html('Cancellation Policy')
    
    # Computed fields
    current_utilization = fields.Float('Current Utilization %', 
                                     compute='_compute_utilization')
    upcoming_bookings = fields.Integer('Upcoming Bookings',
                                     compute='_compute_upcoming_bookings')

    @api.depends('capacity')
    def _compute_utilization(self):
        """Calculate room utilization for current week"""
        for room in self:
            # Get start and end of current week
            today = fields.Date.today()
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            
            # Convert to datetime
            start_datetime = fields.Datetime.from_string(f"{start_week} 00:00:00")
            end_datetime = fields.Datetime.from_string(f"{end_week} 23:59:59")
            
            # Get bookings for this week
            bookings = self.env['facilities.space.booking'].search([
                ('room_id', '=', room.id),
                ('state', 'in', ['confirmed', 'completed']),
                ('start_datetime', '>=', start_datetime),
                ('end_datetime', '<=', end_datetime),
            ])
            
            total_hours = sum(booking.duration_hours for booking in bookings)
            # Assume 8 hours per day, 7 days per week = 56 hours max
            max_hours = 56
            room.current_utilization = (total_hours / max_hours * 100) if max_hours > 0 else 0

    @api.depends()
    def _compute_upcoming_bookings(self):
        """Count upcoming bookings"""
        for room in self:
            upcoming = self.env['facilities.space.booking'].search_count([
                ('room_id', '=', room.id),
                ('state', 'in', ['confirmed', 'pending']),
                ('start_datetime', '>', fields.Datetime.now()),
            ])
            room.upcoming_bookings = upcoming