# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)


class EnergyAlert(models.Model):
    _name = 'facilities.energy.alert'
    _description = 'Energy Alert'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'alert_date desc, priority desc'

    # Standard Odoo fields
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company, 
                                tracking=True, index=True)

    # Basic Information
    name = fields.Char(string='Alert Name', required=True, tracking=True)
    alert_code = fields.Char(string='Alert Code', required=True, copy=False, 
                           readonly=True, default='New', tracking=True)
    alert_type = fields.Selection([
        ('consumption_spike', 'Consumption Spike'),
        ('threshold_exceeded', 'Threshold Exceeded'),
        ('meter_fault', 'Meter Fault'),
        ('cost_anomaly', 'Cost Anomaly'),
        ('efficiency_decline', 'Efficiency Decline'),
        ('maintenance_due', 'Maintenance Due'),
        ('calibration_overdue', 'Calibration Overdue'),
        ('custom', 'Custom Alert')
    ], string='Alert Type', required=True, tracking=True)
    
    # Alert Details
    alert_date = fields.Datetime(string='Alert Date', required=True, 
                               default=fields.Datetime.now, tracking=True)
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Priority', default='medium', required=True, tracking=True)
    
    # Related Objects
    meter_id = fields.Many2one('facilities.utility.meter', string='Meter', 
                             tracking=True, ondelete='cascade')
    facility_id = fields.Many2one('facilities.facility', string='Facility', 
                                related='meter_id.facility_id', store=True)
    consumption_reading_id = fields.Many2one('facilities.energy.consumption', 
                                           string='Related Reading', 
                                           tracking=True, ondelete='set null')
    
    # Alert Status
    state = fields.Selection([
        ('new', 'New'),
        ('acknowledged', 'Acknowledged'),
        ('investigating', 'Under Investigation'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('false_positive', 'False Positive')
    ], string='Status', default='new', tracking=True, required=True)
    
    # Alert Content
    description = fields.Text(string='Description', required=True, tracking=True)
    detected_value = fields.Float(string='Detected Value', digits=(16, 2), tracking=True)
    threshold_value = fields.Float(string='Threshold Value', digits=(16, 2), tracking=True)
    variance_percentage = fields.Float(string='Variance (%)', digits=(16, 2), 
                                     compute='_compute_variance', store=True)
    
    # Investigation and Resolution
    assigned_to_id = fields.Many2one('res.users', string='Assigned To', tracking=True)
    investigation_notes = fields.Text(string='Investigation Notes', tracking=True)
    resolution_notes = fields.Text(string='Resolution Notes', tracking=True)
    resolution_date = fields.Datetime(string='Resolution Date', tracking=True)
    resolved_by_id = fields.Many2one('res.users', string='Resolved By', tracking=True)
    
    # Escalation
    escalation_level = fields.Integer(string='Escalation Level', default=0, tracking=True)
    escalation_date = fields.Datetime(string='Escalation Date', tracking=True)
    escalated_to_id = fields.Many2one('res.users', string='Escalated To', tracking=True)
    
    # Auto-resolution
    auto_resolve = fields.Boolean(string='Auto-Resolve', default=False, tracking=True)
    auto_resolve_date = fields.Datetime(string='Auto-Resolve Date', tracking=True)
    
    # Recurrence
    is_recurring = fields.Boolean(string='Recurring Alert', default=False, tracking=True)
    recurrence_pattern = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly')
    ], string='Recurrence Pattern', tracking=True)
    last_occurrence = fields.Datetime(string='Last Occurrence', tracking=True)
    occurrence_count = fields.Integer(string='Occurrence Count', default=1, tracking=True)
    
    # Performance Impact
    estimated_cost_impact = fields.Float(string='Estimated Cost Impact', 
                                       digits=(16, 2), tracking=True)
    estimated_efficiency_loss = fields.Float(string='Estimated Efficiency Loss (%)', 
                                           digits=(16, 2), tracking=True)
    
    # Mail fields for chatter
    message_ids = fields.One2many('mail.message', 'res_id', string='Messages')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('alert_code', 'New') == 'New':
                vals['alert_code'] = self.env['ir.sequence'].next_by_code('facilities.energy.alert') or 'New'
        return super(EnergyAlert, self).create(vals_list)

    @api.depends('detected_value', 'threshold_value')
    def _compute_variance(self):
        for alert in self:
            if alert.threshold_value > 0 and alert.detected_value > 0:
                alert.variance_percentage = ((alert.detected_value - alert.threshold_value) / alert.threshold_value) * 100
            else:
                alert.variance_percentage = 0.0

    def action_acknowledge(self):
        """Acknowledge the alert"""
        for alert in self:
            alert.state = 'acknowledged'
            alert.message_post(
                body=_('Alert acknowledged by %s') % self.env.user.name,
                message_type='notification'
            )

    def action_investigate(self):
        """Start investigation of the alert"""
        for alert in self:
            alert.state = 'investigating'
            alert.assigned_to_id = self.env.user.id
            alert.message_post(
                body=_('Alert investigation started by %s') % self.env.user.name,
                message_type='notification'
            )

    def action_resolve(self):
        """Resolve the alert"""
        for alert in self:
            alert.state = 'resolved'
            alert.resolution_date = fields.Datetime.now()
            alert.resolved_by_id = self.env.user.id
            alert.message_post(
                body=_('Alert resolved by %s') % self.env.user.name,
                message_type='notification'
            )

    def action_close(self):
        """Close the alert"""
        for alert in self:
            alert.state = 'closed'
            alert.message_post(
                body=_('Alert closed by %s') % self.env.user.name,
                message_type='notification'
            )

    def action_false_positive(self):
        """Mark alert as false positive"""
        for alert in self:
            alert.state = 'false_positive'
            alert.resolution_date = fields.Datetime.now()
            alert.resolved_by_id = self.env.user.id
            alert.message_post(
                body=_('Alert marked as false positive by %s') % self.env.user.name,
                message_type='notification'
            )

    def action_escalate(self):
        """Escalate the alert"""
        for alert in self:
            alert.escalation_level += 1
            alert.escalation_date = fields.Datetime.now()
            alert.escalated_to_id = alert.assigned_to_id.id if alert.assigned_to_id else False
            alert.message_post(
                body=_('Alert escalated to level %d') % alert.escalation_level,
                message_type='notification'
            )

    def get_alert_summary(self):
        """Get summary of alerts for dashboard"""
        return {
            'total_alerts': self.search_count([]),
            'new_alerts': self.search_count([('state', '=', 'new')]),
            'critical_alerts': self.search_count([('priority', '=', 'critical')]),
            'unresolved_alerts': self.search_count([('state', 'in', ['new', 'acknowledged', 'investigating'])]),
            'alerts_this_month': self.search_count([
                ('alert_date', '>=', fields.Date.today().replace(day=1))
            ])
        }

    @api.constrains('detected_value', 'threshold_value')
    def _check_values(self):
        for alert in self:
            if alert.detected_value < 0 or alert.threshold_value < 0:
                raise ValidationError(_("Values cannot be negative."))

    def _auto_escalate(self):
        """Auto-escalate old unresolved alerts"""
        old_alerts = self.search([
            ('state', 'in', ['new', 'acknowledged']),
            ('alert_date', '<', fields.Datetime.now() - timedelta(hours=24))
        ])
        for alert in old_alerts:
            alert.action_escalate()

    def _auto_resolve_stale_alerts(self):
        """Auto-resolve stale alerts if configured"""
        if not self.env.company.auto_resolve_stale_alerts:
            return
        
        stale_alerts = self.search([
            ('state', 'in', ['new', 'acknowledged']),
            ('alert_date', '<', fields.Datetime.now() - timedelta(days=7))
        ])
        for alert in stale_alerts:
            alert.auto_resolve = True
            alert.auto_resolve_date = fields.Datetime.now()
            alert.state = 'closed'


