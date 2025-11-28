# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ServiceContact(models.Model):
    _name = 'facilities.service.contact'
    _description = 'Service Contact Directory'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Contact Name',
        required=True,
        tracking=True,
        help='Name of the contact person or team'
    )
    
    email = fields.Char(
        string='Email Address',
        tracking=True,
        help='Email address for contact'
    )
    
    phone = fields.Char(
        string='Phone Number',
        tracking=True,
        help='Phone number for contact'
    )
    
    mobile = fields.Char(
        string='Mobile Number',
        tracking=True,
        help='Mobile phone number for contact'
    )
    
    description = fields.Html(
        string='Description',
        help='Additional information or details about the contact'
    )
    
    category = fields.Selection([
        ('technical', 'Technical Support'),
        ('administrative', 'Administrative'),
        ('emergency', 'Emergency Contact'),
        ('vendor', 'Vendor/Supplier'),
        ('internal', 'Internal Team'),
        ('external', 'External Service'),
        ('management', 'Management'),
        ('other', 'Other')
    ], string='Category', required=True, default='internal', tracking=True)
    
    # Service Areas
    service_area_ids = fields.Many2many(
        'facilities.service.catalog',
        string='Service Areas',
        help='Service areas this contact handles'
    )
    
    specialization = fields.Char(
        string='Specialization',
        help='Area of specialization or expertise'
    )
    
    # Availability
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    
    available_hours = fields.Char(
        string='Available Hours',
        help='Hours when contact is available (e.g., 9 AM - 5 PM)'
    )
    
    timezone = fields.Selection(
        lambda self: self._get_timezone_selection(),
        string='Timezone',
        default=lambda self: self._get_default_timezone()
    )
    
    # Access Control - who can see this contact
    audience_ids = fields.Many2many(
        'res.groups',
        string='Audience',
        help='User groups who can access this contact. If empty, all users can access.'
    )
    
    department_ids = fields.Many2many(
        'hr.department',
        string='Departments',
        help='Departments that can access this contact'
    )
    
    # Location
    office_location = fields.Char(
        string='Office Location',
        help='Physical office location'
    )
    
    building_id = fields.Many2one(
        'facilities.building',
        string='Building',
        help='Building where contact is located'
    )
    
    floor_id = fields.Many2one(
        'facilities.floor',
        string='Floor',
        help='Floor where contact is located'
    )
    
    room_id = fields.Many2one(
        'facilities.room',
        string='Room',
        help='Room where contact is located'
    )
    
    # Priority and Escalation
    priority_level = fields.Selection([
        ('1', 'Level 1 - First Contact'),
        ('2', 'Level 2 - Escalation'),
        ('3', 'Level 3 - Management'),
        ('4', 'Level 4 - Emergency')
    ], string='Priority Level', default='1')
    
    escalation_contact_id = fields.Many2one(
        'facilities.service.contact',
        string='Escalation Contact',
        help='Contact to escalate to if this contact is unavailable'
    )
    
    # User Association
    user_id = fields.Many2one(
        'res.users',
        string='Related User',
        help='Odoo user associated with this contact'
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Related Partner',
        help='Partner/Vendor associated with this contact'
    )
    
    # External Service Information
    service_provider = fields.Char(
        string='Service Provider',
        help='Name of external service provider'
    )
    
    contract_number = fields.Char(
        string='Contract Number',
        help='Contract or service agreement number'
    )
    
    service_url = fields.Char(
        string='Service URL',
        help='URL for online service or portal'
    )
    
    # Additional Information
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this contact'
    )
    
    image = fields.Image(
        string='Photo',
        max_width=1024,
        max_height=1024
    )
    
    # Statistics
    request_count = fields.Integer(
        string='Service Requests Handled',
        compute='_compute_request_count',
        help='Number of service requests handled by this contact'
    )
    
    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    def _get_timezone_selection(self):
        """Get timezone selection list"""
        import pytz
        timezones = [(tz, tz) for tz in pytz.common_timezones]
        return timezones

    def _get_default_timezone(self):
        """Get default timezone"""
        return self.env.user.tz or 'UTC'

    def _compute_request_count(self):
        """Compute number of service requests handled"""
        for record in self:
            # This would need to be implemented based on how contacts are linked to requests
            # For now, we'll set it to 0
            record.request_count = 0

    @api.constrains('email')
    def _check_email(self):
        """Validate email format"""
        for record in self:
            if record.email:
                import re
                if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', record.email):
                    raise ValidationError(_('Please enter a valid email address.'))

    @api.onchange('user_id')
    def _onchange_user_id(self):
        """Auto-populate fields when user is selected"""
        if self.user_id:
            self.name = self.user_id.name
            self.email = self.user_id.email
            self.phone = self.user_id.phone
            self.mobile = self.user_id.mobile
            if self.user_id.employee_id:
                self.department_ids = [(6, 0, [self.user_id.employee_id.department_id.id])] if self.user_id.employee_id.department_id else False

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Auto-populate fields when partner is selected"""
        if self.partner_id:
            if not self.name:
                self.name = self.partner_id.name
            if not self.email:
                self.email = self.partner_id.email
            if not self.phone:
                self.phone = self.partner_id.phone
            if not self.mobile:
                self.mobile = self.partner_id.mobile

    def check_user_access(self, user=None):
        """Check if user can access this contact"""
        self.ensure_one()
        
        if not user:
            user = self.env.user
        
        # Check if contact is active
        if not self.active:
            return False
        
        # Check group access
        if self.audience_ids:
            user_groups = user.groups_id
            if not any(group in user_groups for group in self.audience_ids):
                return False
        
        # Check department access
        if self.department_ids:
            user_departments = user.employee_id.department_id
            if user_departments not in self.department_ids:
                return False
        
        return True

    @api.model
    def get_available_contacts(self, category=None, service_area=None, user=None):
        """Get contacts available to a user"""
        if not user:
            user = self.env.user
        
        domain = [('active', '=', True)]
        if category:
            domain.append(('category', '=', category))
        if service_area:
            domain.append(('service_area_ids', 'in', [service_area]))
        
        contacts = self.search(domain)
        return contacts.filtered(lambda c: c.check_user_access(user))

    def action_send_email(self):
        """Send email to this contact"""
        self.ensure_one()
        if not self.email:
            raise ValidationError(_('No email address configured for this contact.'))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_ids': [(6, 0, [self.partner_id.id])] if self.partner_id else [],
                'default_email_to': self.email,
                'default_subject': _('Service Request Inquiry'),
            }
        }

    def action_call_contact(self):
        """Initiate call to this contact"""
        self.ensure_one()
        phone = self.mobile or self.phone
        if not phone:
            raise ValidationError(_('No phone number configured for this contact.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'tel:{phone}',
            'target': 'self'
        }

    def action_view_location(self):
        """View contact location"""
        self.ensure_one()
        if self.room_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'facilities.room',
                'res_id': self.room_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.building_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'facilities.building',
                'res_id': self.building_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def name_get(self):
        """Custom name_get"""
        result = []
        for record in self:
            name = record.name
            if record.specialization:
                name += f" ({record.specialization})"
            result.append((record.id, name))
        return result

