# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class MaintenanceWorkOrderSLAMixin(models.Model):
    """Mixin for SLA-related functionality in maintenance work orders"""
    _name = 'maintenance.workorder.sla.mixin'
    _description = 'Maintenance Work Order SLA Mixin'

    # SLA Fields
    sla_id = fields.Many2one('facilities.sla', string='SLA', tracking=True)
    sla_response_deadline = fields.Datetime(string='SLA Response Deadline', tracking=True)
    sla_resolution_deadline = fields.Datetime(string='SLA Resolution Deadline', tracking=True)
    sla_response_status = fields.Selection([
        ('on_time', 'On Time'),
        ('at_risk', 'At Risk'),
        ('breached', 'Breached')
    ], string='SLA Response Status', compute='_compute_sla_response_status', store=True)
    sla_resolution_status = fields.Selection([
        ('on_time', 'On Time'),
        ('at_risk', 'At Risk'),
        ('breached', 'Breached')
    ], string='SLA Resolution Status', compute='_compute_sla_resolution_status', store=True)
    sla_status = fields.Selection([
        ('on_time', 'On Time'),
        ('at_risk', 'At Risk'),
        ('breached', 'Breached')
    ], string='Overall SLA Status', compute='_compute_sla_status', store=True)

    # SLA Assignment
    auto_sla_assignment = fields.Boolean(string='Auto SLA Assignment', default=True)
    sla_assignment_rule = fields.Selection([
        ('asset_criticality', 'Asset Criticality'),
        ('maintenance_type', 'Maintenance Type'),
        ('priority', 'Priority'),
        ('location', 'Location'),
        ('custom', 'Custom Rule')
    ], string='SLA Assignment Rule', default='asset_criticality')

    @api.depends('sla_response_deadline', 'actual_start_date')
    def _compute_sla_response_status(self):
        """Compute SLA response status based on deadline and actual start date"""
        for record in self:
            if not record.sla_response_deadline:
                record.sla_response_status = 'on_time'
                continue
                
            now = fields.Datetime.now()
            deadline = record.sla_response_deadline
            
            if record.actual_start_date and record.actual_start_date <= deadline:
                record.sla_response_status = 'on_time'
            elif now > deadline:
                record.sla_response_status = 'breached'
            else:
                # Calculate percentage of time elapsed
                total_time = deadline - record.create_date
                elapsed_time = now - record.create_date
                if total_time.total_seconds() > 0:
                    percentage = (elapsed_time.total_seconds() / total_time.total_seconds()) * 100
                    if percentage >= 80:
                        record.sla_response_status = 'at_risk'
                    else:
                        record.sla_response_status = 'on_time'
                else:
                    record.sla_response_status = 'on_time'

    @api.depends('sla_resolution_deadline', 'actual_end_date')
    def _compute_sla_resolution_status(self):
        """Compute SLA resolution status based on deadline and actual end date"""
        for record in self:
            if not record.sla_resolution_deadline:
                record.sla_resolution_status = 'on_time'
                continue
                
            now = fields.Datetime.now()
            deadline = record.sla_resolution_deadline
            
            if record.actual_end_date and record.actual_end_date <= deadline:
                record.sla_resolution_status = 'on_time'
            elif now > deadline:
                record.sla_resolution_status = 'breached'
            else:
                # Calculate percentage of time elapsed
                total_time = deadline - record.create_date
                elapsed_time = now - record.create_date
                if total_time.total_seconds() > 0:
                    percentage = (elapsed_time.total_seconds() / total_time.total_seconds()) * 100
                    if percentage >= 80:
                        record.sla_resolution_status = 'at_risk'
                    else:
                        record.sla_resolution_status = 'on_time'
                else:
                    record.sla_resolution_status = 'on_time'

    @api.depends('sla_response_status', 'sla_resolution_status')
    def _compute_sla_status(self):
        """Compute overall SLA status"""
        for record in self:
            if record.sla_response_status == 'breached' or record.sla_resolution_status == 'breached':
                record.sla_status = 'breached'
            elif record.sla_response_status == 'at_risk' or record.sla_resolution_status == 'at_risk':
                record.sla_status = 'at_risk'
            else:
                record.sla_status = 'on_time'

    def _apply_sla(self):
        """Apply SLA to work order based on assignment rules"""
        for record in self:
            if not record.auto_sla_assignment:
                continue
                
            # Find matching SLA
            sla = self._find_matching_sla()
            if sla:
                record.sla_id = sla.id
                record._set_sla_deadlines()

    def _find_matching_sla(self):
        """Find the most appropriate SLA for this work order"""
        self.ensure_one()
        
        # Get all active SLAs
        slas = self.env['facilities.sla'].search([('active', '=', True)])
        
        if not slas:
            return False
            
        # Score each SLA based on matching criteria
        best_sla = False
        best_score = 0
        
        for sla in slas:
            score = sla._calculate_match_score(self)
            if score > best_score:
                best_score = score
                best_sla = sla
                
        return best_sla

    def _set_sla_deadlines(self):
        """Set SLA response and resolution deadlines"""
        for record in self:
            if not record.sla_id:
                continue
                
            now = fields.Datetime.now()
            
            # Set response deadline
            if record.sla_id.response_time_hours:
                record.sla_response_deadline = now + timedelta(hours=record.sla_id.response_time_hours)
            
            # Set resolution deadline
            if record.sla_id.resolution_time_hours:
                record.sla_resolution_deadline = now + timedelta(hours=record.sla_id.resolution_time_hours)


