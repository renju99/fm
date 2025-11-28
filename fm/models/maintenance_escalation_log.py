from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class MaintenanceEscalationLog(models.Model):
    _name = 'facilities.escalation.log'
    _description = 'Maintenance Escalation Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Escalation Reference', required=True, copy=False, 
                      readonly=True, default=lambda self: _('New'))
    workorder_id = fields.Many2one('facilities.workorder', string='Work Order', 
                                  required=True, ondelete='cascade', tracking=True)
    escalation_type = fields.Selection([
        ('sla_breach', 'SLA Breach'),
        ('priority_increase', 'Priority Increase'),
        ('technician_unavailable', 'Technician Unavailable'),
        ('resource_shortage', 'Resource Shortage'),
        ('safety_concern', 'Safety Concern'),
        ('quality_issue', 'Quality Issue'),
        ('response_breach', 'Response SLA Breach'),
        ('resolution_breach', 'Resolution SLA Breach'),
        ('progressive', 'Progressive Escalation'),
        ('warning', 'Warning Threshold'),
        ('automatic', 'Automatic Escalation'),
        ('other', 'Other')
    ], string='Escalation Type', required=True, tracking=True)
    
    escalation_level = fields.Integer(string='Escalation Level', default=1, tracking=True)
    
    escalation_reason = fields.Text(string='Escalation Reason', required=True, tracking=True)
    escalated_to_id = fields.Many2one('hr.employee', string='Escalated To', 
                                     tracking=True, help='Employee who received the escalation')
    escalated_by_id = fields.Many2one('hr.employee', string='Escalated By', 
                                     required=False, default=lambda self: self.env.user.employee_id, 
                                     tracking=True)
    escalation_date = fields.Datetime(string='Escalation Date', default=fields.Datetime.now, 
                                     tracking=True)
    resolution_date = fields.Datetime(string='Resolution Date', tracking=True)
    resolution_notes = fields.Text(string='Resolution Notes', tracking=True)
    status = fields.Selection([
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ], string='Status', default='open', tracking=True)
    
    # SLA related fields
    sla_id = fields.Many2one('facilities.sla', string='SLA', related='workorder_id.sla_id', 
                                 store=True, readonly=True)
    sla_deadline = fields.Datetime(string='SLA Deadline', related='workorder_id.sla_deadline', 
                                    store=True, readonly=True)
    sla_status = fields.Selection(string='SLA Status', related='workorder_id.sla_status', 
                                 store=True, readonly=True)
    
    # Company and currency
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 related='company_id.currency_id', readonly=True)
    
    # Computed fields
    escalation_duration = fields.Float(string='Escalation Duration (Hours)', 
                                      compute='_compute_escalation_duration', store=True)
    is_overdue = fields.Boolean(string='Is Overdue', compute='_compute_is_overdue', store=True)
    
    @api.depends('escalation_date', 'resolution_date')
    def _compute_escalation_duration(self):
        """Compute the duration of the escalation in hours"""
        for record in self:
            if record.escalation_date and record.resolution_date:
                duration = (record.resolution_date - record.escalation_date).total_seconds() / 3600
                record.escalation_duration = round(duration, 2)
            else:
                record.escalation_duration = 0.0
    
    @api.depends('escalation_date', 'status')
    def _compute_is_overdue(self):
        """Compute if the escalation is overdue (more than 24 hours without resolution)"""
        for record in self:
            if record.status in ['resolved', 'closed']:
                record.is_overdue = False
            elif record.escalation_date:
                from datetime import datetime, timedelta
                overdue_threshold = datetime.now() - timedelta(hours=24)
                # Ensure escalation_date is a datetime for comparison
                try:
                    record.is_overdue = record.escalation_date < overdue_threshold
                except TypeError:
                    record.is_overdue = False
            else:
                record.is_overdue = False
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate escalation reference numbers"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.escalation.log') or _('New')
        return super().create(vals_list)
    
    def action_resolve(self):
        """Mark escalation as resolved"""
        self.ensure_one()
        self.write({
            'status': 'resolved',
            'resolution_date': fields.Datetime.now()
        })
        self.message_post(body=_('Escalation marked as resolved'))
    
    def action_close(self):
        """Close the escalation"""
        self.ensure_one()
        if not self.resolution_notes:
            raise ValidationError(_('Please provide resolution notes before closing the escalation.'))
        
        self.write({'status': 'closed'})
        self.message_post(body=_('Escalation closed'))
    
    def action_reopen(self):
        """Reopen a closed escalation"""
        self.ensure_one()
        self.write({'status': 'open'})
        self.message_post(body=_('Escalation reopened'))
    
    @api.constrains('escalation_date', 'resolution_date')
    def _check_dates(self):
        """Ensure resolution date is after escalation date"""
        for record in self:
            if record.resolution_date and record.escalation_date:
                if record.resolution_date < record.escalation_date:
                    raise ValidationError(_('Resolution date cannot be before escalation date.'))
    
    @api.constrains('status')
    def _check_status_transitions(self):
        """Ensure valid status transitions"""
        for record in self:
            if record.status == 'resolved' and not record.resolution_date:
                raise ValidationError(_('Resolution date is required when status is set to resolved.'))
    
    def name_get(self):
        """Custom name display for escalation logs"""
        result = []
        for record in self:
            name = f"{record.name} - {record.escalation_type.replace('_', ' ').title()}"
            if record.workorder_id:
                name += f" ({record.workorder_id.name})"
            result.append((record.id, name))
        return result