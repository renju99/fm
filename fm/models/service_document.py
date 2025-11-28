# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ServiceDocument(models.Model):
    _name = 'facilities.service.document'
    _description = 'Service Help Center Documents'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(
        string='Document Title',
        required=True,
        tracking=True,
        help='Title of the document'
    )
    
    description = fields.Text(
        string='Description',
        help='Brief description or summary of the document'
    )
    
    content = fields.Html(
        string='Content',
        help='Document content (for text-based documents)'
    )
    
    document_type = fields.Selection([
        ('user_guide', 'User Guide'),
        ('faq', 'FAQ'),
        ('procedure', 'Procedure'),
        ('policy', 'Policy'),
        ('troubleshooting', 'Troubleshooting'),
        ('training_material', 'Training Material'),
        ('form_template', 'Form Template'),
        ('contact_info', 'Contact Information'),
        ('other', 'Other')
    ], string='Document Type', required=True, default='user_guide', tracking=True)
    
    category = fields.Selection([
        ('maintenance', 'Maintenance'),
        ('it_support', 'IT Support'),
        ('facility_service', 'Facility Services'),
        ('hr_request', 'Human Resources'),
        ('procurement', 'Procurement/Retail'),
        ('travel', 'Travel'),
        ('event_planning', 'Event Planning'),
        ('access_request', 'Access Management'),
        ('training', 'Training'),
        ('general', 'General'),
        ('other', 'Other')
    ], string='Category', required=True, default='general', tracking=True)
    
    # File Attachment
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Document File',
        help='Attached document file (PDF, DOC, etc.)'
    )
    
    file_name = fields.Char(
        related='attachment_id.name',
        string='File Name',
        readonly=True
    )
    
    file_size = fields.Integer(
        related='attachment_id.file_size',
        string='File Size',
        readonly=True
    )
    
    file_type = fields.Char(
        related='attachment_id.mimetype',
        string='File Type',
        readonly=True
    )
    
    # Access Control
    audience_ids = fields.Many2many(
        'res.groups',
        string='Audience',
        help='User groups who can access this document. If empty, all users can access.'
    )
    
    department_ids = fields.Many2many(
        'hr.department',
        string='Departments',
        help='Departments that can access this document'
    )
    
    # Service Association
    service_ids = fields.Many2many(
        'facilities.service.catalog',
        string='Related Services',
        help='Services this document is related to'
    )
    
    # Metadata
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    
    published = fields.Boolean(
        string='Published',
        default=True,
        tracking=True,
        help='Whether this document is published and visible to users'
    )
    
    version = fields.Char(
        string='Version',
        default='1.0',
        help='Document version number'
    )
    
    author_id = fields.Many2one(
        'res.users',
        string='Author',
        default=lambda self: self.env.user,
        required=True,
        tracking=True
    )
    
    reviewer_id = fields.Many2one(
        'res.users',
        string='Reviewer',
        tracking=True,
        help='User who reviewed and approved this document'
    )
    
    review_date = fields.Date(
        string='Review Date',
        tracking=True,
        help='Date when document was last reviewed'
    )
    
    next_review_date = fields.Date(
        string='Next Review Date',
        tracking=True,
        help='Date when document should be reviewed next'
    )
    
    # Usage Statistics
    view_count = fields.Integer(
        string='View Count',
        default=0,
        help='Number of times this document has been viewed'
    )
    
    download_count = fields.Integer(
        string='Download Count',
        default=0,
        help='Number of times this document has been downloaded'
    )
    
    last_viewed = fields.Datetime(
        string='Last Viewed',
        readonly=True
    )
    
    # Tags and Keywords
    tag_ids = fields.Many2many(
        'facilities.service.document.tag',
        string='Tags',
        help='Tags for categorizing and searching documents'
    )
    
    keywords = fields.Char(
        string='Keywords',
        help='Keywords for searching this document'
    )
    
    # Display Settings
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order in which documents are displayed'
    )
    
    featured = fields.Boolean(
        string='Featured',
        default=False,
        help='Whether this document is featured in the help center'
    )
    
    icon = fields.Char(
        string='Icon',
        help='Font Awesome icon class (e.g., fa-file-text)'
    )
    
    color = fields.Integer(
        string='Color',
        help='Color for display in kanban view'
    )
    
    # External Links
    external_url = fields.Char(
        string='External URL',
        help='Link to external document or resource'
    )
    
    video_url = fields.Char(
        string='Video URL',
        help='Link to instructional video'
    )
    
    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    
    # Computed Fields
    is_file_document = fields.Boolean(
        string='Is File Document',
        compute='_compute_is_file_document'
    )
    
    display_type = fields.Char(
        string='Display Type',
        compute='_compute_display_type'
    )

    @api.depends('attachment_id', 'content', 'external_url')
    def _compute_is_file_document(self):
        for record in self:
            record.is_file_document = bool(record.attachment_id)

    @api.depends('attachment_id', 'content', 'external_url', 'video_url')
    def _compute_display_type(self):
        for record in self:
            if record.video_url:
                record.display_type = 'video'
            elif record.external_url:
                record.display_type = 'link'
            elif record.attachment_id:
                record.display_type = 'file'
            elif record.content:
                record.display_type = 'content'
            else:
                record.display_type = 'empty'

    @api.constrains('attachment_id', 'content', 'external_url')
    def _check_document_content(self):
        for record in self:
            if not any([record.attachment_id, record.content, record.external_url]):
                raise ValidationError(_('Document must have either file attachment, content, or external URL.'))

    def check_user_access(self, user=None):
        """Check if user can access this document"""
        self.ensure_one()
        
        if not user:
            user = self.env.user
        
        # Check if document is active and published
        if not self.active or not self.published:
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
    def get_available_documents(self, category=None, document_type=None, service_id=None, user=None):
        """Get documents available to a user"""
        if not user:
            user = self.env.user
        
        domain = [('active', '=', True), ('published', '=', True)]
        if category:
            domain.append(('category', '=', category))
        if document_type:
            domain.append(('document_type', '=', document_type))
        if service_id:
            domain.append(('service_ids', 'in', [service_id]))
        
        documents = self.search(domain)
        return documents.filtered(lambda d: d.check_user_access(user))

    def action_view_document(self):
        """View or download the document"""
        self.ensure_one()
        
        # Increment view count
        self.sudo().write({
            'view_count': self.view_count + 1,
            'last_viewed': fields.Datetime.now()
        })
        
        if self.external_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.external_url,
                'target': 'new'
            }
        elif self.video_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.video_url,
                'target': 'new'
            }
        elif self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self.attachment_id.id}?download=true',
                'target': 'new'
            }
        else:
            # Show content in form view
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

    def action_download_document(self):
        """Download the document file"""
        self.ensure_one()
        
        if not self.attachment_id:
            raise ValidationError(_('No file attached to this document.'))
        
        # Increment download count
        self.sudo().write({
            'download_count': self.download_count + 1
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.attachment_id.id}?download=true',
            'target': 'new'
        }

    def action_preview_document(self):
        """Preview the document"""
        self.ensure_one()
        
        # Increment view count
        self.sudo().write({
            'view_count': self.view_count + 1,
            'last_viewed': fields.Datetime.now()
        })
        
        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self.attachment_id.id}',
                'target': 'new'
            }
        else:
            return self.action_view_document()

    @api.model
    def search_documents(self, search_term, category=None, user=None):
        """Search documents by term"""
        if not user:
            user = self.env.user
        
        domain = [
            ('active', '=', True),
            ('published', '=', True),
            '|', '|', '|',
            ('name', 'ilike', search_term),
            ('description', 'ilike', search_term),
            ('content', 'ilike', search_term),
            ('keywords', 'ilike', search_term)
        ]
        
        if category:
            domain.append(('category', '=', category))
        
        documents = self.search(domain)
        return documents.filtered(lambda d: d.check_user_access(user))

    def name_get(self):
        """Custom name_get"""
        result = []
        for record in self:
            name = record.name
            if record.version and record.version != '1.0':
                name += f" (v{record.version})"
            result.append((record.id, name))
        return result


class ServiceDocumentTag(models.Model):
    _name = 'facilities.service.document.tag'
    _description = 'Service Document Tags'
    _order = 'name'

    name = fields.Char(
        string='Tag Name',
        required=True
    )
    
    color = fields.Integer(
        string='Color',
        help='Color for display'
    )
    
    description = fields.Text(
        string='Description',
        help='Description of this tag'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    document_count = fields.Integer(
        string='Document Count',
        compute='_compute_document_count'
    )

    def _compute_document_count(self):
        for record in self:
            record.document_count = self.env['facilities.service.document'].search_count([
                ('tag_ids', 'in', [record.id])
            ])

