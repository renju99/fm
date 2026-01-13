# -*- coding: utf-8 -*-
"""Visitor Denial Wizard for Facilities Management.

This wizard handles the visitor access denial process with reasons
and notifications.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class VisitorDenyWizard(models.TransientModel):
    """Wizard for denying visitor access with proper documentation."""

    _name = 'visitor.deny.wizard'
    _description = 'Visitor Access Denial Wizard'

    visitor_id = fields.Many2one(
        'visitor.management',
        string='Visitor',
        required=True,
        readonly=True,
        help="Visitor whose access is being denied"
    )
    
    visitor_number = fields.Char(
        string='Visitor Number',
        related='visitor_id.visitor_number',
        readonly=True
    )
    
    visitor_name = fields.Char(
        string='Visitor Name',
        related='visitor_id.visitor_name',
        readonly=True
    )
    
    host_id = fields.Many2one(
        'res.partner',
        string='Host',
        related='visitor_id.host_id',
        readonly=True
    )
    
    # Denial Information
    denial_reason = fields.Selection([
        ('no_approval', 'Host Did Not Approve'),
        ('security_concern', 'Security Concern'),
        ('no_clearance', 'Insufficient Security Clearance'),
        ('invalid_id', 'Invalid Identification'),
        ('restricted_area', 'Attempting to Access Restricted Area'),
        ('blacklisted', 'Visitor Blacklisted'),
        ('suspicious_behavior', 'Suspicious Behavior'),
        ('incomplete_docs', 'Incomplete Documentation'),
        ('health_screening', 'Failed Health Screening'),
        ('no_appointment', 'No Valid Appointment'),
        ('after_hours', 'Outside Visiting Hours'),
        ('capacity_limit', 'Facility at Capacity'),
        ('emergency', 'Emergency Situation'),
        ('other', 'Other Reason'),
    ], string='Denial Reason',
        required=True,
        help="Primary reason for denying access"
    )
    
    denial_category = fields.Selection([
        ('security', 'Security'),
        ('administrative', 'Administrative'),
        ('health', 'Health & Safety'),
        ('capacity', 'Capacity'),
        ('behavioral', 'Behavioral'),
        ('documentation', 'Documentation'),
    ], string='Denial Category',
        compute='_compute_denial_category',
        store=True,
        help="Category of denial reason"
    )
    
    denial_details = fields.Text(
        string='Detailed Explanation',
        required=True,
        help="Detailed explanation for denial"
    )
    
    # Security Assessment
    security_risk_level = fields.Selection([
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk'),
    ], string='Security Risk Level',
        default='low',
        help="Assessment of security risk posed"
    )
    
    requires_investigation = fields.Boolean(
        string='Requires Further Investigation',
        default=False,
        help="Incident requires security investigation"
    )
    
    # Blacklist
    add_to_blacklist = fields.Boolean(
        string='Add to Blacklist',
        default=False,
        help="Permanently deny future access to this visitor"
    )
    
    blacklist_duration = fields.Selection([
        ('30_days', '30 Days'),
        ('90_days', '90 Days'),
        ('1_year', '1 Year'),
        ('permanent', 'Permanent'),
    ], string='Blacklist Duration',
        help="Duration of blacklist restriction"
    )
    
    blacklist_reason = fields.Text(
        string='Blacklist Reason',
        help="Reason for adding to blacklist"
    )
    
    # Notifications
    notify_host = fields.Boolean(
        string='Notify Host',
        default=True,
        help="Send notification to host about denial"
    )
    
    notify_visitor = fields.Boolean(
        string='Notify Visitor',
        default=True,
        help="Send notification to visitor"
    )
    
    notify_security = fields.Boolean(
        string='Notify Security Team',
        default=False,
        help="Alert security team about this incident"
    )
    
    notify_management = fields.Boolean(
        string='Notify Management',
        default=False,
        help="Alert management about high-risk denial"
    )
    
    # Incident Documentation
    denied_by_id = fields.Many2one(
        'res.users',
        string='Denied By',
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
        help="Security/staff member denying access"
    )
    
    denial_date = fields.Datetime(
        string='Denial Date',
        default=fields.Datetime.now,
        required=True,
        readonly=True
    )
    
    witness_ids = fields.Many2many(
        'res.users',
        string='Witnesses',
        help="Staff members who witnessed the incident"
    )
    
    # Evidence
    photo_evidence = fields.Binary(
        string='Photo Evidence',
        attachment=True,
        help="Photo evidence related to denial"
    )
    
    photo_evidence_filename = fields.Char(
        string='Photo Filename'
    )
    
    video_evidence = fields.Binary(
        string='Video Evidence',
        attachment=True,
        help="Video evidence related to denial"
    )
    
    video_evidence_filename = fields.Char(
        string='Video Filename'
    )
    
    supporting_documents = fields.Binary(
        string='Supporting Documents',
        attachment=True,
        help="Any supporting documents"
    )
    
    supporting_documents_filename = fields.Char(
        string='Document Filename'
    )
    
    # Alternative Actions
    alternative_offered = fields.Boolean(
        string='Alternative Offered',
        default=False,
        help="Alternative solution offered to visitor"
    )
    
    alternative_description = fields.Text(
        string='Alternative Description',
        help="Description of alternative solution offered"
    )
    
    # Follow-up
    follow_up_required = fields.Boolean(
        string='Follow-up Required',
        default=False,
        help="Requires follow-up action"
    )
    
    follow_up_notes = fields.Text(
        string='Follow-up Notes',
        help="Notes about required follow-up actions"
    )
    
    create_incident_report = fields.Boolean(
        string='Create Security Incident Report',
        default=False,
        help="Create formal security incident report"
    )

    @api.depends('denial_reason')
    def _compute_denial_category(self):
        """Automatically categorize denial reason."""
        category_mapping = {
            'security_concern': 'security',
            'no_clearance': 'security',
            'blacklisted': 'security',
            'suspicious_behavior': 'behavioral',
            'invalid_id': 'documentation',
            'incomplete_docs': 'documentation',
            'no_approval': 'administrative',
            'no_appointment': 'administrative',
            'after_hours': 'administrative',
            'health_screening': 'health',
            'capacity_limit': 'capacity',
            'restricted_area': 'security',
            'emergency': 'security',
        }
        
        for record in self:
            record.denial_category = category_mapping.get(
                record.denial_reason,
                'administrative'
            )

    @api.onchange('denial_reason')
    def _onchange_denial_reason(self):
        """Update related fields based on denial reason."""
        high_risk_reasons = [
            'security_concern',
            'blacklisted',
            'suspicious_behavior',
            'restricted_area',
        ]
        
        if self.denial_reason in high_risk_reasons:
            self.security_risk_level = 'high'
            self.notify_security = True
            self.requires_investigation = True
        
        if self.denial_reason == 'health_screening':
            self.notify_management = True
        
        if self.denial_reason in ['blacklisted', 'security_concern']:
            self.create_incident_report = True

    @api.onchange('security_risk_level')
    def _onchange_security_risk_level(self):
        """Update notification flags based on risk level."""
        if self.security_risk_level in ['high', 'critical']:
            self.notify_security = True
            self.notify_management = True
            self.create_incident_report = True

    @api.onchange('add_to_blacklist')
    def _onchange_add_to_blacklist(self):
        """Show blacklist fields when enabled."""
        if self.add_to_blacklist:
            self.blacklist_duration = '90_days'
        else:
            self.blacklist_duration = False
            self.blacklist_reason = False

    @api.constrains('add_to_blacklist', 'blacklist_duration', 'blacklist_reason')
    def _check_blacklist_fields(self):
        """Validate blacklist information."""
        for record in self:
            if record.add_to_blacklist:
                if not record.blacklist_duration:
                    raise ValidationError(_(
                        "Blacklist duration is required when adding to blacklist!"
                    ))
                if not record.blacklist_reason:
                    raise ValidationError(_(
                        "Blacklist reason is required when adding to blacklist!"
                    ))

    def action_confirm_denial(self):
        """Confirm denial and update visitor record."""
        self.ensure_one()
        
        # Update visitor record
        self.visitor_id.write({
            'state': 'denied',
            'host_approval': 'denied',
        })
        
        # Post detailed message to visitor chatter
        message_body = self._prepare_denial_message()
        
        self.visitor_id.message_post(
            body=message_body,
            subject=_("Access Denied"),
            message_type='comment'
        )
        
        # Send notifications
        if self.notify_host:
            self._send_host_notification()
        
        if self.notify_visitor:
            self._send_visitor_notification()
        
        if self.notify_security:
            self._send_security_notification()
        
        if self.notify_management:
            self._send_management_notification()
        
        # Handle blacklist
        if self.add_to_blacklist:
            self._add_to_blacklist()
        
        # Attach evidence
        self._attach_evidence()
        
        # Create incident report if needed
        if self.create_incident_report:
            self._create_incident_report()
        
        # Create follow-up activity if needed
        if self.follow_up_required:
            self._create_follow_up_activity()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Access Denied'),
                'message': _(
                    'Visitor %s has been denied access. '
                    'All notifications have been sent.'
                ) % self.visitor_name,
                'type': 'warning',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }

    def _prepare_denial_message(self):
        """Prepare detailed denial message for chatter."""
        message = _(
            "<p><strong>Access Denied</strong></p>"
            "<ul>"
            "<li><strong>Reason:</strong> %s</li>"
            "<li><strong>Category:</strong> %s</li>"
            "<li><strong>Risk Level:</strong> %s</li>"
            "<li><strong>Denied By:</strong> %s</li>"
            "<li><strong>Date:</strong> %s</li>"
        ) % (
            dict(self._fields['denial_reason'].selection).get(self.denial_reason),
            dict(self._fields['denial_category'].selection).get(self.denial_category),
            dict(self._fields['security_risk_level'].selection).get(
                self.security_risk_level
            ),
            self.denied_by_id.name,
            self.denial_date.strftime('%Y-%m-%d %H:%M:%S'),
        )
        
        if self.denial_details:
            message += _("<li><strong>Details:</strong> %s</li>") % self.denial_details
        
        if self.add_to_blacklist:
            message += _(
                "<li><strong>Blacklisted:</strong> %s</li>"
            ) % dict(self._fields['blacklist_duration'].selection).get(
                self.blacklist_duration
            )
        
        if self.alternative_offered:
            message += _(
                "<li><strong>Alternative Offered:</strong> %s</li>"
            ) % self.alternative_description
        
        message += "</ul>"
        
        return message

    def _send_host_notification(self):
        """Send notification to host."""
        template = self.env.ref(
            'fm.email_template_visitor_denied_host',
            raise_if_not_found=False
        )
        if template and self.host_id.email:
            template.send_mail(self.visitor_id.id, force_send=True)

    def _send_visitor_notification(self):
        """Send notification to visitor."""
        if self.visitor_id.visitor_email:
            template = self.env.ref(
                'fm.email_template_visitor_denied_visitor',
                raise_if_not_found=False
            )
            if template:
                template.send_mail(self.visitor_id.id, force_send=True)

    def _send_security_notification(self):
        """Send notification to security team."""
        security_group = self.env.ref(
            'fm.group_facilities_security',
            raise_if_not_found=False
        )
        if security_group:
            security_users = security_group.users
            for user in security_users:
                self.visitor_id.message_post(
                    body=_(
                        "Security Alert: Visitor %s denied access. "
                        "Reason: %s. Risk Level: %s"
                    ) % (
                        self.visitor_name,
                        dict(self._fields['denial_reason'].selection).get(
                            self.denial_reason
                        ),
                        dict(self._fields['security_risk_level'].selection).get(
                            self.security_risk_level
                        ),
                    ),
                    subject=_("Visitor Access Denied - Security Alert"),
                    partner_ids=user.partner_id.ids,
                    message_type='notification'
                )

    def _send_management_notification(self):
        """Send notification to management."""
        manager_group = self.env.ref(
            'fm.group_facilities_manager',
            raise_if_not_found=False
        )
        if manager_group:
            managers = manager_group.users
            for manager in managers:
                self.visitor_id.message_post(
                    body=_(
                        "Management Alert: High-risk visitor denial. "
                        "Visitor: %s. Reason: %s. Risk Level: %s"
                    ) % (
                        self.visitor_name,
                        dict(self._fields['denial_reason'].selection).get(
                            self.denial_reason
                        ),
                        dict(self._fields['security_risk_level'].selection).get(
                            self.security_risk_level
                        ),
                    ),
                    subject=_("High-Risk Visitor Denial"),
                    partner_ids=manager.partner_id.ids,
                    message_type='notification'
                )

    def _add_to_blacklist(self):
        """Add visitor to blacklist."""
        # Create or update blacklist record (placeholder)
        # In a full implementation, you would have a separate blacklist model
        self.visitor_id.message_post(
            body=_(
                "<p><strong>Visitor Blacklisted</strong></p>"
                "<ul>"
                "<li>Duration: %s</li>"
                "<li>Reason: %s</li>"
                "</ul>"
            ) % (
                dict(self._fields['blacklist_duration'].selection).get(
                    self.blacklist_duration
                ),
                self.blacklist_reason,
            ),
            subject=_("Visitor Blacklisted")
        )

    def _attach_evidence(self):
        """Attach evidence files to visitor record."""
        if self.photo_evidence:
            self.env['ir.attachment'].create({
                'name': self.photo_evidence_filename or 'denial_photo_evidence.jpg',
                'datas': self.photo_evidence,
                'res_model': 'visitor.management',
                'res_id': self.visitor_id.id,
                'description': 'Photo evidence for access denial',
            })
        
        if self.video_evidence:
            self.env['ir.attachment'].create({
                'name': self.video_evidence_filename or 'denial_video_evidence.mp4',
                'datas': self.video_evidence,
                'res_model': 'visitor.management',
                'res_id': self.visitor_id.id,
                'description': 'Video evidence for access denial',
            })
        
        if self.supporting_documents:
            self.env['ir.attachment'].create({
                'name': self.supporting_documents_filename or 'denial_documents.pdf',
                'datas': self.supporting_documents,
                'res_model': 'visitor.management',
                'res_id': self.visitor_id.id,
                'description': 'Supporting documents for access denial',
            })

    def _create_incident_report(self):
        """Create a formal security incident report."""
        # Check if safety incident model exists
        IncidentModel = self.env.get('safety.incident', False)
        if IncidentModel:
            incident = IncidentModel.create({
                'incident_type': 'security',
                'severity': self.security_risk_level,
                'description': _(
                    "Visitor Access Denial\n\n"
                    "Visitor: %s\n"
                    "Reason: %s\n\n"
                    "Details: %s"
                ) % (
                    self.visitor_name,
                    dict(self._fields['denial_reason'].selection).get(
                        self.denial_reason
                    ),
                    self.denial_details,
                ),
                'facility_id': self.visitor_id.facility_id.id,
                'reported_by_id': self.denied_by_id.id,
            })
            
            # Link incident to visitor
            self.visitor_id.message_post(
                body=_(
                    "Security incident report created: %s"
                ) % incident.name_get()[0][1],
                subject=_("Incident Report Created")
            )

    def _create_follow_up_activity(self):
        """Create follow-up activity."""
        self.env['mail.activity'].create({
            'res_id': self.visitor_id.id,
            'res_model_id': self.env['ir.model']._get('visitor.management').id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': _('Follow-up: Visitor Denial'),
            'note': self.follow_up_notes,
            'user_id': self.env.user.id,
            'date_deadline': fields.Date.today(),
        })










