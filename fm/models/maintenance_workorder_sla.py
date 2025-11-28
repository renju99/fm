# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class MaintenanceWorkOrderSLA(models.Model):
    """Enhanced SLA functionality for maintenance work orders"""
    _name = 'maintenance.workorder.sla.enhanced'
    _description = 'Enhanced Maintenance Work Order SLA'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='SLA Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    priority = fields.Integer(string='Priority', default=10, help="Higher number = higher priority")
    
    # SLA Criteria
    asset_criticality = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Asset Criticality')
    
    maintenance_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection')
    ], string='Maintenance Type')
    
    priority_level = fields.Selection([
        ('0', 'Very Low'),
        ('1', 'Low'),
        ('2', 'Normal'),
        ('3', 'High'),
        ('4', 'Critical')
    ], string='Priority Level')
    
    facility_ids = fields.Many2many('facilities.facility', string='Facilities')
    
    # SLA Timeframes
    response_time_hours = fields.Float(string='Response Time (Hours)', required=True, default=4.0)
    resolution_time_hours = fields.Float(string='Resolution Time (Hours)', required=True, default=24.0)
    warning_threshold_hours = fields.Float(string='Warning Threshold (Hours)', default=2.0)
    escalation_delay_hours = fields.Float(string='Escalation Delay (Hours)', default=2.0)
    
    # SLA Percentage Thresholds
    warning_threshold = fields.Float(string='Warning Threshold (%)', default=80.0)
    critical_threshold = fields.Float(string='Critical Threshold (%)', default=95.0)
    
    # Escalation Settings
    escalation_enabled = fields.Boolean(string='Enable Escalation', default=True)
    max_escalation_level = fields.Integer(string='Max Escalation Level', default=3)
    escalation_recipients = fields.Many2many('res.users', string='Escalation Recipients')
    
    # Notifications
    email_notifications = fields.Boolean(string='Email Notifications', default=True)
    sms_notifications = fields.Boolean(string='SMS Notifications', default=False)
    notification_template_id = fields.Many2one('mail.template', string='Notification Template')
    
    # Business Hours
    business_hours_only = fields.Boolean(string='Business Hours Only', default=False)
    business_hours_start = fields.Float(string='Business Hours Start', default=9.0)
    business_hours_end = fields.Float(string='Business Hours End', default=17.0)
    business_days = fields.Selection([
        ('weekdays', 'Weekdays Only'),
        ('all_days', 'All Days'),
        ('custom', 'Custom Days')
    ], string='Business Days', default='weekdays')
    
    # KPI Targets
    target_mttr_hours = fields.Float(string='Target MTTR (Hours)')
    target_first_time_fix_rate = fields.Float(string='Target First-Time Fix Rate (%)')
    target_sla_compliance_rate = fields.Float(string='Target SLA Compliance Rate (%)')
    
    # Performance Metrics
    total_workorders = fields.Integer(string='Total Work Orders', compute='_compute_performance_metrics')
    compliant_workorders = fields.Integer(string='Compliant Work Orders', compute='_compute_performance_metrics')
    breached_workorders = fields.Integer(string='Breached Work Orders', compute='_compute_performance_metrics')
    compliance_rate = fields.Float(string='Compliance Rate (%)', compute='_compute_performance_metrics')
    avg_mttr = fields.Float(string='Average MTTR (Hours)', compute='_compute_performance_metrics')

    @api.depends('name')
    def _compute_performance_metrics(self):
        """Compute performance metrics for this SLA"""
        for record in self:
            # Get work orders using this SLA
            workorders = self.env['facilities.workorder'].search([
                ('sla_id', '=', record.id)
            ])
            
            record.total_workorders = len(workorders)
            record.compliant_workorders = len(workorders.filtered(lambda w: w.sla_status == 'on_time'))
            record.breached_workorders = len(workorders.filtered(lambda w: w.sla_status == 'breached'))
            
            if record.total_workorders > 0:
                record.compliance_rate = (record.compliant_workorders / record.total_workorders) * 100
                
                # Calculate average MTTR
                completed_workorders = workorders.filtered(lambda w: w.state == 'completed' and w.actual_duration > 0)
                if completed_workorders:
                    record.avg_mttr = sum(completed_workorders.mapped('actual_duration')) / len(completed_workorders)
                else:
                    record.avg_mttr = 0.0
            else:
                record.compliance_rate = 0.0
                record.avg_mttr = 0.0

    def _calculate_match_score(self, workorder):
        """Calculate match score for this SLA against a work order"""
        score = 0
        
        # Asset criticality match
        if self.asset_criticality and workorder.asset_criticality == self.asset_criticality:
            score += 4
        
        # Maintenance type match
        if self.maintenance_type and workorder.work_order_type == self.maintenance_type:
            score += 3
        
        # Priority match
        if self.priority_level and workorder.priority == self.priority_level:
            score += 2
        
        # Facility match
        if self.facility_ids and workorder.facility_id in self.facility_ids:
            score += 1
        
        return score

    def action_activate_sla(self):
        """Activate this SLA"""
        for record in self:
            record.active = True
            record.activated_by_id = self.env.user.id
            record.activated_date = fields.Datetime.now()
            record.message_post(body=_('SLA activated.'))

    def action_deactivate_sla(self):
        """Deactivate this SLA"""
        for record in self:
            record.active = False
            record.deactivated_by_id = self.env.user.id
            record.deactivated_date = fields.Datetime.now()
            record.message_post(body=_('SLA deactivated.'))

    def action_view_workorders(self):
        """View work orders using this SLA"""
        self.ensure_one()
        return {
            'name': _('Work Orders - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,form',
            'domain': [('sla_id', '=', self.id)],
            'context': {'default_sla_id': self.id}
        }


class MaintenanceWorkOrderEscalation(models.Model):
    """Escalation management for maintenance work orders"""
    _name = 'maintenance.workorder.escalation'
    _description = 'Maintenance Work Order Escalation'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    workorder_id = fields.Many2one('facilities.workorder', string='Work Order', required=True)
    escalation_level = fields.Integer(string='Escalation Level', required=True)
    escalation_type = fields.Selection([
        ('response', 'Response Time'),
        ('resolution', 'Resolution Time'),
        ('both', 'Both Response and Resolution')
    ], string='Escalation Type', required=True)
    
    escalated_to_id = fields.Many2one('res.users', string='Escalated To', required=True)
    escalation_date = fields.Datetime(string='Escalation Date', default=fields.Datetime.now)
    escalation_reason = fields.Text(string='Escalation Reason')
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved')
    ], string='Status', default='pending')
    
    resolution_date = fields.Datetime(string='Resolution Date')
    resolution_notes = fields.Text(string='Resolution Notes')

    def action_acknowledge(self):
        """Acknowledge escalation"""
        for record in self:
            record.status = 'acknowledged'
            record.message_post(body=_('Escalation acknowledged by %s') % self.env.user.name)

    def action_resolve(self):
        """Resolve escalation"""
        for record in self:
            record.status = 'resolved'
            record.resolution_date = fields.Datetime.now()
            record.message_post(body=_('Escalation resolved by %s') % self.env.user.name)
