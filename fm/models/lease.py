# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from datetime import datetime
from dateutil.relativedelta import relativedelta

# PDF library imports
PdfReader = None
PdfWriter = None
try:
    # Prefer pypdf (actively maintained)
    from pypdf import PdfReader as _PdfReader, PdfWriter as _PdfWriter

    PdfReader, PdfWriter = _PdfReader, _PdfWriter
except Exception:
    try:
        from PyPDF2 import PdfReader as _PdfReader, PdfWriter as _PdfWriter

        PdfReader, PdfWriter = _PdfReader, _PdfWriter
    except Exception:
        PdfReader = None
        PdfWriter = None


class FacilitiesLease(models.Model):
    _name = 'facilities.lease'
    _description = 'Facilities Lease Management'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'create_date desc'

    # Basic Information
    name = fields.Char(string='Contract Number', required=True, copy=False,
                       readonly=True, default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expiring', 'Expiring'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
    ], string='Status', default='draft', tracking=True, group_expand=True)

    # Partner References
    tenant_partner_id = fields.Many2one('res.partner', string='Tenant', tracking=True)
    landlord_partner_id = fields.Many2one('res.partner', string='Landlord Partner', tracking=True)
    lessor_partner_id = fields.Many2one('res.partner', string='Lessor Partner', tracking=True)

    # Facility References (adapted for facilities management)
    facility_id = fields.Many2one('facilities.facility', string='Facility', tracking=True)
    building_id = fields.Many2one('facilities.building', string='Building', tracking=True)
    room_ids = fields.Many2many('facilities.room', string='Rooms',
                               help="Specific rooms included in this lease")

    # Owner/Lessor Information
    owner_name = fields.Char(string="Owner's Name", tracking=True)
    owner_license_no = fields.Char(string="Owner Licence No", tracking=True)
    owner_licensing_authority = fields.Char(string="Owner Licensing Authority", tracking=True)
    lessor_name = fields.Char(string="Lessor's Name", required=True, tracking=True)
    lessor_resident_id = fields.Char(string="Lessor's Resident ID", required=True, tracking=True)
    lessor_email = fields.Char(string="Lessor's Email", tracking=True)
    lessor_phone = fields.Char(string="Lessor's Phone", tracking=True)
    lessor_license_no = fields.Char(string="Lessor License No. (If Company)", tracking=True)
    lessor_licensing_authority = fields.Char(string="Lessor Licensing Authority (If Company)", tracking=True)

    # Tenant Information
    tenant_name = fields.Char(string="Tenant's Name", required=True, tracking=True)
    tenant_resident_id = fields.Char(string="Tenant's Resident ID", required=True, tracking=True)
    tenant_email = fields.Char(string="Tenant's Email", tracking=True)
    tenant_phone = fields.Char(string="Tenant's Phone", tracking=True)
    tenant_license_no = fields.Char(string="Tenant License No. (If Company)", tracking=True)
    tenant_licensing_authority = fields.Char(string="Tenant Licensing Authority (If Company)", tracking=True)

    # Property Information
    plot_no = fields.Char(string="Plot No.", tracking=True)
    makani_no = fields.Char(string="Makani No.", tracking=True)
    location = fields.Char(string="Location", required=True, tracking=True)
    building_name = fields.Char(string="Building Name", tracking=True)
    unit_type_id = fields.Many2one('facilities.room.type', string='Unit Type', tracking=True)
    property_no = fields.Char(string="Property No.", tracking=True)
    property_area = fields.Float(string="Property Area (sq.m)", tracking=True)
    premises_no_dewa = fields.Char(string="Premises No. (DEWA)", tracking=True)
    property_usage = fields.Selection([
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
    ], string="Property Usage", required=True, default='residential', tracking=True)

    # Contract Information
    contract_date = fields.Date(string="Date", tracking=True)
    contract_start_date = fields.Date(string="Contract Start Date", required=True, tracking=True)
    contract_end_date = fields.Date(string="Contract End Date", required=True, tracking=True)
    payment_term_id = fields.Many2one('facilities.payment.term', string='Payment Term', required=True, tracking=True)
    annual_rent = fields.Monetary(string="Annual Rent", required=True, tracking=True)
    security_deposit = fields.Monetary(string="Security Deposit Amount", tracking=True)
    payment_mode = fields.Selection([
        ('1_cheque', '1 Cheque'),
        ('2_cheques', '2 Cheques'),
        ('3_cheques', '3 Cheques'),
        ('4_cheques', '4 Cheques'),
        ('6_cheques', '6 Cheques'),
        ('12_cheques', '12 Cheques'),
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
    ], string="Mode of Payment", default='4_cheques')

    # Additional Terms
    additional_terms_1 = fields.Text(string="Additional Terms 1", tracking=True)
    additional_terms_2 = fields.Text(string="Additional Terms 2", tracking=True)
    additional_terms_3 = fields.Text(string="Additional Terms 3", tracking=True)
    additional_terms_4 = fields.Text(string="Additional Terms 4", tracking=True)
    additional_terms_5 = fields.Text(string="Additional Terms 5", tracking=True)

    # System Fields
    currency_id = fields.Many2one('res.currency', string='Currency',
                                   default=lambda self: self.env.company.currency_id, tracking=True)
    company_id = fields.Many2one('res.company', string='Company',
                                  default=lambda self: self.env.company, tracking=True)

    # Responsible User
    user_id = fields.Many2one('res.users', string='Responsible',
                              default=lambda self: self.env.user, tracking=True)

    # Signature Fields
    signature = fields.Binary(string='Customer Signature', attachment=True)
    signed_on = fields.Datetime(string='Signed On', readonly=True)
    signed_by = fields.Many2one('res.partner', string='Signed By', readonly=True)
    signature_request_id = fields.Many2one('mail.activity', string='Signature Request Activity')

    # Computed Fields
    contract_duration = fields.Integer(string="Contract Duration (Days)",
                                       compute='_compute_contract_duration', store=True)
    contract_value = fields.Monetary(string="Contract Value",
                                     compute='_compute_contract_value', store=True)
    
    # Additional Computed Fields
    days_remaining = fields.Integer(string="Days Remaining",
                                    compute='_compute_days_remaining', store=True)
    is_expiring_soon = fields.Boolean(string="Expiring Soon",
                                      compute='_compute_is_expiring_soon', store=True)
    contract_status_color = fields.Selection([
        ('success', 'Green'),
        ('warning', 'Yellow'),
        ('danger', 'Red'),
        ('info', 'Blue')
    ], string="Status Color", compute='_compute_contract_status_color', store=True)
    
    # Display fields for UI
    expiring_soon_badge = fields.Html(string="Expiring Soon Badge", compute='_compute_expiring_soon_badge', store=False)
    property_name = fields.Char(string="Property Name", compute='_compute_property_name', store=True)

    # PDF Generation
    contract_pdf = fields.Binary(string="Contract PDF", attachment=True)
    contract_pdf_filename = fields.Char(string="PDF Filename")

    # Removed maintenance workorder integration - lease doesn't need workorders

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('facilities.lease') or 'New'
            # Set responsible user if not provided
            if not vals.get('user_id'):
                vals['user_id'] = self.env.user.id
        leases = super().create(vals_list)

        # Set is_tenant=True for the tenant partner when lease is created
        for lease in leases:
            if lease.tenant_partner_id:
                lease.tenant_partner_id.write({'is_tenant': True})

        return leases

    def create_contract(self):
        self._generate_and_store_pdf()

    @api.depends('contract_start_date', 'contract_end_date')
    def _compute_contract_duration(self):
        for record in self:
            if record.contract_start_date and record.contract_end_date:
                delta = record.contract_end_date - record.contract_start_date
                record.contract_duration = delta.days + 1
            else:
                record.contract_duration = 0

    @api.depends('annual_rent')
    def _compute_contract_value(self):
        for record in self:
            record.contract_value = record.annual_rent

    @api.depends('contract_end_date')
    def _compute_days_remaining(self):
        for record in self:
            if record.contract_end_date and record.state == 'active':
                delta = record.contract_end_date - fields.Date.today()
                record.days_remaining = max(0, delta.days)
            else:
                record.days_remaining = 0

    @api.depends('contract_end_date', 'state')
    def _compute_is_expiring_soon(self):
        for record in self:
            if record.contract_end_date and record.state == 'active':
                delta = record.contract_end_date - fields.Date.today()
                record.is_expiring_soon = 0 <= delta.days <= 30
            else:
                record.is_expiring_soon = False

    @api.depends('state', 'days_remaining')
    def _compute_contract_status_color(self):
        for record in self:
            if record.state == 'active':
                if record.days_remaining <= 7:
                    record.contract_status_color = 'danger'
                elif record.days_remaining <= 30:
                    record.contract_status_color = 'warning'
                else:
                    record.contract_status_color = 'success'
            elif record.state == 'draft':
                record.contract_status_color = 'warning'
            elif record.state == 'expired':
                record.contract_status_color = 'warning'
            else:
                record.contract_status_color = 'danger'

    @api.depends('is_expiring_soon')
    def _compute_expiring_soon_badge(self):
        for record in self:
            if record.is_expiring_soon:
                record.expiring_soon_badge = '<span class="badge badge-warning">Expiring Soon</span>'
            else:
                record.expiring_soon_badge = ''

    @api.depends('building_id', 'facility_id')
    def _compute_property_name(self):
        for record in self:
            property_parts = []
            if record.building_id and record.building_id.name:
                property_parts.append(record.building_id.name)
            if record.facility_id and record.facility_id.name:
                property_parts.append(record.facility_id.name)
            record.property_name = ' / '.join(property_parts) if property_parts else ''

    # Removed maintenance count computation - not needed for leases

    @api.constrains('contract_start_date', 'contract_end_date')
    def _check_contract_dates(self):
        for record in self:
            if record.contract_start_date and record.contract_end_date:
                if record.contract_end_date <= record.contract_start_date:
                    raise ValidationError(_('Contract end date must be after start date.'))

    @api.onchange('building_id')
    def _onchange_building_id(self):
        if self.building_id:
            self.landlord_partner_id = self.building_id.landlord_partner_id
            self.facility_id = False  # Reset facility when building changes

    @api.onchange('facility_id')
    def _onchange_facility_id(self):
        if self.facility_id:
            # First try to get landlord from the facility itself
            if self.facility_id.landlord_partner_id:
                self.landlord_partner_id = self.facility_id.landlord_partner_id
            # If facility doesn't have a landlord, try to get it from the building
            elif self.facility_id.building_id and self.facility_id.building_id.landlord_partner_id:
                self.landlord_partner_id = self.facility_id.building_id.landlord_partner_id

            # First try to get lessor from the facility itself
            if hasattr(self.facility_id, 'lessor_partner_id') and self.facility_id.lessor_partner_id:
                self.lessor_partner_id = self.facility_id.lessor_partner_id

    @api.onchange('contract_start_date')
    def _onchange_contract_start_date(self):
        if self.contract_start_date:
            self.contract_end_date = self.contract_start_date + relativedelta(years=1)

    @api.onchange('tenant_partner_id')
    def _onchange_tenant_partner_id(self):
        """Populate tenant information when tenant partner is selected"""
        if self.tenant_partner_id:
            # Populate tenant name
            self.tenant_name = self.tenant_partner_id.name

            # Populate tenant email
            self.tenant_email = self.tenant_partner_id.email

            # Populate tenant phone
            self.tenant_phone = self.tenant_partner_id.phone

            # Try to get resident ID from partner's identification numbers
            # Look for identification with type 'resident_id' or similar
            if hasattr(self.tenant_partner_id, 'resident_id_number') and self.tenant_partner_id.resident_id_number:
                self.tenant_resident_id = self.tenant_partner_id.resident_id_number

        else:
            # Clear fields if no partner selected
            self.tenant_name = False
            self.tenant_email = False
            self.tenant_phone = False
            self.tenant_resident_id = False

    @api.onchange('landlord_partner_id', 'lessor_partner_id')
    def _onchange_landlord_partner_id(self):
        """Populate landlord information when landlord partner is selected"""
        if self.landlord_partner_id:
            # Set is_landlord = True when landlord is assigned
            if not self.landlord_partner_id.is_landlord:
                self.landlord_partner_id.is_landlord = True

            # Populate owner name
            self.owner_name = self.landlord_partner_id.name

            # Populate lessor name
            if self.lessor_partner_id:
                self.lessor_name = self.lessor_partner_id.name
                self.lessor_email = self.lessor_partner_id.email
                self.lessor_phone = self.lessor_partner_id.phone
                if hasattr(self.lessor_partner_id, 'resident_id_number') and self.lessor_partner_id.resident_id_number:
                    self.lessor_resident_id = self.lessor_partner_id.resident_id_number
        else:
            # Clear fields if no partner selected
            self.owner_name = False
            self.lessor_name = False
            self.lessor_email = False
            self.lessor_phone = False
            self.lessor_resident_id = False

    def get_template_pdf_path(self):
        """Get the path to the PDF template"""
        module_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        return os.path.join(module_path, 'facilities_management', 'data', 'facilities_lease_contract_template.pdf')

    def action_generate_pdf(self):
        """Generate PDF contract and store on the record."""
        self.ensure_one()
        self._generate_and_store_pdf()
        return True

    def action_regenerate_pdf(self):
        """Force regenerate PDF contract and store on the record."""
        self.ensure_one()
        # Clear existing PDF to force regeneration
        self.write({'contract_pdf': False, 'contract_pdf_filename': False})

        self._generate_and_store_pdf()
        return True

    def action_download_pdf(self):
        """Generate from template and download the filled PDF"""
        self.ensure_one()
        # Always regenerate PDF to ensure latest data
        self.action_generate_pdf()

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=facilities.lease&id={self.id}&field=contract_pdf&filename={self.contract_pdf_filename}&download=true',
            'target': 'self',
        }

    def _generate_and_store_pdf(self):
        """Generate PDF and write it on the record."""
        self.ensure_one()
        pdf_content = None
        # Try generating a basic PDF report
        try:
            # For now, create a simple PDF content placeholder
            # In a real implementation, you would generate actual PDF content
            pdf_content = b"PDF placeholder content for lease contract"
        except Exception as e:
            # Last resort: raise a user-visible error
            raise ValidationError(_('Unable to generate PDF. Please contact the administrator.'))

        filename = f"Facilities_Lease_{self.name}_{datetime.now().strftime('%Y%m%d')}.pdf"
        self.write({
            'contract_pdf': base64.b64encode(pdf_content),
            'contract_pdf_filename': filename,
        })

    def write(self, vals):
        regen = bool(set(vals.keys()) & self._fields_affecting_pdf())
        res = super(FacilitiesLease, self).write(vals)
        if regen:
            for record in self:
                try:
                    record._generate_and_store_pdf()
                except Exception:
                    # Do not block write; log on chatter for visibility
                    record.message_post(
                        body=_('PDF could not be auto-generated. Use "Generate PDF" button or check server logs.'),
                        message_type='comment'
                    )
        return res

    def _fields_affecting_pdf(self):
        """Return set of field names that should trigger regeneration."""
        return {
            'landlord_partner_id', 'owner_name', 'owner_license_no', 'owner_licensing_authority',
            'lessor_partner_id', 'lessor_name', 'lessor_resident_id', 'lessor_email', 'lessor_phone',
            'lessor_license_no', 'lessor_licensing_authority',
            'tenant_partner_id', 'tenant_name', 'tenant_resident_id', 'tenant_email', 'tenant_phone',
            'tenant_license_no', 'tenant_licensing_authority',
            'plot_no', 'makani_no', 'location', 'building_name', 'unit_type_id', 'property_no',
            'property_area', 'premises_no_dewa', 'property_usage',
            'contract_date', 'contract_start_date', 'contract_end_date', 'annual_rent', 'security_deposit',
            'payment_mode', 'additional_terms_1', 'additional_terms_2', 'additional_terms_3', 'additional_terms_4', 'additional_terms_5',
            'currency_id', 'building_id', 'facility_id'
        }

    def action_view_messages(self):
        """Action to view all messages in chatter"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contract Messages'),
            'res_model': 'mail.message',
            'view_mode': 'list,form',
            'domain': [('model', '=', 'facilities.lease'), ('res_id', '=', self.id)],
            'context': {'default_model': 'facilities.lease', 'default_res_id': self.id},
        }

    def get_contract_summary(self):
        """Get a summary of the contract for display purposes"""
        self.ensure_one()
        return {
            'contract_number': self.name,
            'tenant': self.tenant_name,
            'lessor': self.lessor_name,
            'property_location': self.location,
            'annual_rent': self.currency_id.symbol + f"{self.annual_rent:,.2f}" if self.annual_rent else '',
            'contract_period': f"{self.contract_start_date} - {self.contract_end_date}" if self.contract_start_date and self.contract_end_date else '',
            'status': dict(self._fields['state'].selection).get(self.state, ''),
        }

    def action_activate_contract(self):
        """Activate the contract"""
        self.ensure_one()
        if self.state == 'draft':
            self.write({
                'state': 'active',
            })
            # Update facility occupancy
            if self.facility_id:
                self.facility_id.write({
                    'occupancy_status': 'occupied',
                    'tenant_partner_id': self.tenant_partner_id.id
                })
            return True
        return False

    def action_expire_contract(self):
        """Mark contract as expired"""
        self.ensure_one()
        if self.state == 'active':
            self.write({'state': 'expired'})
            # Update facility occupancy
            if self.facility_id:
                self.facility_id.write({
                    'occupancy_status': 'vacant',
                    'tenant_partner_id': False
                })
            return True
        return False

    def action_terminate_contract(self):
        """Terminate the contract"""
        self.ensure_one()
        if self.state in ['draft', 'active']:
            self.write({'state': 'terminated'})
            # Update facility occupancy
            if self.facility_id:
                self.facility_id.write({
                    'occupancy_status': 'vacant',
                    'tenant_partner_id': False
                })
            return True
        return False

    def action_reset_to_draft(self):
        """Reset contract to draft state and clear signature data"""
        self.ensure_one()
        if self.state != 'draft':
            # Clear signature and signed dates, then set to draft
            self.write({
                'state': 'draft',
                'signature': False,
                'signed_on': False,
                'signed_by': False,
                'signature_request_id': False,
            })
            return True
        return False

    def action_renew_contract(self):
        """Renew the contract for another period"""
        self.ensure_one()
        if self.state == 'active':
            # Create a new contract based on the current one
            new_contract_vals = {
                'tenant_name': self.tenant_name,
                'lessor_name': self.lessor_name,
                'location': self.location,
                'unit_type_id': self.unit_type_id.id if self.unit_type_id else False,
                'property_usage': self.property_usage,
                'annual_rent': self.annual_rent,
                'security_deposit': self.security_deposit,
                'payment_mode': self.payment_mode,
                'state': 'draft',
                'contract_date': fields.Date.today(),
                'contract_start_date': self.contract_end_date + relativedelta(days=1),
                'contract_end_date': self.contract_end_date + relativedelta(years=1),
            }
            
            new_contract = self.create(new_contract_vals)
            
            # Mark current contract as expired
            self.write({'state': 'expired'})
            
            return {
                'type': 'ir.actions.act_window',
                'name': _('Renewed Contract'),
                'res_model': 'facilities.lease',
                'res_id': new_contract.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return False

    def action_send_lease_by_email(self):
        """Send lease document to customer by email"""
        self.ensure_one()
        if not self.tenant_partner_id or not self.tenant_partner_id.email:
            raise ValidationError(_('Tenant partner must have an email address.'))

        # Generate PDF if not exists
        if not self.contract_pdf:
            self._generate_and_store_pdf()

        # Get email template
        template = self.env.ref('facilities_management.lease_email_template', raise_if_not_found=False)
        if not template:
            # Create template if it doesn't exist
            template = self._create_lease_email_template()

        # Create attachment for the PDF
        attachment = self.env['ir.attachment'].create({
            'name': f'Lease_Agreement_{self.name}.pdf',
            'type': 'binary',
            'datas': self.contract_pdf,
            'res_model': 'facilities.lease',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        # Send email with attachment
        template.attachment_ids = [(6, 0, [attachment.id])]
        template.send_mail(self.id, force_send=True)

        # Clean up attachment after sending
        attachment.unlink()

        # Log activity
        self.message_post(
            body=_('Lease document sent to customer: %s') % self.tenant_partner_id.email,
            message_type='comment'
        )

        return True

    def _create_lease_email_template(self):
        """Create email template for lease documents"""
        return self.env['mail.template'].create({
            'name': 'Lease Document Email',
            'model_id': self.env.ref('facilities_management.model_facilities_lease').id,
            'subject': 'Lease Agreement - {{ object.name }}',
            'body_html': '''
                <div style="margin: 0px; padding: 0px;">
                    <p>Dear {{ object.tenant_name }},</p>
                    <p>Please find attached your lease agreement document.</p>
                    <p>Contract Details:</p>
                    <ul>
                        <li><strong>Contract Number:</strong> {{ object.name }}</li>
                        <li><strong>Property:</strong> {{ object.location }}</li>
                        <li><strong>Start Date:</strong> {{ object.contract_start_date }}</li>
                        <li><strong>End Date:</strong> {{ object.contract_end_date }}</li>
                        <li><strong>Annual Rent:</strong> {{ object.currency_id.symbol }}{{ object.annual_rent }}</li>
                    </ul>
                    <p>Please review the document and let us know if you have any questions.</p>
                    <p>Best regards,<br/>{{ object.company_id.name }}</p>
                </div>
            ''',
            'attachment_ids': False,
            'email_to': '{{ object.tenant_partner_id.email }}',
            'email_from': '{{ object.company_id.email }}',
        })

    def action_request_signature(self):
        """Request customer signature for the lease"""
        self.ensure_one()
        if not self.tenant_partner_id:
            raise ValidationError(_('Tenant partner is required for signature request.'))

        # Create activity for signature request
        activity = self.env['mail.activity'].create({
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': _('Please sign the lease agreement'),
            'note': _('Lease agreement %s is ready for your signature.') % self.name,
            'user_id': self.user_id.id,
            'res_model_id': self.env.ref('facilities_management.model_facilities_lease').id,
            'res_id': self.id,
            'date_deadline': fields.Date.today() + relativedelta(days=7),
        })

        self.signature_request_id = activity.id

        # Send email notification
        self.action_send_lease_by_email()

        return True

    def action_sign_lease(self, signature_data):
        """Sign the lease agreement"""
        self.ensure_one()
        if not signature_data:
            raise ValidationError(_('Signature is required.'))

        # Update signature fields
        self.write({
            'signature': signature_data,
            'signed_on': fields.Datetime.now(),
            'signed_by': self.tenant_partner_id.id,
            'state': 'active',  # Activate lease after signing
        })

        # Mark signature request activity as done
        if self.signature_request_id:
            self.signature_request_id.action_done()

        # Log signature
        self.message_post(
            body=_('Lease agreement signed by %s on %s') % (
                self.tenant_partner_id.name,
                fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ),
            message_type='comment'
        )

        return True

    # Removed maintenance request action - not needed for leases

    @api.model
    def _cron_create_lease_reminders(self):
        """Create activities for lease agreements expiring soon"""
        reminder_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'facilities_management.lease_reminder_days', 60
        ))

        # Find leases that need reminders
        reminder_date = fields.Date.today() + relativedelta(days=reminder_days)
        leases_to_remind = self.search([
            ('contract_end_date', '=', reminder_date),
            ('state', '=', 'active'),
        ])

        for lease in leases_to_remind:
            # Check if activity already exists
            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', 'facilities.lease'),
                ('res_id', '=', lease.id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
                ('summary', 'ilike', 'Lease expiring'),
            ])

            if not existing_activity:
                # Create reminder activity
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': f'Lease expiring soon: {lease.name}',
                    'note': f'Lease agreement {lease.name} for {lease.tenant_name} expires on {lease.contract_end_date}. Please take necessary action.',
                    'user_id': lease.user_id.id,
                    'res_model_id': self.env.ref('facilities_management.model_facilities_lease').id,
                    'res_id': lease.id,
                    'date_deadline': fields.Date.today() + relativedelta(days=7),
                })

    @api.model
    def _cron_update_expiring_status(self):
        """Update lease status to expiring when approaching expiration date"""
        reminder_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'facilities_management.lease_reminder_days', 60
        ))

        # Find active leases that should be marked as expiring
        reminder_date = fields.Date.today() + relativedelta(days=reminder_days)
        expiring_leases = self.search([
            ('contract_end_date', '=', reminder_date),
            ('state', '=', 'active'),
        ])

        # Update status to expiring
        if expiring_leases:
            expiring_leases.write({'state': 'expiring'})

    @api.model
    def _cron_send_customer_reminders(self):
        """Send email reminders to customers for expiring leases"""
        reminder_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'facilities_management.lease_customer_reminder_days', 60
        ))

        # Find leases that need customer reminders
        reminder_date = fields.Date.today() + relativedelta(days=reminder_days)
        leases_to_remind = self.search([
            ('contract_end_date', '=', reminder_date),
            ('state', '=', 'active'),
            ('tenant_partner_id.email', '!=', False),
        ])

        template = self.env.ref('facilities_management.lease_reminder_email_template', raise_if_not_found=False)
        if not template:
            template = self._create_reminder_email_template()

        for lease in leases_to_remind:
            try:
                # Generate PDF if not exists
                if not lease.contract_pdf:
                    lease._generate_and_store_pdf()

                if lease.contract_pdf:
                    # Create attachment for the PDF
                    attachment = self.env['ir.attachment'].create({
                        'name': f'Lease_Agreement_{lease.name}.pdf',
                        'type': 'binary',
                        'datas': lease.contract_pdf,
                        'res_model': 'facilities.lease',
                        'res_id': lease.id,
                        'mimetype': 'application/pdf',
                    })

                    # Send email with attachment
                    template.attachment_ids = [(6, 0, [attachment.id])]
                    template.send_mail(lease.id, force_send=True)

                    # Clean up attachment after sending
                    attachment.unlink()
                else:
                    # Send without attachment if PDF generation failed
                    template.send_mail(lease.id, force_send=True)

            except Exception as e:
                pass  # Log error in real implementation

    def _create_reminder_email_template(self):
        """Create email template for lease expiration reminders"""
        return self.env['mail.template'].create({
            'name': 'Lease Expiration Reminder',
            'model_id': self.env.ref('facilities_management.model_facilities_lease').id,
            'subject': 'Lease Agreement Expiration Reminder - {{ object.name }}',
            'body_html': '''
                <div style="margin: 0px; padding: 0px;">
                    <p>Dear {{ object.tenant_name }},</p>
                    <p>This is a reminder that your lease agreement is approaching its expiration date.</p>
                    <p><strong>Lease Details:</strong></p>
                    <ul>
                        <li><strong>Contract Number:</strong> {{ object.name }}</li>
                        <li><strong>Property:</strong> {{ object.location }}</li>
                        <li><strong>Expiration Date:</strong> {{ object.contract_end_date }}</li>
                        <li><strong>Annual Rent:</strong> {{ object.currency_id.symbol }}{{ "{:,.2f}".format(object.annual_rent) }}</li>
                    </ul>
                    <p>Please contact us if you would like to renew your lease or discuss any changes.</p>
                    <p>Best regards,<br/>{{ object.company_id.name }}</p>
                </div>
            ''',
            'email_to': '{{ object.tenant_partner_id.email }}',
            'email_from': '{{ object.company_id.email or "noreply@company.com" }}',
        })

    def _has_to_be_signed(self):
        """Check if the lease needs to be signed"""
        self.ensure_one()
        return self.state == 'draft' and not self.signature

    def _has_to_be_paid(self):
        """Check if the lease needs payment (placeholder for future payment integration)"""
        self.ensure_one()
        return False

    def _compute_access_url(self):
        for record in self:
            record.access_url = '/my/lease/%s' % record.id

    def get_portal_url(self, suffix=None, report_type=None, download=None, query_string=None, anchor=None):
        """Get the portal URL for the lease"""
        self.ensure_one()
        url = self.access_url + '%s?access_token=%s%s%s%s%s' % (
            suffix if suffix else '',
            self._portal_ensure_token(),
            '&report_type=%s' % report_type if report_type else '',
            '&download=true' if download else '',
            query_string if query_string else '',
            '#%s' % anchor if anchor else ''
        )
        return url

    def unlink(self):
        """Prevent deletion of tenant lease records if state is not draft"""
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_('You cannot delete a lease that is not in draft state.'))
        return super().unlink()


class FacilitiesPaymentTerm(models.Model):
    _name = 'facilities.payment.term'
    _description = 'Facilities Payment Terms'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)


class FacilitiesLandlordContract(models.Model):
    _name = 'facilities.landlord.contract'
    _description = 'Facilities Landlord Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Contract Reference', required=True, tracking=True)
    landlord_partner_id = fields.Many2one('res.partner', string='Landlord', required=True, tracking=True,
                                        domain="[('is_landlord', '=', True)]")
    contract_type = fields.Selection([
        ('maintenance', 'Maintenance'),
        ('cleaning', 'Cleaning'),
        ('security', 'Security'),
        ('utilities', 'Utilities'),
        ('insurance', 'Insurance'),
        ('other', 'Other')
    ], string='Contract Type', required=True, tracking=True)
    
    # Contract terms
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)
    contract_value = fields.Monetary(string='Contract Value', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Vendor/Service Provider
    vendor_id = fields.Many2one('res.partner', string='Vendor/Service Provider', tracking=True)
    vendor_contact = fields.Char(string='Vendor Contact', tracking=True)
    vendor_phone = fields.Char(string='Vendor Phone', tracking=True)
    vendor_email = fields.Char(string='Vendor Email', tracking=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
        ('renewed', 'Renewed')
    ], string='Status', default='draft', tracking=True)
    
    # Contract details
    description = fields.Text(string='Description', tracking=True)
    terms_conditions = fields.Text(string='Terms & Conditions', tracking=True)
    notes = fields.Text(string='Notes', tracking=True)
    
    active = fields.Boolean(string='Active', default=True, tracking=True)
    
    @api.constrains('monthly_rent', 'security_deposit', 'maintenance_charges')
    def _check_lease_amounts(self):
        """Validate lease financial amounts."""
        for lease in self:
            if lease.monthly_rent and lease.monthly_rent < 0:
                raise ValidationError(_("Monthly rent cannot be negative."))
            if lease.security_deposit and lease.security_deposit < 0:
                raise ValidationError(_("Security deposit cannot be negative."))
            if lease.maintenance_charges and lease.maintenance_charges < 0:
                raise ValidationError(_("Maintenance charges cannot be negative."))
            
            # Security deposit should typically be 1-6 months rent
            if lease.monthly_rent and lease.security_deposit:
                if lease.security_deposit > lease.monthly_rent * 12:
                    raise ValidationError(_("Security deposit seems unusually high (more than 12 months rent). Please verify."))
    
    @api.constrains('contract_start_date', 'contract_end_date')
    def _check_lease_duration(self):
        """Validate lease duration is reasonable."""
        for lease in self:
            if lease.contract_start_date and lease.contract_end_date:
                duration = lease.contract_end_date - lease.contract_start_date
                
                # Minimum lease duration: 1 month
                if duration.days < 30:
                    raise ValidationError(_("Lease duration must be at least 30 days."))
                
                # Maximum lease duration: 99 years
                if duration.days > 36135:  # 99 years
                    raise ValidationError(_("Lease duration cannot exceed 99 years."))
    
    @api.constrains('tenant_partner_id', 'landlord_partner_id')
    def _check_tenant_landlord_different(self):
        """Ensure tenant and landlord are different entities."""
        for lease in self:
            if lease.tenant_partner_id and lease.landlord_partner_id:
                if lease.tenant_partner_id == lease.landlord_partner_id:
                    raise ValidationError(_("Tenant and landlord cannot be the same entity."))
    
    @api.constrains('state', 'contract_start_date', 'contract_end_date')
    def _check_active_lease_dates(self):
        """Validate active lease dates."""
        from datetime import date
        for lease in self:
            if lease.state == 'active':
                today = date.today()
                if lease.contract_start_date and lease.contract_start_date > today:
                    raise ValidationError(_("Cannot activate lease with future start date."))
                if lease.contract_end_date and lease.contract_end_date < today:
                    raise ValidationError(_("Cannot activate lease that has already expired."))
    
    @api.constrains('facility_id', 'building_id', 'floor_id', 'room_id')
    def _check_lease_location_hierarchy(self):
        """Validate lease location follows proper hierarchy."""
        for lease in self:
            if lease.room_id:
                if lease.floor_id and lease.room_id.floor_id != lease.floor_id:
                    raise ValidationError(_("Selected room does not belong to the selected floor."))
                if lease.building_id and lease.room_id.building_id != lease.building_id:
                    raise ValidationError(_("Selected room does not belong to the selected building."))
                if lease.facility_id and lease.room_id.facility_id != lease.facility_id:
                    raise ValidationError(_("Selected room does not belong to the selected facility."))
            
            elif lease.floor_id:
                if lease.building_id and lease.floor_id.building_id != lease.building_id:
                    raise ValidationError(_("Selected floor does not belong to the selected building."))
                if lease.facility_id and lease.floor_id.facility_id != lease.facility_id:
                    raise ValidationError(_("Selected floor does not belong to the selected facility."))
            
            elif lease.building_id:
                if lease.facility_id and lease.building_id.facility_id != lease.facility_id:
                    raise ValidationError(_("Selected building does not belong to the selected facility."))

    @api.model
    def _cron_check_expiring_leases(self):
        """Cron job to check for expiring leases and send notifications"""
        try:
            # Get leases expiring in the next 30 days
            today = fields.Date.today()
            warning_date = today + relativedelta(days=30)
            
            expiring_leases = self.search([
                ('state', '=', 'active'),
                ('end_date', '<=', warning_date),
                ('end_date', '>=', today)
            ])
            
            for lease in expiring_leases:
                # Update lease state if expiring soon
                if lease.end_date <= today + relativedelta(days=7):
                    lease.state = 'expiring'
                
                # Send notification to relevant parties
                lease._send_expiry_notification()
            
            # Mark expired leases
            expired_leases = self.search([
                ('state', 'in', ['active', 'expiring']),
                ('end_date', '<', today)
            ])
            
            for lease in expired_leases:
                lease.state = 'expired'
                lease._send_expiry_notification(expired=True)
            
            return True
            
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(f"Error in lease expiry cron job: {e}")
            return False

    def _send_expiry_notification(self, expired=False):
        """Send lease expiry notification"""
        try:
            if expired:
                subject = f"Lease Expired: {self.name}"
                body = f"The lease {self.name} has expired on {self.end_date}."
            else:
                subject = f"Lease Expiring Soon: {self.name}"
                body = f"The lease {self.name} will expire on {self.end_date}."
            
            # Send notification to tenant
            if self.tenant_partner_id and self.tenant_partner_id.email:
                self.env['mail.mail'].create({
                    'subject': subject,
                    'body_html': body,
                    'email_to': self.tenant_partner_id.email,
                    'auto_delete': True
                })
            
            # Send notification to landlord
            if self.landlord_partner_id and self.landlord_partner_id.email:
                self.env['mail.mail'].create({
                    'subject': subject,
                    'body_html': body,
                    'email_to': self.landlord_partner_id.email,
                    'auto_delete': True
                })
            
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(f"Error sending lease expiry notification: {e}")