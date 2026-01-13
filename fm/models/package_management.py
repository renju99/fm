# -*- coding: utf-8 -*-
"""Package Management Module for Facilities Management.

This module provides comprehensive package tracking functionality for buildings
and facilities, including package reception, storage, collection, and notifications.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class PackageManagement(models.Model):
    """Model for managing packages and deliveries in facilities."""

    _name = 'package.management'
    _description = 'Package Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'received_date desc, id desc'
    _rec_name = 'tracking_number'

    # Basic Information
    tracking_number = fields.Char(
        string='Tracking Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
        help="Unique tracking number for the package"
    )
    
    package_reference = fields.Char(
        string='Package Reference',
        help="External reference or carrier tracking number"
    )
    
    # Recipient Information
    recipient_id = fields.Many2one(
        'res.partner',
        string='Recipient',
        required=True,
        tracking=True,
        help="Person or company receiving the package"
    )
    
    recipient_phone = fields.Char(
        string='Recipient Phone',
        related='recipient_id.phone',
        readonly=True
    )
    
    recipient_email = fields.Char(
        string='Recipient Email',
        related='recipient_id.email',
        readonly=True
    )
    
    # Location Information
    facility_id = fields.Many2one(
        'facilities.facility',
        string='Facility',
        required=True,
        tracking=True,
        help="Facility where the package was received"
    )
    
    building_id = fields.Many2one(
        'facilities.building',
        string='Building',
        tracking=True,
        help="Building where recipient is located"
    )
    
    floor_id = fields.Many2one(
        'facilities.floor',
        string='Floor',
        tracking=True
    )
    
    room_id = fields.Many2one(
        'facilities.room',
        string='Room/Unit',
        tracking=True,
        help="Recipient's room or unit number"
    )
    
    storage_location = fields.Char(
        string='Storage Location',
        help="Where the package is currently stored (e.g., Mailroom Shelf A3)"
    )
    
    # Package Details
    carrier_id = fields.Many2one(
        'res.partner',
        string='Carrier',
        domain=[('is_company', '=', True)],
        help="Delivery carrier company"
    )
    
    carrier_name = fields.Char(
        string='Carrier Name',
        help="Name of delivery carrier if not in partner list"
    )
    
    package_type = fields.Selection([
        ('letter', 'Letter'),
        ('small_parcel', 'Small Parcel'),
        ('medium_parcel', 'Medium Parcel'),
        ('large_parcel', 'Large Parcel'),
        ('oversized', 'Oversized'),
        ('envelope', 'Envelope'),
        ('document', 'Document'),
        ('perishable', 'Perishable'),
        ('fragile', 'Fragile'),
    ], string='Package Type', default='small_parcel', required=True)
    
    package_size = fields.Char(
        string='Package Size',
        help="Dimensions of the package (L x W x H)"
    )
    
    package_weight = fields.Float(
        string='Weight (kg)',
        help="Package weight in kilograms"
    )
    
    package_description = fields.Text(
        string='Description',
        help="Description of package contents"
    )
    
    requires_signature = fields.Boolean(
        string='Requires Signature',
        default=False,
        help="Package requires signature upon collection"
    )
    
    is_fragile = fields.Boolean(
        string='Fragile',
        default=False
    )
    
    is_perishable = fields.Boolean(
        string='Perishable',
        default=False,
        help="Package contains perishable items"
    )
    
    # Status and Dates
    state = fields.Selection([
        ('received', 'Received'),
        ('notified', 'Recipient Notified'),
        ('ready', 'Ready for Collection'),
        ('collected', 'Collected'),
        ('returned', 'Returned to Sender'),
        ('disposed', 'Disposed'),
    ], string='Status', default='received', required=True, tracking=True)
    
    received_date = fields.Datetime(
        string='Received Date',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        help="Date and time when package was received"
    )
    
    received_by_id = fields.Many2one(
        'res.users',
        string='Received By',
        default=lambda self: self.env.user,
        required=True,
        help="Staff member who received the package"
    )
    
    notification_date = fields.Datetime(
        string='Notification Date',
        readonly=True,
        help="Date and time when recipient was notified"
    )
    
    collection_date = fields.Datetime(
        string='Collection Date',
        readonly=True,
        tracking=True,
        help="Date and time when package was collected"
    )
    
    collected_by_id = fields.Many2one(
        'res.partner',
        string='Collected By',
        readonly=True,
        help="Person who collected the package"
    )
    
    collected_by_staff_id = fields.Many2one(
        'res.users',
        string='Handed Over By',
        readonly=True,
        help="Staff member who handed over the package"
    )
    
    signature = fields.Binary(
        string='Signature',
        readonly=True,
        attachment=True,
        help="Digital signature of collector"
    )
    
    days_in_storage = fields.Integer(
        string='Days in Storage',
        compute='_compute_days_in_storage',
        store=True,
        help="Number of days package has been in storage"
    )
    
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        store=True,
        help="Package has been in storage too long"
    )
    
    # Images and Attachments
    package_image = fields.Binary(
        string='Package Photo',
        attachment=True,
        help="Photo of the package"
    )
    
    # Notes
    notes = fields.Text(
        string='Internal Notes',
        help="Internal notes about the package"
    )
    
    special_instructions = fields.Text(
        string='Special Instructions',
        help="Special handling or delivery instructions"
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
        """Override create to generate tracking number sequence."""
        if vals.get('tracking_number', _('New')) == _('New'):
            vals['tracking_number'] = self.env['ir.sequence'].next_by_code(
                'package.management'
            ) or _('New')
        return super(PackageManagement, self).create(vals)

    @api.depends('received_date', 'collection_date', 'state')
    def _compute_days_in_storage(self):
        """Compute number of days package has been in storage."""
        for record in self:
            if record.state in ['received', 'notified', 'ready']:
                if record.received_date:
                    delta = datetime.now() - record.received_date
                    record.days_in_storage = delta.days
                else:
                    record.days_in_storage = 0
            else:
                record.days_in_storage = 0

    @api.depends('days_in_storage', 'state')
    def _compute_is_overdue(self):
        """Check if package is overdue (more than 7 days in storage)."""
        max_days = self.env['ir.config_parameter'].sudo().get_param(
            'package.max_storage_days', default='7'
        )
        for record in self:
            if record.state in ['received', 'notified', 'ready']:
                record.is_overdue = record.days_in_storage > int(max_days)
            else:
                record.is_overdue = False

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

    @api.constrains('received_date', 'collection_date')
    def _check_dates(self):
        """Validate that collection date is after received date."""
        for record in self:
            if record.collection_date and record.received_date:
                if record.collection_date < record.received_date:
                    raise ValidationError(_(
                        "Collection date cannot be before received date!"
                    ))

    def action_notify_recipient(self):
        """Send notification to recipient about package arrival."""
        self.ensure_one()
        if self.state != 'received':
            raise UserError(_(
                "Can only notify recipient for packages in 'Received' state!"
            ))
        
        # Send email notification
        template = self.env.ref(
            'fm.email_template_package_arrival',
            raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)
        
        # Send SMS if phone number exists
        if self.recipient_phone:
            self._send_sms_notification()
        
        # Update state and notification date
        self.write({
            'state': 'notified',
            'notification_date': fields.Datetime.now(),
        })
        
        # Post message to chatter
        self.message_post(
            body=_("Recipient %s has been notified about package arrival.") % (
                self.recipient_id.name
            ),
            subject=_("Recipient Notified")
        )
        
        return True

    def _send_sms_notification(self):
        """Send SMS notification to recipient (placeholder for SMS integration)."""
        # This is a placeholder method
        # Implement SMS gateway integration as needed
        _logger.info(
            "SMS notification would be sent to %s for package %s",
            self.recipient_phone,
            self.tracking_number
        )

    def action_mark_ready(self):
        """Mark package as ready for collection."""
        for record in self:
            if record.state not in ['received', 'notified']:
                raise UserError(_(
                    "Can only mark received or notified packages as ready!"
                ))
            record.write({'state': 'ready'})
            record.message_post(
                body=_("Package marked as ready for collection."),
                subject=_("Ready for Collection")
            )

    def action_collect_package(self):
        """Open wizard to collect package."""
        self.ensure_one()
        if self.state not in ['notified', 'ready']:
            raise UserError(_(
                "Can only collect packages that are notified or ready!"
            ))
        
        return {
            'name': _('Collect Package'),
            'type': 'ir.actions.act_window',
            'res_model': 'package.collect.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_package_id': self.id,
                'default_recipient_id': self.recipient_id.id,
            }
        }

    def action_return_to_sender(self):
        """Mark package as returned to sender."""
        for record in self:
            if record.state == 'collected':
                raise UserError(_(
                    "Cannot return a package that has been collected!"
                ))
            record.write({
                'state': 'returned',
            })
            record.message_post(
                body=_("Package returned to sender."),
                subject=_("Returned to Sender")
            )

    def action_dispose_package(self):
        """Mark package as disposed (after retention period)."""
        for record in self:
            if record.state == 'collected':
                raise UserError(_(
                    "Cannot dispose a package that has been collected!"
                ))
            if record.days_in_storage < 30:
                raise UserError(_(
                    "Packages can only be disposed after 30 days in storage!"
                ))
            record.write({
                'state': 'disposed',
            })
            record.message_post(
                body=_("Package disposed after retention period."),
                subject=_("Package Disposed")
            )

    @api.model
    def _cron_send_overdue_notifications(self):
        """Cron job to send notifications for overdue packages."""
        overdue_packages = self.search([
            ('is_overdue', '=', True),
            ('state', 'in', ['received', 'notified', 'ready'])
        ])
        
        for package in overdue_packages:
            package.message_post(
                body=_(
                    "Package %s has been in storage for %d days. "
                    "Please follow up with recipient %s."
                ) % (
                    package.tracking_number,
                    package.days_in_storage,
                    package.recipient_id.name
                ),
                subject=_("Overdue Package Alert"),
                message_type='notification'
            )
        
        _logger.info(
            "Sent overdue notifications for %d packages",
            len(overdue_packages)
        )

    def name_get(self):
        """Custom name_get to show tracking number and recipient."""
        result = []
        for record in self:
            name = "%s - %s" % (
                record.tracking_number,
                record.recipient_id.name
            )
            result.append((record.id, name))
        return result