class MaintenanceWorkOrderStateMixin(models.Model):
    """Mixin for state management in maintenance work orders"""
    _name = 'maintenance.workorder.state.mixin'
    _description = 'Maintenance Work Order State Mixin'

    # State fields
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Work Order Status', default='draft', tracking=True)

    approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Review'),
        ('supervisor', 'Supervisor Review'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
        ('cancelled', 'Cancelled')
    ], string='Approval Workflow Status', default='draft', tracking=True)

    onhold_approval_state = fields.Selection([
        ('none', 'No Request'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='On-Hold Approval Status', default='none', tracking=True)

    # State transition validation
    @api.constrains('state')
    def _check_state_transition(self):
        """Validate state transitions"""
        for record in self:
            if record.id:  # Only check for existing records
                old_state = record._origin.state if record._origin else 'draft'
                if not self._is_valid_state_transition(old_state, record.state):
                    raise ValidationError(_(
                        'Invalid state transition from "%s" to "%s". '
                        'Please check the workflow rules.'
                    ) % (old_state.replace('_', ' ').title(), 
                         record.state.replace('_', ' ').title()))

    def _is_valid_state_transition(self, from_state, to_state):
        """Check if state transition is valid"""
        valid_transitions = {
            'draft': ['assigned', 'cancelled'],
            'assigned': ['in_progress', 'cancelled'],
            'in_progress': ['on_hold', 'completed', 'cancelled'],
            'on_hold': ['in_progress', 'cancelled'],
            'completed': ['cancelled'],  # Allow reopening
            'cancelled': []  # No transitions from cancelled
        }
        
        return to_state in valid_transitions.get(from_state, [])

    def action_start_progress(self):
        """Start work order progress"""
        for record in self:
            if record.state not in ['draft', 'assigned']:
                raise UserError(_('Work order must be in draft or assigned state to start.'))
            
            record.write({
                'state': 'in_progress',
                'actual_start_date': fields.Datetime.now()
            })
            record.message_post(body=_('Work order started.'))

    def action_complete(self):
        """Complete work order"""
        for record in self:
            if record.state != 'in_progress':
                raise UserError(_('Work order must be in progress to complete.'))
            
            record.write({
                'state': 'completed',
                'actual_end_date': fields.Datetime.now()
            })
            record.message_post(body=_('Work order completed.'))

    def action_put_on_hold(self):
        """Put work order on hold"""
        for record in self:
            if record.state != 'in_progress':
                raise UserError(_('Work order must be in progress to put on hold.'))
            
            record.write({
                'state': 'on_hold',
                'onhold_approval_state': 'pending'
            })
            record.message_post(body=_('Work order put on hold.'))

    def action_resume_work(self):
        """Resume work order from hold"""
        for record in self:
            if record.state != 'on_hold':
                raise UserError(_('Work order must be on hold to resume.'))
            
            record.write({
                'state': 'in_progress',
                'onhold_approval_state': 'none'
            })
            record.message_post(body=_('Work order resumed.'))


class MaintenanceWorkOrderValidationMixin(models.Model):
    """Mixin for validation in maintenance work orders"""
    _name = 'maintenance.workorder.validation.mixin'
    _description = 'Maintenance Work Order Validation Mixin'

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        """Validate start and end dates"""
        for record in self:
            if record.start_date and record.end_date and record.end_date < record.start_date:
                raise ValidationError(_('End date cannot be earlier than start date.'))

    @api.constrains('actual_start_date', 'actual_end_date')
    def _check_actual_dates(self):
        """Validate actual start and end dates"""
        for record in self:
            if (record.actual_start_date and record.actual_end_date and 
                record.actual_end_date < record.actual_start_date):
                raise ValidationError(_('Actual end date cannot be earlier than actual start date.'))

    @api.constrains('priority')
    def _check_priority(self):
        """Validate priority field"""
        for record in self:
            if record.priority not in ['0', '1', '2', '3', '4']:
                raise ValidationError(_('Invalid priority value.'))

    @api.constrains('estimated_duration')
    def _check_estimated_duration(self):
        """Validate estimated duration"""
        for record in self:
            if record.estimated_duration and record.estimated_duration < 0:
                raise ValidationError(_('Estimated duration cannot be negative.'))

    def _validate_required_fields(self):
        """Validate required fields based on work order type"""
        for record in self:
            if record.work_order_type == 'preventive' and not record.schedule_id:
                raise ValidationError(_('Preventive work orders must have a maintenance schedule.'))
            
            if record.work_order_type == 'corrective' and not record.asset_id:
                raise ValidationError(_('Corrective work orders must be associated with an asset.'))
