# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class MaintenanceWorkOrderCore(models.Model):
    """Core maintenance work order model with essential fields and functionality"""
    _name = 'facilities.workorder.core'
    _description = 'Core Maintenance Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, id desc'

    # Basic Information
    name = fields.Char(string='Work Order', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    title = fields.Char(string='Title', required=True, tracking=True)
    description = fields.Html(string='Description', required=False)
    
    # Asset and Location
    asset_id = fields.Many2one('facilities.asset', string='Asset', tracking=True, 
                              ondelete='restrict', help='Select for equipment-specific work orders')
    asset_tag = fields.Char(string='Asset Tag', readonly=True, tracking=True,
                           help='Asset tag from the selected asset')
    serial_number = fields.Char(string='Serial Number', readonly=True, tracking=True,
                               help='Serial number from the selected asset')
    asset_category_id = fields.Many2one('facilities.asset.category', string='Asset Category', 
                                       readonly=True, tracking=True, help='Asset category from the selected asset')
    
    # Location fields
    facility_id = fields.Many2one('facilities.facility', string='Facility', tracking=True)
    building_id = fields.Many2one('facilities.building', string='Building', tracking=True)
    floor_id = fields.Many2one('facilities.floor', string='Floor', tracking=True)
    room_id = fields.Many2one('facilities.room', string='Room', tracking=True)
    
    # Work Order Details
    work_order_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection')
    ], string='Work Order Type', default='corrective', tracking=True)
    
    priority = fields.Selection([
        ('0', 'Very Low'), ('1', 'Low'), ('2', 'Normal'), ('3', 'High'), ('4', 'Critical')
    ], string='Priority', default='2', tracking=True)
    
    asset_criticality = fields.Selection(related='asset_id.criticality', store=True)
    
    # Scheduling
    schedule_id = fields.Many2one('asset.maintenance.schedule', string='Maintenance Schedule', tracking=True)
    start_date = fields.Date(string='Start Date', tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)
    estimated_duration = fields.Float(string='Estimated Duration (Hours)', tracking=True)
    
    # Time Tracking
    actual_start_date = fields.Datetime(string='Actual Start Date', tracking=True)
    actual_end_date = fields.Datetime(string='Actual End Date', tracking=True)
    actual_duration = fields.Float(string='Actual Duration (Hours)', compute='_compute_actual_duration', store=True)
    
    # Assignment
    technician_id = fields.Many2one('hr.employee', string='Technician', tracking=True,
                                   domain="[('is_technician', '=', True)]")
    team_id = fields.Many2one('maintenance.team', string='Maintenance Team', tracking=True)
    supervisor_id = fields.Many2one('hr.employee', string='Supervisor', tracking=True)
    manager_id = fields.Many2one('hr.employee', string='Manager', tracking=True)
    
    # Service Request Integration
    service_request_id = fields.Many2one('facilities.service.request', string='Service Request',
                                       readonly=True, tracking=True, help='Service request that generated this work order')
    requester_id = fields.Many2one('res.users', string='Requester', tracking=True)
    
    # Cost Tracking
    labor_cost = fields.Monetary(string='Labor Cost', currency_field='currency_id', 
                                 compute='_compute_labor_cost', store=True, tracking=True)
    parts_cost = fields.Monetary(string='Parts Cost', currency_field='currency_id', 
                                compute='_compute_parts_cost', store=True, tracking=True)
    total_cost = fields.Monetary(string='Total Cost', currency_field='currency_id',
                                 compute='_compute_total_cost', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    
    # Assignment tracking
    assignment_ids = fields.One2many('facilities.workorder.assignment', 'workorder_id', string='Technician Assignments')
    total_assignment_hours = fields.Float(string='Total Assignment Hours', 
                                         compute='_compute_total_assignment_hours', store=True)
    total_assignment_labor_cost = fields.Monetary(string='Total Assignment Labor Cost', 
                                                currency_field='currency_id',
                                                compute='_compute_total_assignment_labor_cost', store=True)
    
    # Parts and Materials
    parts_used_ids = fields.One2many('facilities.workorder.part_line', 'workorder_id', string='Parts Used')
    
    # Permits
    permit_ids = fields.One2many('facilities.workorder.permit', 'workorder_id', string='Permits')
    
    # Tasks and Sections
    section_ids = fields.One2many('facilities.workorder.section', 'workorder_id', string='Sections')
    task_ids = fields.One2many('facilities.workorder.task', 'workorder_id', string='Tasks')
    
    # Job Plan Integration
    job_plan_id = fields.Many2one('maintenance.job.plan', string='Job Plan', tracking=True)
    
    # Additional Information
    partner_id = fields.Many2one('res.partner', string='Vendor/Contractor', tracking=True)
    cost_center_id = fields.Many2one('facilities.cost.center', string='Cost Center', tracking=True)
    
    # Computed fields
    can_create_workorder = fields.Boolean(string='Can Create Work Order', compute='_compute_can_create_workorder')
    can_reopen_workorder = fields.Boolean(string='Can Reopen Work Order', compute='_compute_can_reopen_workorder')
    all_tasks_completed = fields.Boolean(string='All Tasks Completed', compute='_compute_all_tasks_completed')
    
    # On-Hold Management
    onhold_reason = fields.Selection([
        ('waiting_materials', 'Waiting for Materials'),
        ('waiting_parts', 'Waiting for Parts'),
        ('waiting_tools', 'Waiting for Tools/Equipment'),
        ('waiting_permits', 'Waiting for Permits/Approvals'),
        ('weather_conditions', 'Weather Conditions'),
        ('safety_concerns', 'Safety Concerns'),
        ('resource_unavailable', 'Resource Unavailable'),
        ('technical_issues', 'Technical Issues'),
        ('customer_request', 'Customer Request'),
        ('other', 'Other')
    ], string='On-Hold Reason', tracking=True, help='Reason for putting work order on hold')
    
    onhold_comment = fields.Text(string='On-Hold Comments', tracking=True, 
                                help='Additional details about why work order is on hold')
    
    onhold_request_date = fields.Datetime(string='On-Hold Request Date', readonly=True)
    onhold_approved_by = fields.Many2one('res.users', string='On-Hold Approved By', readonly=True)
    onhold_approval_date = fields.Datetime(string='On-Hold Approval Date', readonly=True)
    
    # Escalation
    escalation_triggered = fields.Boolean(string='Escalation Triggered', default=False)
    escalation_history = fields.One2many('facilities.escalation.log', 'workorder_id', string='Escalation History')
    
    # Invoice and Financial
    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_count')
    invoice_status = fields.Selection([
        ('no_invoice', 'No Invoice'),
        ('to_invoice', 'To Invoice'),
        ('invoiced', 'Invoiced')
    ], string='Invoice Status', compute='_compute_invoice_status')
    
    # Statistics
    picking_count = fields.Integer(string='Picking Count', compute='_compute_picking_count')
    budget_expense_count = fields.Integer(string='Budget Expense Count', compute='_compute_budget_expense_count')
    
    # UI Helper fields
    show_standalone_tasks = fields.Boolean(string='Show Standalone Tasks', default=False)
    start_date_readonly = fields.Boolean(string='Start Date Readonly', compute='_compute_start_date_readonly')
    sla_dates_readonly = fields.Boolean(string='SLA Dates Readonly', compute='_compute_sla_dates_readonly')
    is_schedule_generated = fields.Boolean(string='Is Schedule Generated', default=False)

    @api.depends('actual_start_date', 'actual_end_date')
    def _compute_actual_duration(self):
        """Compute actual duration in hours"""
        for record in self:
            if record.actual_start_date and record.actual_end_date:
                duration = record.actual_end_date - record.actual_start_date
                record.actual_duration = duration.total_seconds() / 3600.0
            else:
                record.actual_duration = 0.0

    @api.depends('assignment_ids.labor_cost')
    def _compute_labor_cost(self):
        """Compute total labor cost from assignments"""
        for record in self:
            record.labor_cost = sum(record.assignment_ids.mapped('labor_cost'))

    @api.depends('parts_used_ids.total_cost')
    def _compute_parts_cost(self):
        """Compute total parts cost"""
        for record in self:
            record.parts_cost = sum(record.parts_used_ids.mapped('total_cost'))

    @api.depends('labor_cost', 'parts_cost')
    def _compute_total_cost(self):
        """Compute total cost"""
        for record in self:
            record.total_cost = record.labor_cost + record.parts_cost

    @api.depends('assignment_ids.work_hours')
    def _compute_total_assignment_hours(self):
        """Compute total assignment hours"""
        for record in self:
            record.total_assignment_hours = sum(record.assignment_ids.mapped('work_hours'))

    @api.depends('assignment_ids.labor_cost')
    def _compute_total_assignment_labor_cost(self):
        """Compute total assignment labor cost"""
        for record in self:
            record.total_assignment_labor_cost = sum(record.assignment_ids.mapped('labor_cost'))

    @api.depends('service_request_id.state')
    def _compute_can_create_workorder(self):
        """Compute if work order can be created from service request"""
        for record in self:
            record.can_create_workorder = (
                record.service_request_id and 
                record.service_request_id.state == 'in_progress'
            )

    @api.depends('state')
    def _compute_can_reopen_workorder(self):
        """Compute if work order can be reopened"""
        for record in self:
            record.can_reopen_workorder = record.state in ['completed', 'cancelled']

    @api.depends('task_ids.is_done')
    def _compute_all_tasks_completed(self):
        """Compute if all tasks are completed"""
        for record in self:
            if record.task_ids:
                record.all_tasks_completed = all(record.task_ids.mapped('is_done'))
            else:
                record.all_tasks_completed = True

    @api.depends('state')
    def _compute_start_date_readonly(self):
        """Compute if start date should be readonly"""
        for record in self:
            record.start_date_readonly = record.state in ['completed', 'cancelled']

    @api.depends('sla_id')
    def _compute_sla_dates_readonly(self):
        """Compute if SLA dates should be readonly"""
        for record in self:
            record.sla_dates_readonly = bool(record.sla_id)

    def _compute_invoice_count(self):
        """Compute invoice count"""
        for record in self:
            record.invoice_count = len(record.env['account.move'].search([
                ('workorder_id', '=', record.id)
            ]))

    def _compute_invoice_status(self):
        """Compute invoice status"""
        for record in self:
            if record.invoice_count == 0:
                record.invoice_status = 'no_invoice'
            elif record.total_cost > 0 and record.state == 'completed':
                record.invoice_status = 'to_invoice'
            else:
                record.invoice_status = 'invoiced'

    def _compute_picking_count(self):
        """Compute picking count"""
        for record in self:
            record.picking_count = len(record.env['stock.picking'].search([
                ('workorder_id', '=', record.id)
            ]))

    def _compute_budget_expense_count(self):
        """Compute budget expense count"""
        for record in self:
            record.budget_expense_count = 0  # Implement based on budget model

    @api.model
    def create(self, vals):
        """Override create to set sequence and apply SLA"""
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('facilities.workorder') or _('New')
        
        workorder = super().create(vals)
        
        # Apply SLA if auto assignment is enabled
        if workorder.auto_sla_assignment:
            workorder._apply_sla()
        
        return workorder

    def write(self, vals):
        """Override write to handle state transitions"""
        result = super().write(vals)
        
        # Handle state transitions
        if 'state' in vals:
            for record in self:
                record._handle_state_transition(vals['state'])
        
        return result

    def _handle_state_transition(self, new_state):
        """Handle state transition logic"""
        if new_state == 'in_progress' and not self.actual_start_date:
            self.actual_start_date = fields.Datetime.now()
        elif new_state == 'completed' and not self.actual_end_date:
            self.actual_end_date = fields.Datetime.now()

    def action_start_progress(self):
        """Start work order progress"""
        self.ensure_one()
        if self.state not in ['draft', 'assigned']:
            raise UserError(_('Work order must be in draft or assigned state to start.'))
        
        self.write({
            'state': 'in_progress',
            'actual_start_date': fields.Datetime.now()
        })
        self.message_post(body=_('Work order started.'))

    def action_complete(self):
        """Complete work order"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Work order must be in progress to complete.'))
        
        self.write({
            'state': 'completed',
            'actual_end_date': fields.Datetime.now()
        })
        self.message_post(body=_('Work order completed.'))

    def action_put_on_hold(self):
        """Put work order on hold"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Work order must be in progress to put on hold.'))
        
        self.write({
            'state': 'on_hold',
            'onhold_approval_state': 'pending'
        })
        self.message_post(body=_('Work order put on hold.'))

    def action_resume_work(self):
        """Resume work order from hold"""
        self.ensure_one()
        if self.state != 'on_hold':
            raise UserError(_('Work order must be on hold to resume.'))
        
        self.write({
            'state': 'in_progress',
            'onhold_approval_state': 'none'
        })
        self.message_post(body=_('Work order resumed.'))

    def action_reopen_workorder(self):
        """Reopen work order"""
        self.ensure_one()
        if not self.can_reopen_workorder:
            raise UserError(_('Work order cannot be reopened.'))
        
        self.write({
            'state': 'draft',
            'actual_end_date': False
        })
        self.message_post(body=_('Work order reopened.'))

    def action_import_job_plan_tasks(self):
        """Import tasks from job plan"""
        self.ensure_one()
        if not self.job_plan_id:
            raise UserError(_('Please select a Job Plan first.'))
        
        if self.work_order_type != 'preventive':
            raise UserError(_('Job plans can only be imported for preventive maintenance work orders.'))
        
        # Clear existing sections and tasks
        self.section_ids.unlink()
        
        # Import sections and tasks from job plan
        for job_section in self.job_plan_id.section_ids:
            # Create work order section
            wo_section = self.env['facilities.workorder.section'].create({
                'name': job_section.name,
                'sequence': job_section.sequence,
                'workorder_id': self.id,
            })
            
            # Import tasks for this section
            for job_task in job_section.task_ids:
                self.env['facilities.workorder.task'].create({
                    'workorder_id': self.id,
                    'section_id': wo_section.id,
                    'name': job_task.name,
                    'sequence': job_task.sequence,
                    'description': job_task.description,
                    'is_checklist_item': job_task.is_checklist_item,
                    'duration': job_task.duration,
                    'tools_materials': job_task.tools_materials,
                    'frequency_type': job_task.frequency_type,
                })
        
        # Post message about the import
        task_count = sum(len(section.task_ids) for section in self.section_ids)
        self.message_post(
            body=_('Imported %d tasks from Job Plan "%s"') % (task_count, self.job_plan_id.name),
            message_type='notification'
        )

    def action_view_service_request(self):
        """View related service request"""
        self.ensure_one()
        if not self.service_request_id:
            raise UserError(_('No service request associated with this work order.'))
        
        return {
            'name': _('Service Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.service.request',
            'view_mode': 'form',
            'res_id': self.service_request_id.id,
            'target': 'current'
        }

    def action_view_picking(self):
        """View related pickings"""
        self.ensure_one()
        pickings = self.env['stock.picking'].search([('workorder_id', '=', self.id)])
        
        if not pickings:
            raise UserError(_('No pickings found for this work order.'))
        
        return {
            'name': _('Parts Transfers'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('workorder_id', '=', self.id)],
            'target': 'current'
        }

    def action_view_invoices(self):
        """View related invoices"""
        self.ensure_one()
        invoices = self.env['account.move'].search([('workorder_id', '=', self.id)])
        
        if not invoices:
            raise UserError(_('No invoices found for this work order.'))
        
        return {
            'name': _('Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('workorder_id', '=', self.id)],
            'target': 'current'
        }

    def action_view_budget_expenses(self):
        """View related budget expenses"""
        self.ensure_one()
        # Implement based on budget model
        return {
            'name': _('Budget Expenses'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.expense',
            'view_mode': 'list,form',
            'domain': [('workorder_id', '=', self.id)],
            'target': 'current'
        }
