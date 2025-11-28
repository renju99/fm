# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class ServiceRequest(models.Model):
    _name = 'facilities.service.request'
    _description = 'Service Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, create_date desc'
    _rec_name = 'display_name'

    # Basic Information
    name = fields.Char(
        string='Request Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    title = fields.Char(
        string='Title',
        required=True,
        tracking=True,
        help='Brief title describing the service request'
    )
    
    description = fields.Html(
        string='Description',
        required=True,
        tracking=True,
        help='Detailed description of the service request'
    )
    
    # Request Details
    service_type = fields.Selection([
        ('plumbing', '🚿 Plumbing & Water Issues'),
        ('electrical', '⚡ Electrical & Power Issues'),
        ('hvac', '❄️ Heating, Cooling & Ventilation'),
        ('appliances', '🏠 Appliances & Equipment'),
        ('doors_windows', '🚪 Doors, Windows & Locks'),
        ('safety_security', '🛡️ Safety & Security'),
        ('cleaning_maintenance', '🧹 Cleaning & General Maintenance'),
        ('utilities', '⚡ Utilities & Services'),
        ('common_areas', '🏢 Common Areas & Amenities'),
        ('other', '❓ Other Issues')
    ], string='Issue Category', required=True, tracking=True)
    
    category_id = fields.Many2one(
        'facilities.service.catalog',
        string='Service Category',
        tracking=True,
        help='Service catalog category for this request'
    )
    
    priority = fields.Selection([
        ('0', 'Very Low'),
        ('1', 'Low'),
        ('2', 'Normal'),
        ('3', 'High'),
        ('4', 'Very High'),
        ('5', 'Critical')
    ], string='Priority', default='2', required=True, tracking=True)
    
    urgency = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Urgency', default='medium', required=True, tracking=True)
    
    # Status and Workflow
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('in_progress', 'In Progress'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('on_hold', 'On Hold'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)
    
    # People
    requester_id = fields.Many2one(
        'res.users',
        string='Requester',
        required=True,
        default=lambda self: self.env.user,
        tracking=True
    )
    
    assigned_to_id = fields.Many2one(
        'res.users',
        string='Assigned To',
        tracking=True,
        help='User responsible for handling this request'
    )
    
    team_id = fields.Many2one(
        'maintenance.team',
        string='Assigned Team',
        tracking=True,
        help='Team responsible for handling this request'
    )
    
    # Asset and Location
    asset_id = fields.Many2one(
        'facilities.asset',
        string='Related Asset',
        tracking=True,
        ondelete='restrict',
        help='Asset related to this service request'
    )
    
    facility_id = fields.Many2one(
        'facilities.facility',
        string='Facility',
        tracking=True,
        ondelete='restrict'
    )
    
    building_id = fields.Many2one(
        'facilities.building',
        string='Building',
        tracking=True
    )
    
    floor_id = fields.Many2one(
        'facilities.floor',
        string='Floor',
        tracking=True
    )
    
    room_id = fields.Many2one(
        'facilities.room',
        string='Room',
        tracking=True
    )
    
    # Dates and SLA
    request_date = fields.Datetime(
        string='Request Date',
        default=fields.Datetime.now,
        required=True,
        tracking=True
    )
    
    due_date = fields.Datetime(
        string='Due Date',
        tracking=True,
        help='Expected completion date'
    )
    
    resolution_date = fields.Datetime(
        string='Resolution Date',
        tracking=True,
        readonly=True
    )
    
    sla_id = fields.Many2one(
        'facilities.sla',
        string='SLA',
        tracking=True,
        help='Service Level Agreement for this request'
    )
    
    sla_deadline = fields.Datetime(
        string='SLA Deadline',
        compute='_compute_sla_deadline',
        store=True,
        tracking=True
    )
    
    sla_status = fields.Selection([
        ('on_time', 'On Time'),
        ('at_risk', 'At Risk'),
        ('breached', 'Breached')
    ], string='SLA Status', compute='_compute_sla_status', store=True)
    
    # Work Order Integration
    workorder_id = fields.Many2one(
        'facilities.workorder',
        string='Related Work Order',
        readonly=True,
        tracking=True,
        help='Work order created from this service request'
    )
    
    can_create_workorder = fields.Boolean(
        string='Can Create Work Order',
        compute='_compute_can_create_workorder'
    )
    
    # Communication and Tracking
    resolution_notes = fields.Html(
        string='Resolution Notes',
        tracking=True,
        help='Notes about how the request was resolved'
    )
    
    feedback_rating = fields.Selection([
        ('1', 'Very Poor'),
        ('2', 'Poor'),
        ('3', 'Average'),
        ('4', 'Good'),
        ('5', 'Excellent')
    ], string='Feedback Rating', tracking=True)
    
    feedback_comments = fields.Text(
        string='Feedback Comments',
        tracking=True
    )
    
    # Approval Process
    approval_required = fields.Boolean(
        string='Approval Required',
        default=False,
        tracking=True
    )
    
    approver_id = fields.Many2one(
        'res.users',
        string='Approver',
        tracking=True
    )
    
    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True,
        tracking=True
    )
    
    approval_notes = fields.Text(
        string='Approval Notes',
        tracking=True
    )
    
    # Computed Fields
    days_open = fields.Integer(
        string='Days Open',
        compute='_compute_days_open',
        store=True,
        help='Number of days the request has been open'
    )
    
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        store=True
    )
    
    # Additional Information
    attachment_count = fields.Integer(
        string='Attachment Count',
        compute='_compute_attachment_count'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    # Contact Information
    contact_phone = fields.Char(
        string='Contact Phone',
        help='Phone number for contact regarding this request'
    )
    
    contact_email = fields.Char(
        string='Contact Email',
        help='Email address for contact regarding this request'
    )
    
    # Website/Portal compatibility fields
    is_frontend_multilang = fields.Boolean(
        string='Is Frontend Multilang',
        compute='_compute_is_frontend_multilang',
        help='Compatibility field for portal templates'
    )
    
    # Cost Tracking
    estimated_cost = fields.Monetary(
        string='Estimated Cost',
        currency_field='currency_id'
    )
    
    actual_cost = fields.Monetary(
        string='Actual Cost',
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    @api.depends('title', 'name')
    def _compute_display_name(self):
        for record in self:
            if record.title:
                record.display_name = f"[{record.name}] {record.title}"
            else:
                record.display_name = record.name or _('New Service Request')

    @api.depends('sla_id', 'request_date', 'priority')
    def _compute_sla_deadline(self):
        for record in self:
            if record.sla_id and record.request_date:
                # Calculate deadline based on SLA response time and priority
                hours_to_add = record.sla_id.response_time_hours or 24
                # Adjust based on priority
                priority_multiplier = {
                    '0': 2.0,    # Very Low - double time
                    '1': 1.5,    # Low - 1.5x time
                    '2': 1.0,    # Normal - standard time
                    '3': 0.75,   # High - 25% less time
                    '4': 0.5,    # Very High - 50% less time
                    '5': 0.25,   # Critical - 75% less time
                }.get(record.priority, 1.0)
                
                adjusted_hours = hours_to_add * priority_multiplier
                record.sla_deadline = record.request_date + timedelta(hours=adjusted_hours)
            else:
                record.sla_deadline = False

    @api.depends('sla_deadline', 'state')
    def _compute_sla_status(self):
        now = fields.Datetime.now()
        for record in self:
            if not record.sla_deadline or record.state in ['resolved', 'closed', 'cancelled']:
                record.sla_status = 'on_time'
            elif now > record.sla_deadline:
                record.sla_status = 'breached'
            elif now > (record.sla_deadline - timedelta(hours=2)):  # 2 hours before deadline
                record.sla_status = 'at_risk'
            else:
                record.sla_status = 'on_time'

    @api.depends('state', 'service_type', 'workorder_id')
    def _compute_can_create_workorder(self):
        for record in self:
            # Can create work order when technician has inspected (in_progress state)
            record.can_create_workorder = (
                record.state == 'in_progress' and
                not record.workorder_id and
                record.service_type in ['maintenance', 'facility_service']
            )

    @api.depends('request_date', 'state')
    def _compute_days_open(self):
        for record in self:
            if record.state not in ['resolved', 'closed', 'cancelled']:
                delta = fields.Datetime.now() - record.request_date
                record.days_open = delta.days
            else:
                if record.resolution_date:
                    delta = record.resolution_date - record.request_date
                    record.days_open = delta.days
                else:
                    record.days_open = 0

    @api.depends('due_date', 'state')
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for record in self:
            record.is_overdue = (
                record.due_date and
                now > record.due_date and
                record.state not in ['resolved', 'closed', 'cancelled']
            )

    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = self.env['ir.attachment'].search_count([
                ('res_model', '=', self._name),
                ('res_id', '=', record.id)
            ])
    
    def _compute_is_frontend_multilang(self):
        """Compute is_frontend_multilang from request context"""
        for record in self:
            # Get the value from the request object if available
            try:
                from odoo.http import request
                record.is_frontend_multilang = getattr(request, 'is_frontend_multilang', False)
            except:
                # Default to False if not in a web context
                record.is_frontend_multilang = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('facilities.service.request') or _('New')
        
        records = super().create(vals_list)
        
        # Send notification emails only for submitted records
        for record in records:
            # Only send creation notification if the record is already submitted
            # (for portal auto-submit). For draft records, wait until action_submit
            if record.state == 'submitted' and record.contact_email:
                record._send_creation_notification()
            
            # Send assignment notification if already assigned
            if record.assigned_to_id:
                record._send_assignment_notification()
        
        return records

    def write(self, vals):
        # Track state changes
        old_states = {record.id: record.state for record in self}
        old_assigned = {record.id: record.assigned_to_id for record in self}
        
        result = super().write(vals)
        
        # Handle state changes
        for record in self:
            if 'state' in vals and old_states[record.id] != record.state:
                record._handle_state_change(old_states[record.id], record.state)
            
            if 'assigned_to_id' in vals and old_assigned[record.id] != record.assigned_to_id:
                if record.assigned_to_id:
                    record._send_assignment_notification()
        
        return result

    def _handle_state_change(self, old_state, new_state):
        """Handle actions when state changes"""
        if new_state == 'resolved':
            self.resolution_date = fields.Datetime.now()
            self._send_resolution_notification()
        elif new_state in ['closed', 'cancelled']:
            if not self.resolution_date:
                self.resolution_date = fields.Datetime.now()
        
        # Send status update notification for all state changes
        self._send_status_update_notification(old_state, new_state)

    def _send_assignment_notification(self):
        """Send notification when request is assigned"""
        template = self.env.ref('facilities_management.service_request_assignment_email_template', raise_if_not_found=False)
        if template and self.assigned_to_id:
            template.send_mail(self.id, force_send=True)

    def _send_resolution_notification(self):
        """Send direct resolution notification without template"""
        if not self.contact_email:
            return
            
        # Format resolution date
        resolution_date_str = self.resolution_date.strftime('%B %d, %Y at %I:%M %p') if self.resolution_date else 'Not specified'
        request_date_str = self.request_date.strftime('%B %d, %Y at %I:%M %p') if self.request_date else 'Not specified'
        
        email_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #28a745; margin-bottom: 20px;">✅ Service Request Resolved</h2>
            <p style="font-size: 14px;">Hello,</p>
            <p style="font-size: 14px;">Great news! Your service request has been successfully resolved:</p>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #28a745;">
                <h3 style="color: #28a745; margin-top: 0;">Request Details</h3>
                <p><strong>Request Number:</strong> {self.name}</p>
                <p><strong>Title:</strong> {self.title}</p>
                <p><strong>Service Type:</strong> {dict(self._fields['service_type'].selection)[self.service_type]}</p>
                <p><strong>Request Date:</strong> {request_date_str}</p>
                <p><strong>Resolution Date:</strong> {resolution_date_str}</p>
                {f'<p><strong>Resolved By:</strong> {self.assigned_to_id.name}</p>' if self.assigned_to_id else ''}
                {f'<p><strong>Resolution Notes:</strong></p><p style="background-color: #e9ecef; padding: 10px; border-radius: 4px;">{self.resolution_notes}</p>' if self.resolution_notes else ''}
            </div>
            
            <div style="background-color: #d4edda; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #28a745;">
                <p style="margin: 0; color: #155724; font-weight: bold;">🎉 Your service request has been successfully completed! We hope you're satisfied with the service provided.</p>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="/my/service-request/{self.id}" style="background-color: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; margin-right: 10px;">
                    🔗 View Service Request
                </a>
                <a href="/my/service-request/{self.id}#feedback" style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                    ⭐ Provide Feedback
                </a>
            </div>
            
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
                <p style="margin: 0; color: #856404; font-weight: bold;">📝 We'd love your feedback! Please take a moment to rate the service and let us know how we can improve.</p>
            </div>
            
            <p style="font-size: 13px; color: #666;">Best regards,<br/><strong>Facilities Management Team</strong></p>
        </div>
        """
        
        mail_values = {
            'subject': f'Service Request Resolved: {self.name} - {self.title}',
            'body_html': email_body,
            'email_to': self.contact_email,
            'email_from': self.env.user.email or 'noreply@yourcompany.com',
            'auto_delete': True,
        }
        
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
        
        self.message_post(
            body=f"📧 Resolution notification email sent to: {self.contact_email}",
            subject=f"Email Notification: Resolution Notice Sent"
        )
        
        return True

    def _send_status_update_notification(self, old_state, new_state):
        """Send status update notification to requester and contact email"""
        if old_state == new_state:
            return
            
        # Don't send duplicate notifications for resolved state (handled separately)
        if new_state == 'resolved':
            return
        
        # Send direct email without template to avoid template variable issues
        self._send_direct_status_email(new_state)

    def _send_direct_status_email(self, status):
        """Send direct email notification without template"""
        if not self.contact_email:
            return
            
        # Status messages
        status_messages = {
            'submitted': '📋 Your service request has been submitted and is awaiting assignment to a technician.',
            'in_progress': '🔧 Work has started on your service request. Our technician is actively working to resolve your issue.',
            'pending_approval': '⏳ Your service request is pending approval before work can continue.',
            'approved': '✅ Your service request has been approved and work will resume shortly.',
            'rejected': '❌ Your service request has been rejected. Please contact us for more information.',
            'on_hold': '⏸️ Your service request has been temporarily put on hold. We will resume work as soon as possible.',
            'closed': '📁 Your service request has been closed. Thank you for using our services!',
            'cancelled': '🚫 Your service request has been cancelled.'
        }
        
        status_msg = status_messages.get(status, f'Your service request status has been updated to: {status}')
        
        # Create email body
        email_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #007bff; margin-bottom: 20px;">📋 Service Request Status Update</h2>
            
            <p style="font-size: 14px;">Hello,</p>
            <p style="font-size: 14px;">Your service request status has been updated:</p>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #007bff;">
                <h3 style="color: #007bff; margin-top: 0;">Request Details</h3>
                <p><strong>Request Number:</strong> {self.name}</p>
                <p><strong>Title:</strong> {self.title}</p>
                <p><strong>Service Type:</strong> {self.service_type}</p>
                <p><strong>Priority:</strong> {self.priority}</p>
                <p><strong>Current Status:</strong> <span style="background-color: #007bff; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;">{status}</span></p>
                <p><strong>Days Open:</strong> {self.days_open} days</p>
                {f'<p><strong>Assigned To:</strong> {self.assigned_to_id.name}</p>' if self.assigned_to_id else ''}
            </div>
            
            <div style="background-color: #e7f3ff; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #007bff;">
                <p style="margin: 0; color: #004085; font-weight: bold;">{status_msg}</p>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="/my/service-request/{self.id}" style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                    🔗 View Service Request
                </a>
            </div>
            
            <p style="font-size: 13px; color: #666;">Best regards,<br/><strong>Facilities Management Team</strong></p>
        </div>
        """
        
        # Send email directly
        mail_values = {
            'subject': f'Service Request Update: {self.name} - {self.title}',
            'body_html': email_body,
            'email_to': self.contact_email,
            'email_from': self.env.user.email or 'noreply@yourcompany.com',
            'auto_delete': True,
        }
        
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
        
        # Add chatter notification about email sent
        self.message_post(
            body=f"📧 Status update email sent to: {self.contact_email}",
            subject=f"Email Notification: Status Update Sent"
        )
        
        return True

    def _send_creation_notification(self):
        """Send creation confirmation notification to requester and contact email"""
        if not self.contact_email:
            return
            
        # Create email body directly
        email_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #28a745; margin-bottom: 20px;">✅ Service Request Created Successfully</h2>
            
            <p style="font-size: 14px;">Hello,</p>
            <p style="font-size: 14px;">Thank you for submitting your service request. Here are the details:</p>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #28a745;">
                <h3 style="color: #28a745; margin-top: 0;">Request Details</h3>
                <p><strong>Request Number:</strong> {self.name}</p>
                <p><strong>Title:</strong> {self.title}</p>
                <p><strong>Service Type:</strong> {self.service_type}</p>
                <p><strong>Priority:</strong> {self.priority}</p>
                <p><strong>Status:</strong> <span style="background-color: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;">{self.state}</span></p>
                <p><strong>Contact Email:</strong> {self.contact_email}</p>
                <p><strong>Contact Phone:</strong> {self.contact_phone or 'Not provided'}</p>
            </div>
            
            <div style="background-color: #e7f3ff; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #007bff;">
                <h4 style="color: #007bff; margin-top: 0;">📋 What's Next:</h4>
                <ul style="color: #004085;">
                    <li>Our team will review and assign your request</li>
                    <li>You'll receive email updates on progress</li>
                    <li>Track your request anytime in the portal</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="/my/service-request/{self.id}" style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                    🔗 Track Your Request
                </a>
            </div>
            
            <p style="font-size: 13px; color: #666;">Best regards,<br/><strong>Facilities Management Team</strong></p>
        </div>
        """
        
        # Send email directly
        mail_values = {
            'subject': f'Service Request Created: {self.name} - {self.title}',
            'body_html': email_body,
            'email_to': self.contact_email,
            'email_from': self.env.user.email or 'noreply@yourcompany.com',
            'auto_delete': True,
        }
        
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
        
        # Add chatter notification about email sent
        self.message_post(
            body=f"📧 Creation confirmation email sent to: {self.contact_email}",
            subject=f"Email Notification: Creation Confirmation Sent"
        )
        
        return True

    def action_submit(self):
        """Submit the service request"""
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_("Service request can only be submitted from Draft state. Current state: %s") % record.state)
            record.state = 'submitted'
            record.message_post(body=_('Service request submitted for processing.'))
            # Send creation notification if not already sent
            if record.contact_email:
                record._send_creation_notification()

    def action_start_progress(self):
        """Start working on the service request"""
        for record in self:
            if record.state not in ['submitted', 'approved']:
                raise ValidationError(_("Service request can only be started from Submitted or Approved state. Current state: %s") % record.state)
            record.state = 'in_progress'
            record.message_post(body=_('Work started on service request.'))

    def action_resolve(self):
        """Mark the service request as resolved"""
        for record in self:
            if record.state in ['submitted', 'in_progress', 'approved']:
                record.state = 'resolved'
                record.resolution_date = fields.Datetime.now()
                record.message_post(body=_('Service request resolved.'))

    def action_close(self):
        """Close the service request"""
        for record in self:
            if record.state == 'resolved':
                record.state = 'closed'
                record.message_post(body=_('Service request closed.'))

    def action_cancel(self):
        """Cancel the service request"""
        for record in self:
            if record.state not in ['closed', 'resolved']:
                record.state = 'cancelled'
                record.message_post(body=_('Service request cancelled.'))

    def action_reopen(self, reopen_reason=None):
        """Reopen a closed or resolved service request"""
        for record in self:
            if record.state not in ['closed', 'resolved', 'cancelled']:
                raise UserError(_("Only closed, resolved, or cancelled service requests can be reopened."))
            
            # Check permissions - only requester or manager can reopen
            if not record.can_user_reopen():
                raise UserError(_("You can only reopen service requests that you created, or you need manager permissions."))
            
            # Update state and fields
            record.state = 'submitted'
            record.resolution_date = False
            record.resolution_notes = False  # Clear resolution notes when reopening
            
            # Reopen associated workorder if it exists and is completed
            if record.workorder_id and record.workorder_id.state == 'completed':
                # Update workorder state to in_progress
                record.workorder_id.state = 'in_progress'
                
                # Reset first time fix status since we're reopening
                record.workorder_id.first_time_fix = False
                
                # Create log entry for workorder
                workorder_message = _("Work order reopened due to service request reopening by %s.\nReason: %s") % (
                    self.env.user.name,
                    reopen_reason or _('Service request reopened')
                )
                
                record.workorder_id.sudo().message_post(
                    body=workorder_message,
                    message_type='notification'
                )
                
                # Create activity for the technician if assigned
                if record.workorder_id.technician_id and record.workorder_id.technician_id.user_id:
                    record.workorder_id.activity_schedule(
                        'mail.mail_activity_data_todo',
                        summary=_('Work Order Reopened'),
                        note=_('Work order %s has been reopened due to service request reopening. Reason: %s') % (
                            record.workorder_id.name, reopen_reason or _('Service request reopened')
                        ),
                        user_id=record.workorder_id.technician_id.user_id.id,
                        date_deadline=fields.Date.today()
                    )
            
            # Post message to chatter (use sudo to bypass portal user permission issues)
            message = _('Service request reopened.')
            if reopen_reason:
                message += _('\nReopen reason: %s') % reopen_reason
            
            # Add note about workorder reopening if applicable
            if record.workorder_id and record.workorder_id.state == 'in_progress':
                message += _('\nAssociated work order has also been reopened and is now in progress.')
            
            # Use sudo to allow portal users to post messages
            record.sudo().message_post(body=message)
            
        return True

    def can_user_reopen(self, user_id=None):
        """Check if the given user can reopen this service request"""
        if not user_id:
            user_id = self.env.user.id
        
        # Get the current user
        current_user = self.env['res.users'].browse(user_id)
        
        # Check if user is the requester or has manager permissions
        is_requester = (self.requester_id.id == user_id)
        
        has_manager_permissions = current_user.has_group('facilities_management.group_facilities_manager')
        
        return (
            (is_requester or has_manager_permissions) and 
            self.state in ['closed', 'resolved', 'cancelled']
        )
    
    def can_portal_user_reopen(self, user_id=None):
        """Portal-safe method to check if user can reopen this service request"""
        if not user_id:
            user_id = self.env.user.id
        
        # For portal users, we need to be more careful with permission checking
        try:
            # Use sudo to avoid permission issues
            service_request = self.sudo()
            current_user = self.env['res.users'].browse(user_id)
            
            # Check if user is the requester
            is_requester = (service_request.requester_id.id == user_id)
            
            # Check manager permissions (this might fail for portal users, so we catch it)
            try:
                has_manager_permissions = current_user.has_group('facilities_management.group_facilities_manager')
            except:
                has_manager_permissions = False
            
            return (
                (is_requester or has_manager_permissions) and 
                service_request.state in ['closed', 'resolved', 'cancelled']
            )
        except Exception as e:
            _logger.warning(f"Error checking portal user reopen permissions: {e}")
            return False

    def action_approve(self):
        """Approve the service request"""
        for record in self:
            if record.state == 'pending_approval':
                record.state = 'approved'
                record.approval_date = fields.Datetime.now()
                record.approver_id = self.env.user
                record.message_post(body=_('Service request approved.'))

    def action_reject(self):
        """Reject the service request"""
        for record in self:
            if record.state == 'pending_approval':
                record.state = 'rejected'
                record.approval_date = fields.Datetime.now()
                record.approver_id = self.env.user
                record.message_post(body=_('Service request rejected.'))

    def action_request_approval(self):
        """Request approval for the service request"""
        for record in self:
            if record.state in ['submitted', 'in_progress']:
                record.state = 'pending_approval'
                record.message_post(body=_('Approval requested for service request.'))

    def action_put_on_hold(self):
        """Put the service request on hold"""
        for record in self:
            if record.state in ['submitted', 'in_progress', 'approved']:
                record.state = 'on_hold'
                record.message_post(body=_('Service request put on hold.'))

    def action_resume(self):
        """Resume a service request from hold"""
        for record in self:
            if record.state == 'on_hold':
                record.state = 'in_progress'
                record.message_post(body=_('Service request resumed.'))

    def action_create_workorder(self):
        """Create a work order from this service request after technician inspection"""
        for record in self:
            if not record.can_create_workorder:
                raise UserError(_('Work orders can only be created when the service request is in progress (after technician inspection).'))
            
            # Open a wizard to select the asset identified during inspection
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'service.request.workorder.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_service_request_id': record.id,
                    'default_description': record.description,
                    'default_priority': record.priority,
                    'default_facility_id': record.facility_id.id if record.facility_id else False,
                    'default_building_id': record.building_id.id if record.building_id else False,
                    'default_floor_id': record.floor_id.id if record.floor_id else False,
                    'default_room_id': record.room_id.id if record.room_id else False,
                    'default_sla_id': record.sla_id.id if record.sla_id else False,
                    'default_team_id': record.team_id.id if record.team_id else False,
                }
            }

    def action_view_workorder(self):
        """View the related work order"""
        self.ensure_one()
        if self.workorder_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'facilities.workorder',
                'res_id': self.workorder_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_view_attachments(self):
        """View attachments for this service request"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'view_mode': 'list,form',
            'name': _('Attachments'),
            'target': 'current',
        }

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        """Auto-populate location fields when asset is selected"""
        if self.asset_id:
            self.facility_id = self.asset_id.facility_id
            self.building_id = self.asset_id.building_id
            self.floor_id = self.asset_id.floor_id
            self.room_id = self.asset_id.room_id

    @api.onchange('service_type')
    def _onchange_service_type(self):
        """Set default SLA based on service type"""
        if self.service_type:
            sla = self.env['facilities.sla'].search([
                ('service_type', '=', self.service_type)
            ], limit=1)
            if sla:
                self.sla_id = sla

    @api.onchange('urgency')
    def _onchange_urgency(self):
        """Auto-calculate priority based on urgency"""
        if self.urgency:
            priority_mapping = {
                'low': '1',
                'medium': '2',
                'high': '3',
                'critical': '4',
            }
            self.priority = priority_mapping.get(self.urgency, '2')

    def name_get(self):
        """Custom name_get to show title with request number"""
        result = []
        for record in self:
            if record.title:
                name = f"[{record.name}] {record.title}"
            else:
                name = record.name
            result.append((record.id, name))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        """Enhanced search to include title and description"""
        args = args or []
        domain = []
        if name:
            domain = ['|', '|', '|',
                     ('name', operator, name),
                     ('title', operator, name),
                     ('description', operator, name),
                     ('display_name', operator, name)]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
    
    @api.constrains('state')
    def _check_state_transitions(self):
        """Validate state transitions follow business rules."""
        for record in self:
            if record._origin.id:  # Only check for existing records
                old_state = record._origin.state
                new_state = record.state
                
                # Define valid transitions
                valid_transitions = {
                    'draft': ['submitted', 'cancelled'],
                    'submitted': ['in_progress', 'pending_approval', 'approved', 'rejected', 'cancelled'],
                    'in_progress': ['resolved', 'on_hold', 'pending_approval', 'cancelled'],
                    'pending_approval': ['approved', 'rejected', 'cancelled'],
                    'approved': ['in_progress', 'resolved', 'cancelled'],
                    'rejected': ['submitted', 'cancelled'],
                    'on_hold': ['in_progress', 'cancelled'],
                    'resolved': ['closed', 'in_progress', 'submitted'],  # Allow reopening
                    'closed': ['submitted'],  # Allow reopening from closed
                    'cancelled': ['submitted']   # Allow reopening from cancelled
                }
                
                if new_state != old_state and new_state not in valid_transitions.get(old_state, []):
                    raise ValidationError(_("Invalid state transition from '%s' to '%s'. Please follow the proper workflow.") % (old_state, new_state))
