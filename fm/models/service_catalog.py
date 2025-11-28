# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ServiceCatalog(models.Model):
    _name = 'facilities.service.catalog'
    _description = 'Service Catalog'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    _rec_name = 'display_name'

    name = fields.Char(
        string='Service Name',
        required=True,
        tracking=True,
        help='Name of the service offered'
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    code = fields.Char(
        string='Service Code',
        required=True,
        tracking=True,
        help='Unique code for the service'
    )
    
    description = fields.Html(
        string='Description',
        required=True,
        tracking=True,
        help='Detailed description of the service'
    )
    
    short_description = fields.Text(
        string='Short Description',
        help='Brief description shown in catalog lists'
    )
    
    category = fields.Selection([
        ('maintenance', 'Maintenance Services'),
        ('it_support', 'IT Support Services'),
        ('facility_service', 'Facility Services'),
        ('hr_request', 'Human Resources Services'),
        ('procurement', 'Procurement/Retail Services'),
        ('travel', 'Travel Services'),
        ('event_planning', 'Event Planning Services'),
        ('access_request', 'Access Services'),
        ('training', 'Training Services'),
        ('other', 'Other Services')
    ], string='Category', required=True, tracking=True)
    
    service_type = fields.Selection(
        related='category',
        string='Service Type',
        store=True
    )
    
    # Hierarchy
    parent_id = fields.Many2one(
        'facilities.service.catalog',
        string='Parent Service',
        index=True,
        ondelete='cascade',
        tracking=True
    )
    
    child_ids = fields.One2many(
        'facilities.service.catalog',
        'parent_id',
        string='Sub-Services'
    )
    
    # Availability and Access
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    
    available = fields.Boolean(
        string='Available for Request',
        default=True,
        tracking=True,
        help='Whether this service can be requested by users'
    )
    
    # Access Control
    user_group_ids = fields.Many2many(
        'res.groups',
        string='Authorized Groups',
        help='Groups that can request this service. If empty, all users can request.'
    )
    
    department_ids = fields.Many2many(
        'hr.department',
        string='Authorized Departments',
        help='Departments that can request this service'
    )
    
    # SLA and Processing
    default_sla_id = fields.Many2one(
        'facilities.sla',
        string='Default SLA',
        help='Default Service Level Agreement for requests of this service'
    )
    
    default_team_id = fields.Many2one(
        'maintenance.team',
        string='Default Team',
        help='Default team to handle requests for this service'
    )
    
    default_priority = fields.Selection([
        ('0', 'Very Low'),
        ('1', 'Low'),
        ('2', 'Normal'),
        ('3', 'High'),
        ('4', 'Very High'),
        ('5', 'Critical')
    ], string='Default Priority', default='2')
    
    approval_required = fields.Boolean(
        string='Approval Required',
        default=False,
        tracking=True,
        help='Whether requests for this service require approval'
    )
    
    default_approver_id = fields.Many2one(
        'res.users',
        string='Default Approver',
        help='Default approver for requests of this service'
    )
    
    # Cost Information
    estimated_cost = fields.Monetary(
        string='Estimated Cost',
        currency_field='currency_id',
        help='Estimated cost for this service'
    )
    
    cost_center = fields.Char(
        string='Cost Center',
        help='Cost center for this service'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # Request Form Configuration
    custom_form_view_id = fields.Many2one(
        'ir.ui.view',
        string='Custom Form View',
        domain=[('type', '=', 'form'), ('model', '=', 'facilities.service.request')],
        help='Custom form view for requests of this service'
    )
    
    required_fields = fields.Char(
        string='Required Fields',
        help='Comma-separated list of required field names for this service'
    )
    
    # Instructions and Help
    instructions = fields.Html(
        string='Request Instructions',
        help='Instructions shown to users when requesting this service'
    )
    
    help_document_ids = fields.Many2many(
        'facilities.service.document',
        string='Help Documents',
        help='Documents that provide help for this service'
    )
    
    faq = fields.Html(
        string='Frequently Asked Questions',
        help='FAQ for this service'
    )
    
    # Contact Information
    contact_ids = fields.Many2many(
        'facilities.service.contact',
        string='Service Contacts',
        help='Contacts for this service'
    )
    
    # Statistics
    request_count = fields.Integer(
        string='Request Count',
        compute='_compute_request_count',
        help='Number of requests for this service'
    )
    
    avg_resolution_time = fields.Float(
        string='Average Resolution Time (Hours)',
        compute='_compute_avg_resolution_time',
        help='Average time to resolve requests for this service'
    )
    
    # Display and Ordering
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order in which services are displayed'
    )
    
    icon = fields.Char(
        string='Icon',
        help='Font Awesome icon class (e.g., fa-wrench)'
    )
    
    color = fields.Integer(
        string='Color',
        help='Color for display in kanban view'
    )
    
    image = fields.Image(
        string='Service Image',
        max_width=1024,
        max_height=1024
    )
    
    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for record in self:
            if record.code and record.name:
                record.display_name = f"[{record.code}] {record.name}"
            else:
                record.display_name = record.name or record.code or _('New Service')

    def _compute_request_count(self):
        for record in self:
            record.request_count = self.env['facilities.service.request'].search_count([
                ('category_id', '=', record.id)
            ])

    def _compute_avg_resolution_time(self):
        for record in self:
            requests = self.env['facilities.service.request'].search([
                ('category_id', '=', record.id),
                ('state', 'in', ['resolved', 'closed']),
                ('resolution_date', '!=', False)
            ])
            
            if requests:
                total_time = sum([
                    (req.resolution_date - req.request_date).total_seconds() / 3600
                    for req in requests
                ])
                record.avg_resolution_time = total_time / len(requests)
            else:
                record.avg_resolution_time = 0.0

    @api.constrains('code')
    def _check_code_unique(self):
        for record in self:
            if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('Service code must be unique.'))

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive service hierarchies.'))

    def action_create_request(self):
        """Create a new service request for this catalog item"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.service.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_category_id': self.id,
                'default_service_type': self.category,
                'default_priority': self.default_priority,
                'default_sla_id': self.default_sla_id.id if self.default_sla_id else False,
                'default_team_id': self.default_team_id.id if self.default_team_id else False,
                'default_approval_required': self.approval_required,
                'default_approver_id': self.default_approver_id.id if self.default_approver_id else False,
                'default_estimated_cost': self.estimated_cost,
            },
            'view_id': self.custom_form_view_id.id if self.custom_form_view_id else False,
        }

    def action_view_requests(self):
        """View all requests for this service"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.service.request',
            'domain': [('category_id', '=', self.id)],
            'view_mode': 'list,form,kanban',
            'name': _('Requests for %s') % self.name,
            'target': 'current',
        }

    def check_user_access(self, user=None):
        """Check if user can request this service"""
        self.ensure_one()
        
        if not user:
            user = self.env.user
        
        # Check if service is available
        if not self.available or not self.active:
            return False
        
        # Check group access
        if self.user_group_ids:
            user_groups = user.groups_id
            if not any(group in user_groups for group in self.user_group_ids):
                return False
        
        # Check department access
        if self.department_ids:
            user_departments = user.employee_id.department_id
            if user_departments not in self.department_ids:
                return False
        
        return True

    @api.model
    def get_available_services(self, category=None, user=None):
        """Get services available to a user"""
        if not user:
            user = self.env.user
        
        domain = [('available', '=', True), ('active', '=', True)]
        if category:
            domain.append(('category', '=', category))
        
        services = self.search(domain)
        return services.filtered(lambda s: s.check_user_access(user))

    def name_get(self):
        """Custom name_get to show code and name"""
        result = []
        for record in self:
            if record.code and record.name:
                name = f"[{record.code}] {record.name}"
            else:
                name = record.name or record.code or _('New Service')
            result.append((record.id, name))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        """Enhanced search to include code, name, and description"""
        args = args or []
        domain = []
        if name:
            domain = ['|', '|', '|',
                     ('name', operator, name),
                     ('code', operator, name),
                     ('description', operator, name),
                     ('short_description', operator, name)]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)

