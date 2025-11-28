# models/maintenance_workorder_assignment.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class MaintenanceWorkOrderAssignment(models.Model):
    _name = 'facilities.workorder.assignment'
    _description = 'Maintenance Work Order Technician Assignment'
    _rec_name = 'technician_id' # Display technician name in relation
    _order = 'start_date desc'

    workorder_id = fields.Many2one(
        'facilities.workorder',
        string='Work Order',
        required=True,
        ondelete='cascade' # If work order is deleted, assignments are deleted
    )
    technician_id = fields.Many2one(
        'hr.employee',
        string="Technician",
        required=True
    )
    start_date = fields.Datetime(string="Start Date", default=fields.Datetime.now, required=True)
    end_date = fields.Datetime(string="End Date")
    
    # Work time tracking
    work_hours = fields.Float(string="Work Hours", compute='_compute_work_hours', store=True, help="Total hours worked by this technician")
    work_minutes = fields.Float(string="Work Minutes", compute='_compute_work_minutes', store=True, help="Total minutes worked by this technician")
    
    # Status tracking
    is_active = fields.Boolean(string="Currently Working", compute='_compute_is_active', store=True, help="Indicates if technician is currently working on this task")
    status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('paused', 'Paused')
    ], string="Assignment Status", default='not_started')
    
    # Cost tracking
    hourly_rate = fields.Monetary(string="Hourly Rate", currency_field='currency_id', related='technician_id.hourly_cost', readonly=True)
    labor_cost = fields.Monetary(string="Labor Cost", currency_field='currency_id', compute='_compute_labor_cost', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='workorder_id.currency_id', readonly=True)
    
    # Notes and documentation
    notes = fields.Html(string="Work Notes", help="Notes about the work performed by this technician")
    work_description = fields.Html(string="Work Description", help="Detailed description of work performed")
    
    # Time tracking validation
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.end_date and record.start_date and record.end_date < record.start_date:
                raise ValidationError(_("End date cannot be earlier than start date."))
    
    @api.constrains('workorder_id')
    def _check_workorder_status_for_personnel(self):
        """Ensure personnel can only be added when work order is in progress"""
        for record in self:
            if record.workorder_id and record.workorder_id.state != 'in_progress':
                raise ValidationError(_(
                    "Personnel can only be added to work orders that are 'In Progress'. "
                    "Current status of Work Order '%s' is '%s'. "
                    "Please start the work order first."
                ) % (record.workorder_id.name, record.workorder_id.state.replace('_', ' ').title()))
    
    @api.depends('start_date', 'end_date')
    def _compute_work_hours(self):
        for record in self:
            if record.start_date and record.end_date:
                duration = record.end_date - record.start_date
                record.work_hours = duration.total_seconds() / 3600.0
            else:
                record.work_hours = 0.0
    
    @api.depends('start_date', 'end_date')
    def _compute_work_minutes(self):
        for record in self:
            if record.start_date and record.end_date:
                duration = record.end_date - record.start_date
                record.work_minutes = duration.total_seconds() / 60.0
            else:
                record.work_minutes = 0.0
    
    @api.depends('start_date', 'end_date', 'status')
    def _compute_is_active(self):
        for record in self:
            if record.status == 'in_progress' and record.start_date and not record.end_date:
                record.is_active = True
            else:
                record.is_active = False
    
    @api.depends('work_hours', 'hourly_rate')
    def _compute_labor_cost(self):
        for record in self:
            record.labor_cost = record.work_hours * (record.hourly_rate or 0.0)
    
    def action_start_work(self):
        """Start work for this technician assignment"""
        self.ensure_one()
        if self.status == 'not_started':
            self.write({
                'start_date': fields.Datetime.now(),
                'status': 'in_progress'
            })
        elif self.status == 'paused':
            self.write({
                'start_date': fields.Datetime.now(),
                'status': 'in_progress'
            })
    
    def action_pause_work(self):
        """Pause work for this technician assignment"""
        self.ensure_one()
        if self.status == 'in_progress':
            self.write({
                'end_date': fields.Datetime.now(),
                'status': 'paused'
            })
    
    def action_complete_work(self):
        """Complete work for this technician assignment"""
        self.ensure_one()
        if self.status in ['in_progress', 'paused']:
            self.write({
                'end_date': fields.Datetime.now(),
                'status': 'completed'
            })
    
    def action_resume_work(self):
        """Resume work for this technician assignment"""
        self.ensure_one()
        if self.status == 'paused':
            self.write({
                'start_date': fields.Datetime.now(),
                'status': 'in_progress'
            })

    _sql_constraints = [
        ('unique_technician_per_workorder_date', 'UNIQUE(workorder_id, technician_id, start_date)', 'A technician can only be assigned once to the same work order at the exact same start time. Please adjust the start date/time or add a new assignment.'),
    ]