class EnergyAlertRule(models.Model):
    _name = 'facilities.energy.alert.rule'
    _description = 'Energy Alert Rule'
    _rec_name = 'name'

    name = fields.Char(string='Rule Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
    
    # Rule Configuration
    rule_type = fields.Selection([
        ('consumption_threshold', 'Consumption Threshold'),
        ('cost_threshold', 'Cost Threshold'),
        ('efficiency_threshold', 'Efficiency Threshold'),
        ('meter_status', 'Meter Status'),
        ('maintenance_due', 'Maintenance Due'),
        ('calibration_due', 'Calibration Due')
    ], string='Rule Type', required=True)
    
    # Scope
    meter_type = fields.Selection([
        ('electricity', 'Electricity'),
        ('water', 'Water'),
        ('gas', 'Gas'),
        ('steam', 'Steam'),
        ('cooling', 'Cooling'),
        ('heating', 'Heating'),
        ('all', 'All Types')
    ], string='Meter Type', default='all')
    
    facility_id = fields.Many2one('facilities.facility', string='Facility')
    meter_id = fields.Many2one('facilities.utility.meter', string='Specific Meter')
    
    # Thresholds
    threshold_value = fields.Float(string='Threshold Value', digits=(16, 2))
    threshold_operator = fields.Selection([
        ('greater_than', 'Greater Than'),
        ('less_than', 'Less Than'),
        ('equals', 'Equals'),
        ('greater_equal', 'Greater Than or Equal'),
        ('less_equal', 'Less Than or Equal')
    ], string='Threshold Operator', default='greater_than')
    
    # Alert Configuration
    alert_priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Alert Priority', default='medium')
    
    alert_template = fields.Text(string='Alert Template', 
                               default='Alert: {rule_name}\nValue: {detected_value}\nThreshold: {threshold_value}')
    
    # Notification
    notify_users = fields.Many2many('res.users', string='Notify Users')
    notify_groups = fields.Many2many('res.groups', string='Notify Groups')
    email_notification = fields.Boolean(string='Email Notification', default=True)
    
    # Recurrence
    check_frequency = fields.Selection([
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly')
    ], string='Check Frequency', default='daily')
    
    # Auto-resolution
    auto_resolve_after_hours = fields.Integer(string='Auto-Resolve After (Hours)', default=0)
    
    def evaluate_rule(self):
        """Evaluate the rule and create alerts if conditions are met"""
        for rule in self:
            if not rule.active:
                continue
                
            # Get relevant meters
            meter_domain = []
            if rule.meter_type != 'all':
                meter_domain.append(('meter_type', '=', rule.meter_type))
            if rule.facility_id:
                meter_domain.append(('facility_id', '=', rule.facility_id.id))
            if rule.meter_id:
                meter_domain.append(('id', '=', rule.meter_id.id))
            
            meters = self.env['facilities.utility.meter'].search(meter_domain)
            
            for meter in meters:
                self._check_meter_against_rule(meter, rule)

    def _check_meter_against_rule(self, meter, rule):
        """Check if a meter violates the rule"""
        if rule.rule_type == 'consumption_threshold':
            self._check_consumption_threshold(meter, rule)
        elif rule.rule_type == 'cost_threshold':
            self._check_cost_threshold(meter, rule)
        elif rule.rule_type == 'meter_status':
            self._check_meter_status(meter, rule)

    def _check_consumption_threshold(self, meter, rule):
        """Check consumption threshold"""
        # Get recent consumption readings
        recent_readings = self.env['facilities.energy.consumption'].search([
            ('meter_id', '=', meter.id),
            ('reading_date', '>=', fields.Datetime.now() - timedelta(days=1))
        ], limit=1)
        
        if not recent_readings:
            return
            
        reading = recent_readings[0]
        detected_value = reading.consumption
        
        if self._evaluate_threshold(detected_value, rule.threshold_value, rule.threshold_operator):
            self._create_alert(rule, meter, reading, detected_value, 'consumption_spike')

    def _check_cost_threshold(self, meter, rule):
        """Check cost threshold"""
        recent_readings = self.env['facilities.energy.consumption'].search([
            ('meter_id', '=', meter.id),
            ('reading_date', '>=', fields.Datetime.now() - timedelta(days=1))
        ], limit=1)
        
        if not recent_readings:
            return
            
        reading = recent_readings[0]
        detected_value = reading.total_cost
        
        if self._evaluate_threshold(detected_value, rule.threshold_value, rule.threshold_operator):
            self._create_alert(rule, meter, reading, detected_value, 'cost_anomaly')

    def _check_meter_status(self, meter, rule):
        """Check meter status"""
        if meter.state in ['faulty', 'maintenance']:
            self._create_alert(rule, meter, False, 0, 'meter_fault')

    def _evaluate_threshold(self, detected_value, threshold_value, operator):
        """Evaluate threshold condition"""
        if operator == 'greater_than':
            return detected_value > threshold_value
        elif operator == 'less_than':
            return detected_value < threshold_value
        elif operator == 'equals':
            return detected_value == threshold_value
        elif operator == 'greater_equal':
            return detected_value >= threshold_value
        elif operator == 'less_equal':
            return detected_value <= threshold_value
        return False

    def _create_alert(self, rule, meter, reading, detected_value, alert_type):
        """Create alert based on rule violation"""
        # Check if similar alert already exists
        existing_alert = self.env['facilities.energy.alert'].search([
            ('rule_id', '=', rule.id),
            ('meter_id', '=', meter.id),
            ('state', 'in', ['new', 'acknowledged', 'investigating']),
            ('alert_date', '>=', fields.Datetime.now() - timedelta(hours=1))
        ])
        
        if existing_alert:
            return  # Don't create duplicate alerts
            
        alert_vals = {
            'name': f"{rule.name} - {meter.name}",
            'alert_type': alert_type,
            'priority': rule.alert_priority,
            'meter_id': meter.id,
            'consumption_reading_id': reading.id if reading else False,
            'detected_value': detected_value,
            'threshold_value': rule.threshold_value,
            'description': rule.alert_template.format(
                rule_name=rule.name,
                detected_value=detected_value,
                threshold_value=rule.threshold_value,
                meter_name=meter.name
            )
        }
        
        alert = self.env['facilities.energy.alert'].create(alert_vals)
        
        # Send notifications
        if rule.email_notification:
            self._send_notifications(alert, rule)

    def _send_notifications(self, alert, rule):
        """Send notifications for the alert"""
        recipients = []
        
        if rule.notify_users:
            recipients.extend([user.email for user in rule.notify_users if user.email])
        
        if rule.notify_groups:
            for group in rule.notify_groups:
                recipients.extend([user.email for user in group.users if user.email])
        
        if recipients:
            # In a real implementation, you would send emails here
            _logger.info(f"Alert notification sent to: {', '.join(recipients)}")


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    auto_resolve_stale_alerts = fields.Boolean(
        string='Auto-Resolve Stale Alerts',
        default=False,
        help="Automatically resolve alerts that are older than 7 days"
    )
