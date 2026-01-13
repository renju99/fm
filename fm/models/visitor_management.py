# -*- coding: utf-8 -*-
"""Visitor Management Module for Facilities Management.

This module provides comprehensive visitor tracking and management functionality
including visitor registration, check-in/out, access control, and security.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class VisitorManagement(models.Model):
    """Model for managing visitors to facilities."""

    _name = 'visitor.management'
    _description = 'Visitor Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'visit_date desc, id desc'
    _rec_name = 'visitor_name'

    # Sequence and Reference
    visitor_number = fields.Char(
        string='Visitor Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
        help="Unique visitor registration number"
    )
    
    # Visitor Information
    visitor_name = fields.Char(
        string='Visitor Name',
        required=True,
        tracking=True,
        help="Full name of the visitor"
    )
    
    visitor_email = fields.Char(
        string='Email',
        help="Email address of the visitor"
    )
    
    visitor_phone = fields.Char(
        string='Phone',
        required=True,
        help="Contact phone number"
    )
    
    visitor_company = fields.Char(
        string='Company/Organization',
        help="Company or organization the visitor represents"
    )
    
    visitor_id_type = fields.Selection([
        ('national_id', 'National ID'),
        ('passport', 'Passport'),
        ('drivers_license', 'Driver\'s License'),
        ('employee_id', 'Employee ID'),
        ('other', 'Other'),
    ], string='ID Type', help="Type of identification document")
    
    visitor_id_number = fields.Char(
        string='ID Number',
        help="Identification document number"
    )
    
    visitor_photo = fields.Binary(
        string='Visitor Photo',
        attachment=True,
        help="Photo of the visitor for security"
    )
    
    # Visit Details
    visit_date = fields.Datetime(
        string='Visit Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help="Date and time of visit"
    )
    
    visit_purpose = fields.Selection([
        ('meeting', 'Business Meeting'),
        ('delivery', 'Delivery'),
        ('maintenance', 'Maintenance'),
        ('contractor', 'Contractor Work'),
        ('interview', 'Interview'),
        ('personal', 'Personal Visit'),
        ('event', 'Event/Function'),
        ('official', 'Official Business'),
        ('other', 'Other'),
    ], string='Purpose of Visit',
        required=True,
        default='meeting',
        help="Reason for the visit"
    )
    
    visit_description = fields.Text(
        string='Visit Description',
        help="Detailed description of visit purpose"
    )
    
    # Host Information
    host_id = fields.Many2one(
        'res.partner',
        string='Host/Contact Person',
        required=True,
        tracking=True,
        help="Person being visited"
    )
    
    host_phone = fields.Char(
        string='Host Phone',
        related='host_id.phone',
        readonly=True
    )
    
    host_email = fields.Char(
        string='Host Email',
        related='host_id.email',
        readonly=True
    )
    
    host_notified = fields.Boolean(
        string='Host Notified',
        default=False,
        help="Whether the host has been notified of visitor arrival"
    )
    
    host_approval = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
    ], string='Host Approval',
        default='pending',
        tracking=True,
        help="Host approval status"
    )
    
    # Location Information
    facility_id = fields.Many2one(
        'facilities.facility',
        string='Facility',
        required=True,
        tracking=True,
        help="Facility being visited"
    )
    
    building_id = fields.Many2one(
        'facilities.building',
        string='Building',
        tracking=True,
        help="Building to visit"
    )
    
    floor_id = fields.Many2one(
        'facilities.floor',
        string='Floor',
        help="Floor number"
    )
    
    room_id = fields.Many2one(
        'facilities.room',
        string='Room/Office',
        help="Specific room or office to visit"
    )
    
    # Check-in/out Information
    check_in_time = fields.Datetime(
        string='Check-in Time',
        readonly=True,
        tracking=True,
        help="Actual check-in time"
    )
    
    check_out_time = fields.Datetime(
        string='Check-out Time',
        readonly=True,
        tracking=True,
        help="Actual check-out time"
    )
    
    checked_in_by_id = fields.Many2one(
        'res.users',
        string='Checked-in By',
        readonly=True,
        help="Security/staff member who checked in the visitor"
    )
    
    checked_out_by_id = fields.Many2one(
        'res.users',
        string='Checked-out By',
        readonly=True,
        help="Security/staff member who checked out the visitor"
    )
    
    duration = fields.Float(
        string='Visit Duration (Hours)',
        compute='_compute_duration',
        store=True,
        help="Duration of visit in hours"
    )
    
    # Access Control
    visitor_badge_number = fields.Char(
        string='Badge Number',
        readonly=True,
        help="Temporary badge number issued to visitor"
    )
    
    access_card_number = fields.Char(
        string='Access Card Number',
        help="Temporary access card number"
    )
    
    access_areas = fields.Text(
        string='Authorized Areas',
        help="Areas the visitor is authorized to access"
    )
    
    escort_required = fields.Boolean(
        string='Escort Required',
        default=False,
        help="Visitor must be escorted at all times"
    )
    
    escort_id = fields.Many2one(
        'res.users',
        string='Escort',
        help="Staff member escorting the visitor"
    )
    
    # Vehicle Information
    has_vehicle = fields.Boolean(
        string='Has Vehicle',
        default=False,
        help="Visitor arrived with a vehicle"
    )
    
    vehicle_type = fields.Selection([
        ('car', 'Car'),
        ('motorcycle', 'Motorcycle'),
        ('van', 'Van'),
        ('truck', 'Truck'),
        ('bicycle', 'Bicycle'),
        ('other', 'Other'),
    ], string='Vehicle Type')
    
    vehicle_registration = fields.Char(
        string='Vehicle Registration',
        help="Vehicle license plate number"
    )
    
    parking_spot = fields.Char(
        string='Parking Spot',
        help="Assigned parking location"
    )
    
    # Assets/Equipment
    has_equipment = fields.Boolean(
        string='Carrying Equipment',
        default=False,
        help="Visitor is carrying equipment or tools"
    )
    
    equipment_description = fields.Text(
        string='Equipment Description',
        help="Description of equipment brought by visitor"
    )
    
    equipment_checked = fields.Boolean(
        string='Equipment Checked',
        default=False,
        help="Equipment has been inspected by security"
    )
    
    # Status
    state = fields.Selection([
        ('pre_registered', 'Pre-registered'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
        ('denied', 'Access Denied'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ], string='Status',
        default='pre_registered',
        required=True,
        tracking=True,
        help="Current status of the visit"
    )
    
    # Security and Compliance
    security_clearance = fields.Selection([
        ('none', 'None Required'),
        ('basic', 'Basic'),
        ('standard', 'Standard'),
        ('high', 'High Security'),
        ('restricted', 'Restricted Area'),
    ], string='Security Clearance Level',
        default='basic',
        help="Required security clearance level"
    )
    
    nda_signed = fields.Boolean(
        string='NDA Signed',
        default=False,
        help="Non-disclosure agreement signed"
    )
    
    safety_briefing = fields.Boolean(
        string='Safety Briefing Completed',
        default=False,
        help="Safety and security briefing completed"
    )
    
    temperature_check = fields.Float(
        string='Temperature (°C)',
        help="Body temperature check (health screening)"
    )
    
    health_declaration = fields.Boolean(
        string='Health Declaration Completed',
        default=False,
        help="Health declaration form completed"
    )
    
    # QR Code for check-in
    qr_code = fields.Binary(
        string='QR Code',
        compute='_compute_qr_code',
        store=True,
        attachment=True,
        help="QR code for quick check-in"
    )
    
    # Notes
    notes = fields.Text(
        string='Internal Notes',
        help="Internal notes about the visitor"
    )
    
    security_notes = fields.Text(
        string='Security Notes',
        help="Security-related notes and observations"
    )
    
    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    @api.model
    def create(self, vals):
        """Override create to generate visitor number sequence."""
        if vals.get('visitor_number', _('New')) == _('New'):
            vals['visitor_number'] = self.env['ir.sequence'].next_by_code(
                'visitor.management'
            ) or _('New')
        return super(VisitorManagement, self).create(vals)

    @api.depends('check_in_time', 'check_out_time')
    def _compute_duration(self):
        """Compute visit duration in hours."""
        for record in self:
            if record.check_in_time and record.check_out_time:
                delta = record.check_out_time - record.check_in_time
                record.duration = delta.total_seconds() / 3600.0
            else:
                record.duration = 0.0

    @api.depends('visitor_number')
    def _compute_qr_code(self):
        """Generate QR code for visitor check-in."""
        try:
            import qrcode
            import base64
            from io import BytesIO
        except ImportError:
            _logger.warning("QR code library not available")
            for record in self:
                record.qr_code = False
            return
        
        for record in self:
            if record.visitor_number and record.visitor_number != _('New'):
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(record.visitor_number)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                record.qr_code = base64.b64encode(buffer.getvalue())
            else:
                record.qr_code = False

    @api.onchange('facility_id')
    def _onchange_facility_id(self):
        """Reset building when facility changes."""
        if self.facility_id:
            self.building_id = False
            self.floor_id = False
            self.room_id = False

    @api.onchange('building_id')
    def _onchange_building_id(self):
        """Reset floor and room when building changes."""
        if self.building_id:
            self.floor_id = False
            self.room_id = False

    @api.onchange('floor_id')
    def _onchange_floor_id(self):
        """Reset room when floor changes."""
        if self.floor_id:
            self.room_id = False

    @api.constrains('check_in_time', 'check_out_time')
    def _check_times(self):
        """Validate check-in and check-out times."""
        for record in self:
            if record.check_in_time and record.check_out_time:
                if record.check_out_time < record.check_in_time:
                    raise ValidationError(_(
                        "Check-out time cannot be before check-in time!"
                    ))

    def action_request_approval(self):
        """Request approval from host."""
        for record in self:
            if record.state != 'pre_registered':
                raise UserError(_(
                    "Can only request approval for pre-registered visitors!"
                ))
            
            # Send notification to host
            template = self.env.ref(
                'fm.email_template_visitor_approval_request',
                raise_if_not_found=False
            )
            if template:
                template.send_mail(record.id, force_send=True)
            
            record.write({
                'state': 'pending_approval',
                'host_notified': True,
            })
            
            record.message_post(
                body=_("Approval request sent to host %s") % record.host_id.name,
                subject=_("Approval Requested")
            )

    def action_approve_visit(self):
        """Approve visitor access."""
        for record in self:
            if record.state not in ['pre_registered', 'pending_approval']:
                raise UserError(_(
                    "Can only approve pre-registered or pending visitors!"
                ))
            
            record.write({
                'state': 'approved',
                'host_approval': 'approved',
            })
            
            # Send approval notification to visitor
            if record.visitor_email:
                template = self.env.ref(
                    'fm.email_template_visitor_approved',
                    raise_if_not_found=False
                )
                if template:
                    template.send_mail(record.id, force_send=True)
            
            record.message_post(
                body=_("Visit approved by %s") % self.env.user.name,
                subject=_("Visit Approved")
            )

    def action_deny_visit(self):
        """Open wizard to deny visitor access."""
        self.ensure_one()
        if self.state == 'checked_in':
            raise UserError(_(
                "Cannot deny access for visitor who is already checked in!"
            ))
        
        return {
            'name': _('Deny Visitor Access'),
            'type': 'ir.actions.act_window',
            'res_model': 'visitor.deny.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_visitor_id': self.id,
            }
        }

    def action_check_in(self):
        """Check in visitor."""
        for record in self:
            if record.state != 'approved':
                raise UserError(_(
                    "Can only check in approved visitors!"
                ))
            
            # Assign badge number if not already assigned
            if not record.visitor_badge_number:
                badge_number = self.env['ir.sequence'].next_by_code(
                    'visitor.badge'
                ) or 'BADGE-%s' % record.id
                record.visitor_badge_number = badge_number
            
            record.write({
                'state': 'checked_in',
                'check_in_time': fields.Datetime.now(),
                'checked_in_by_id': self.env.user.id,
            })
            
            record.message_post(
                body=_(
                    "Visitor checked in at %s by %s. Badge: %s"
                ) % (
                    record.check_in_time.strftime('%Y-%m-%d %H:%M:%S'),
                    self.env.user.name,
                    record.visitor_badge_number
                ),
                subject=_("Visitor Checked In")
            )

    def action_check_out(self):
        """Check out visitor."""
        for record in self:
            if record.state != 'checked_in':
                raise UserError(_(
                    "Can only check out visitors who are checked in!"
                ))
            
            record.write({
                'state': 'checked_out',
                'check_out_time': fields.Datetime.now(),
                'checked_out_by_id': self.env.user.id,
            })
            
            record.message_post(
                body=_(
                    "Visitor checked out at %s by %s. "
                    "Duration: %.2f hours"
                ) % (
                    record.check_out_time.strftime('%Y-%m-%d %H:%M:%S'),
                    self.env.user.name,
                    record.duration
                ),
                subject=_("Visitor Checked Out")
            )

    def action_cancel_visit(self):
        """Cancel scheduled visit."""
        for record in self:
            if record.state in ['checked_in', 'checked_out']:
                raise UserError(_(
                    "Cannot cancel a visit that has already started or completed!"
                ))
            
            record.write({'state': 'cancelled'})
            record.message_post(
                body=_("Visit cancelled by %s") % self.env.user.name,
                subject=_("Visit Cancelled")
            )

    def action_mark_no_show(self):
        """Mark visitor as no-show."""
        for record in self:
            if record.state not in ['approved', 'pending_approval']:
                raise UserError(_(
                    "Can only mark approved or pending visitors as no-show!"
                ))
            
            record.write({'state': 'no_show'})
            record.message_post(
                body=_("Visitor marked as no-show by %s") % self.env.user.name,
                subject=_("No Show")
            )

    @api.model
    def _cron_check_no_shows(self):
        """Cron job to automatically mark visitors as no-show."""
        # Find approved visitors whose visit date was more than 2 hours ago
        cutoff_time = datetime.now() - timedelta(hours=2)
        no_show_visitors = self.search([
            ('state', '=', 'approved'),
            ('visit_date', '<', cutoff_time),
            ('check_in_time', '=', False),
        ])
        
        for visitor in no_show_visitors:
            visitor.action_mark_no_show()
        
        _logger.info(
            "Marked %d visitors as no-show",
            len(no_show_visitors)
        )

    def name_get(self):
        """Custom name_get to show visitor number and name."""
        result = []
        for record in self:
            name = "%s - %s" % (
                record.visitor_number,
                record.visitor_name
            )
            result.append((record.id, name))
        return result










