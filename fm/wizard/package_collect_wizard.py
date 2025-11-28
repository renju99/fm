# -*- coding: utf-8 -*-
"""Package Collection Wizard for Facilities Management.

This wizard handles the package collection process including verification,
signature capture, and identity confirmation.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class PackageCollectWizard(models.TransientModel):
    """Wizard for collecting packages with verification and signature."""

    _name = 'package.collect.wizard'
    _description = 'Package Collection Wizard'

    package_id = fields.Many2one(
        'package.management',
        string='Package',
        required=True,
        readonly=True,
        help="Package to be collected"
    )
    
    tracking_number = fields.Char(
        string='Tracking Number',
        related='package_id.tracking_number',
        readonly=True
    )
    
    recipient_id = fields.Many2one(
        'res.partner',
        string='Expected Recipient',
        related='package_id.recipient_id',
        readonly=True
    )
    
    collector_id = fields.Many2one(
        'res.partner',
        string='Collected By',
        required=True,
        help="Person collecting the package"
    )
    
    collector_name = fields.Char(
        string='Collector Name',
        help="Name of person collecting (if not in system)"
    )
    
    collector_phone = fields.Char(
        string='Collector Phone',
        help="Contact number of collector"
    )
    
    collector_email = fields.Char(
        string='Collector Email',
        help="Email address of collector"
    )
    
    is_recipient = fields.Boolean(
        string='Collector is Recipient',
        default=True,
        help="Check if the collector is the actual recipient"
    )
    
    relationship = fields.Selection([
        ('self', 'Self'),
        ('family', 'Family Member'),
        ('colleague', 'Colleague'),
        ('neighbor', 'Neighbor'),
        ('assistant', 'Assistant'),
        ('authorized', 'Authorized Representative'),
        ('other', 'Other'),
    ], string='Relationship to Recipient',
        default='self',
        required=True,
        help="Relationship of collector to recipient"
    )
    
    # Identification
    id_type = fields.Selection([
        ('national_id', 'National ID'),
        ('passport', 'Passport'),
        ('drivers_license', 'Driver\'s License'),
        ('employee_id', 'Employee ID'),
        ('student_id', 'Student ID'),
        ('other', 'Other'),
    ], string='ID Type', help="Type of identification provided")
    
    id_number = fields.Char(
        string='ID Number',
        help="Identification document number"
    )
    
    id_verified = fields.Boolean(
        string='ID Verified',
        default=False,
        help="Check if identification has been verified"
    )
    
    # Signature
    signature = fields.Binary(
        string='Signature',
        required=True,
        attachment=True,
        help="Digital signature of collector"
    )
    
    signature_date = fields.Datetime(
        string='Signature Date',
        default=fields.Datetime.now,
        readonly=True
    )
    
    # Authorization
    authorization_letter = fields.Binary(
        string='Authorization Letter',
        attachment=True,
        help="Upload authorization letter if collecting on behalf of someone"
    )
    
    authorization_letter_filename = fields.Char(
        string='Authorization Letter Filename'
    )
    
    requires_authorization = fields.Boolean(
        string='Requires Authorization',
        compute='_compute_requires_authorization',
        help="Determined if authorization letter is required"
    )
    
    # Collection details
    collection_date = fields.Datetime(
        string='Collection Date',
        default=fields.Datetime.now,
        required=True,
        readonly=True
    )
    
    collected_by_staff_id = fields.Many2one(
        'res.users',
        string='Staff Member',
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
        help="Staff member processing the collection"
    )
    
    # Package condition
    package_condition = fields.Selection([
        ('good', 'Good Condition'),
        ('damaged', 'Damaged'),
        ('opened', 'Opened/Tampered'),
        ('wet', 'Wet/Water Damage'),
    ], string='Package Condition',
        default='good',
        required=True,
        help="Condition of package at collection"
    )
    
    condition_notes = fields.Text(
        string='Condition Notes',
        help="Notes about package condition or any issues"
    )
    
    # Photo verification
    collector_photo = fields.Binary(
        string='Collector Photo',
        attachment=True,
        help="Photo of person collecting the package"
    )
    
    package_photo = fields.Binary(
        string='Package Photo',
        attachment=True,
        help="Photo of package during collection"
    )
    
    # Notes
    notes = fields.Text(
        string='Collection Notes',
        help="Additional notes about the collection"
    )
    
    # Verification flags
    sms_verification_sent = fields.Boolean(
        string='SMS Verification Sent',
        default=False,
        help="SMS verification code sent to recipient"
    )
    
    verification_code = fields.Char(
        string='Verification Code',
        help="Enter verification code sent to recipient"
    )
    
    otp_verified = fields.Boolean(
        string='OTP Verified',
        default=False,
        help="One-time password verified"
    )

    @api.depends('is_recipient', 'relationship')
    def _compute_requires_authorization(self):
        """Determine if authorization letter is required."""
        for record in self:
            # Require authorization if not self-collecting
            record.requires_authorization = (
                not record.is_recipient and
                record.relationship not in ['self']
            )

    @api.onchange('collector_id')
    def _onchange_collector_id(self):
        """Auto-fill collector details from partner record."""
        if self.collector_id:
            self.collector_name = self.collector_id.name
            self.collector_phone = self.collector_id.phone
            self.collector_email = self.collector_id.email
            
            # Check if collector is the recipient
            if self.collector_id == self.recipient_id:
                self.is_recipient = True
                self.relationship = 'self'
            else:
                self.is_recipient = False

    @api.onchange('is_recipient')
    def _onchange_is_recipient(self):
        """Update relationship when is_recipient changes."""
        if self.is_recipient:
            self.relationship = 'self'
            self.collector_id = self.recipient_id

    @api.constrains('signature')
    def _check_signature(self):
        """Validate that signature is provided."""
        for record in self:
            if not record.signature:
                raise ValidationError(_(
                    "Signature is required to collect the package!"
                ))

    @api.constrains('id_verified', 'requires_authorization', 'authorization_letter')
    def _check_authorization(self):
        """Validate authorization requirements."""
        for record in self:
            if record.requires_authorization and not record.authorization_letter:
                raise ValidationError(_(
                    "Authorization letter is required when collecting "
                    "on behalf of someone else!"
                ))
            
            if not record.id_verified and record.id_type:
                raise ValidationError(_(
                    "Please verify the identification before proceeding!"
                ))

    def action_send_verification_code(self):
        """Send SMS verification code to recipient."""
        self.ensure_one()
        
        if not self.recipient_id.phone:
            raise UserError(_(
                "Recipient phone number not found. Cannot send verification code!"
            ))
        
        # Generate random 6-digit verification code
        import random
        verification_code = str(random.randint(100000, 999999))
        
        # Store verification code (in production, hash this)
        self.env['ir.config_parameter'].sudo().set_param(
            'package.verification.%s' % self.package_id.id,
            verification_code
        )
        
        # Send SMS (placeholder - implement actual SMS gateway)
        self._send_verification_sms(verification_code)
        
        self.sms_verification_sent = True
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Verification Code Sent'),
                'message': _(
                    'A verification code has been sent to %s'
                ) % self.recipient_id.phone,
                'type': 'success',
                'sticky': False,
            }
        }

    def _send_verification_sms(self, code):
        """Send verification code via SMS (placeholder)."""
        _logger.info(
            "Sending verification code %s to %s for package %s",
            code,
            self.recipient_id.phone,
            self.package_id.tracking_number
        )
        # Implement actual SMS gateway integration here

    def action_verify_code(self):
        """Verify the entered code."""
        self.ensure_one()
        
        stored_code = self.env['ir.config_parameter'].sudo().get_param(
            'package.verification.%s' % self.package_id.id
        )
        
        if not stored_code:
            raise UserError(_(
                "No verification code found. Please send a new code."
            ))
        
        if self.verification_code != stored_code:
            raise UserError(_(
                "Invalid verification code. Please try again."
            ))
        
        self.otp_verified = True
        
        # Clear the verification code
        self.env['ir.config_parameter'].sudo().set_param(
            'package.verification.%s' % self.package_id.id,
            False
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Verified'),
                'message': _('Verification code confirmed successfully!'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_confirm_collection(self):
        """Confirm package collection and update package record."""
        self.ensure_one()
        
        # Validate required fields
        if not self.signature:
            raise UserError(_("Signature is required!"))
        
        if self.requires_authorization and not self.authorization_letter:
            raise UserError(_(
                "Authorization letter is required for this collection!"
            ))
        
        # Update package record
        self.package_id.write({
            'state': 'collected',
            'collection_date': self.collection_date,
            'collected_by_id': self.collector_id.id if self.collector_id else False,
            'collected_by_staff_id': self.collected_by_staff_id.id,
            'signature': self.signature,
        })
        
        # Post message to package chatter
        message_body = _(
            "<p><strong>Package Collected</strong></p>"
            "<ul>"
            "<li>Collected by: %s</li>"
            "<li>Relationship: %s</li>"
            "<li>Collection Date: %s</li>"
            "<li>Package Condition: %s</li>"
            "<li>Staff Member: %s</li>"
        ) % (
            self.collector_name or self.collector_id.name,
            dict(self._fields['relationship'].selection).get(self.relationship),
            self.collection_date.strftime('%Y-%m-%d %H:%M:%S'),
            dict(self._fields['package_condition'].selection).get(
                self.package_condition
            ),
            self.collected_by_staff_id.name
        )
        
        if self.id_type and self.id_number:
            message_body += _(
                "<li>ID Type: %s</li>"
                "<li>ID Number: %s</li>"
            ) % (
                dict(self._fields['id_type'].selection).get(self.id_type),
                self.id_number
            )
        
        if self.notes:
            message_body += _("<li>Notes: %s</li>") % self.notes
        
        message_body += "</ul>"
        
        self.package_id.message_post(
            body=message_body,
            subject=_("Package Collected"),
            message_type='comment'
        )
        
        # Attach authorization letter if provided
        if self.authorization_letter:
            self.env['ir.attachment'].create({
                'name': self.authorization_letter_filename or 'authorization_letter.pdf',
                'datas': self.authorization_letter,
                'res_model': 'package.management',
                'res_id': self.package_id.id,
                'description': 'Authorization letter for package collection',
            })
        
        # Attach collector photo if provided
        if self.collector_photo:
            self.env['ir.attachment'].create({
                'name': 'collector_photo.jpg',
                'datas': self.collector_photo,
                'res_model': 'package.management',
                'res_id': self.package_id.id,
                'description': 'Photo of collector',
            })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _(
                    'Package %s has been collected successfully!'
                ) % self.package_id.tracking_number,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }










