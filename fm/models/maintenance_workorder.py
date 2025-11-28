from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError, MissingError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime, timedelta
from markupsafe import Markup
import logging
import json
import re

_logger = logging.getLogger(__name__)


class MaintenanceWorkOrder(models.Model):
    _name = 'facilities.workorder'
    _description = 'Facilities Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, id desc'

    name = fields.Char(string='Work Order', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    asset_id = fields.Many2one('facilities.asset', string='Asset', tracking=True, 
                              ondelete='restrict',
                              help='Select for equipment-specific work orders')
    asset_tag = fields.Char(string='Asset Tag', readonly=True, tracking=True,
                           help='Asset tag from the selected asset')
    serial_number = fields.Char(string='Serial Number', readonly=True, tracking=True,
                               help='Serial number from the selected asset')
    asset_category_id = fields.Many2one('facilities.asset.category', string='Asset Category', readonly=True, tracking=True,
                                       help='Asset category from the selected asset')
    schedule_id = fields.Many2one('asset.maintenance.schedule', string='Maintenance Schedule', tracking=True)
    service_request_id = fields.Many2one(
        'facilities.service.request',
        string='Service Request',
        readonly=True,
        tracking=True,
        help='Service request that generated this work order'
    )
    
    # Location fields for location-based work orders (cleaning, security, landscaping, etc.)
    work_location_facility_id = fields.Many2one(
        'facilities.facility',
        string='Work Location - Facility',
        tracking=True,
        ondelete='restrict',
        help='Facility where work will be performed'
    )
    
    work_location_building_id = fields.Many2one(
        'facilities.building',
        string='Work Location - Building',
        tracking=True,
        ondelete='restrict',
        help='Building where work will be performed'
    )
    
    work_location_floor_id = fields.Many2one(
        'facilities.floor',
        string='Work Location - Floor',
        tracking=True,
        ondelete='restrict',
        help='Floor where work will be performed'
    )
    
    work_location_room_id = fields.Many2one(
        'facilities.room',
        string='Work Location - Room',
        tracking=True,
        ondelete='restrict',
        help='Room where work will be performed'
    )
    
    # Financial Management Integration
    cost_center_id = fields.Many2one(
        'facilities.cost.center',
        string='Cost Center',
        required=True,
        tracking=True,
        help='Cost center for this work order'
    )
    
    # Vendor Management Integration (Using Standard Odoo Purchase Module)
    vendor_partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        domain=[('supplier_rank', '>', 0)],
        tracking=True,
        help='Vendor assigned to this work order'
    )
    
    agreement_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        tracking=True,
        help='Related purchase order'
    )
    
    # Computed fields for location display
    work_location_display = fields.Char(
        string='Work Location',
        compute='_compute_work_location_display',
        store=True,
        help='Hierarchical display of work location'
    )
    
    maintenance_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection')
    ], string='Maintenance Type', required=True, default='corrective', tracking=True)
    work_order_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection')
    ], string='Work Order Type', required=True, default='corrective', tracking=True)
    
    # Helper field to determine if this is a schedule-generated preventive workorder
    is_schedule_generated = fields.Boolean(
        string='Schedule Generated',
        compute='_compute_is_schedule_generated',
        store=True,
        help='True if this workorder was generated from a maintenance schedule'
    )

    # Job Plan and Schedule Fields
    job_plan_id = fields.Many2one('maintenance.job.plan', string='Job Plan', 
                                  domain="[('active', '=', True)]",
                                  tracking=True,
                                  help="Select a Job Plan to automatically populate tasks for this work order. "
                                       "Note: Job plans are only available for preventive maintenance work orders.")
    section_ids = fields.One2many('facilities.workorder.section', 'workorder_id', string='Sections')

    # SLA and KPI Fields
    sla_id = fields.Many2one('facilities.sla', string='SLA', tracking=True, required=True, readonly=True, ondelete='restrict')
    sla_deadline = fields.Datetime(string='SLA Deadline', compute='_compute_sla_deadline', store=True)
    sla_status = fields.Selection([
        ('on_time', 'On Time'),
        ('at_risk', 'At Risk'),
        ('breached', 'Breached'),
        ('completed', 'Completed')
    ], string='SLA Status', compute='_compute_sla_status', store=True)
    sla_breach_time = fields.Datetime(string='SLA Breach Time', readonly=True)
    sla_escalation_level = fields.Integer(string='Escalation Level', default=0)

    # KPI Metrics
    mttr = fields.Float(string='MTTR (Hours)', compute='_compute_mttr', store=True)
    first_time_fix = fields.Boolean(string='First Time Fix', default=True)
    downtime_hours = fields.Float(string='Downtime Hours', compute='_compute_downtime_hours', store=True)
    cost_per_workorder = fields.Monetary(string='Cost per Work Order', currency_field='currency_id',
                                         compute='_compute_cost_per_workorder', store=True)
    

    # Time Tracking
    start_date = fields.Date(string='Start Date', tracking=True)
    start_time = fields.Datetime(string='Start Time', tracking=True)
    end_time = fields.Datetime(string='End Time', tracking=True)
    actual_start_date = fields.Datetime(string='Actual Start Date', tracking=True)
    actual_end_date = fields.Datetime(string='Actual End Date', tracking=True)
    actual_duration = fields.Float(string='Actual Duration (Hours)', compute='_compute_actual_duration', store=True)
    estimated_duration = fields.Float(string='Estimated Duration (Hours)', tracking=True)

    # Resource Utilization
    technician_ids = fields.Many2many('hr.employee', string='Assigned Technicians', tracking=True)
    team_id = fields.Many2one('maintenance.team', string='Work Team', tracking=True)
    # skill_requirements = fields.Many2many('hr.skill', string='Required Skills')  # Commented out - hr.skill not available
    # skill_match_score = fields.Float(string='Skill Match Score', compute='_compute_skill_match_score')  # Commented out - depends on hr.skill

    # Cost Tracking
    labor_cost = fields.Monetary(string='Labor Cost', currency_field='currency_id', 
                                 compute='_compute_labor_cost', store=True, tracking=True)
    parts_cost = fields.Monetary(string='Parts Cost', currency_field='currency_id', 
                                compute='_compute_parts_cost', store=True, tracking=True)
    total_cost = fields.Monetary(string='Total Cost', currency_field='currency_id',
                                 compute='_compute_total_cost', store=True)
    
    # Computed fields from assignments
    total_assignment_labor_cost = fields.Monetary(string='Total Assignment Labor Cost', currency_field='currency_id',
                                                  compute='_compute_total_assignment_labor_cost', store=True)
    total_assignment_hours = fields.Float(string='Total Assignment Hours', compute='_compute_total_assignment_hours', store=True)
    total_assignment_minutes = fields.Float(string='Total Assignment Minutes', compute='_compute_total_assignment_minutes', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)

    # Priority and Criticality
    priority = fields.Selection([
        ('0', 'Very Low'), ('1', 'Low'), ('2', 'Normal'), ('3', 'High'), ('4', 'Critical')
    ], string='Priority', default='2', tracking=True)
    asset_criticality = fields.Selection(related='asset_id.criticality', store=True)

    # Dynamic SLA Assignment
    auto_sla_assignment = fields.Boolean(string='Auto SLA Assignment', default=True)
    sla_assignment_rule = fields.Selection([
        ('asset_criticality', 'Asset Criticality'),
        ('maintenance_type', 'Maintenance Type'),
        ('priority', 'Priority'),
        ('location', 'Location'),
        ('custom', 'Custom Rule')
    ], string='SLA Assignment Rule', default='asset_criticality')

    # Escalation Workflow
    escalation_triggered = fields.Boolean(string='Escalation Triggered', default=False)
    escalation_history = fields.One2many('facilities.escalation.log', 'workorder_id', string='Escalation History')
    next_escalation_time = fields.Datetime(string='Next Escalation Time', compute='_compute_next_escalation_time')

    # Additional Fields
    description = fields.Html(string='Description', required=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Work Order Status', default='draft', tracking=True, help='Current operational status of the work order')

    # Approval Workflow
    approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Review'),
        ('supervisor', 'Supervisor Review'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
        ('cancelled', 'Cancelled')
    ], string='Approval Workflow Status', default='draft', tracking=True, help='Current status in the supervisor approval process')

    # Approval Related Fields
    submitted_by_id = fields.Many2one('res.users', string='Submitted By', readonly=True)
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_request_date = fields.Datetime(string='Approval Request Date', readonly=True)
    escalation_deadline = fields.Datetime(string='Escalation Deadline', readonly=True)
    escalation_to_id = fields.Many2one('res.users', string='Escalated To', readonly=True)
    escalation_count = fields.Integer(string='Escalation Count', default=0, readonly=True)

    # On-Hold Management Fields
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
    onhold_approval_state = fields.Selection([
        ('none', 'No Request'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='On-Hold Approval Status', default='none', tracking=True)

    # Additional Work Order Fields
    facility_id = fields.Many2one('facilities.facility', string='Facility', related='asset_id.facility_id', store=True)
    room_id = fields.Many2one('facilities.room', string='Room', related='asset_id.room_id', store=True)
    building_id = fields.Many2one('facilities.building', string='Building', related='asset_id.building_id', store=True)
    floor_id = fields.Many2one('facilities.floor', string='Floor', related='asset_id.floor_id', store=True)
    # Removed lease_id field - workorders don't need lease association
    service_type = fields.Selection([
        ('repair', 'Repair'),
        ('maintenance', 'Maintenance'),
        ('inspection', 'Inspection'),
        ('installation', 'Installation'),
        ('replacement', 'Replacement'),
        ('calibration', 'Calibration'),
        ('testing', 'Testing'),
        ('cleaning', 'Cleaning')
    ], string='Service Type', tracking=True)
    maintenance_team_id = fields.Many2one('maintenance.team', string='Maintenance Team', tracking=True)
    technician_id = fields.Many2one('hr.employee', string='Technician', tracking=True)
    supervisor_id = fields.Many2one('hr.employee', string='Supervisor', tracking=True)
    manager_id = fields.Many2one('hr.employee', string='Manager', tracking=True)
    
    # Financial and Vendor Management Fields - Using Standard Odoo
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        tracking=True,
        compute='_compute_analytic_account',
        store=True,
        readonly=False,
        help='Analytic account for cost tracking - automatically set from cost center'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor Partner',
        domain=[('is_company', '=', True), ('supplier_rank', '>', 0)],
        tracking=True,
        help='Vendor assigned to this work order'
    )
    contract_id = fields.Many2one(
        'facilities.maintenance.contract',
        string='Maintenance Contract',
        tracking=True,
        help='Maintenance contract under which this work order is performed'
    )
    
    # Invoice related fields
    invoice_ids = fields.One2many('account.move', 'workorder_id', string='Invoices')
    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_count')
    invoiced = fields.Boolean(string='Invoiced', compute='_compute_invoiced', store=True)
    invoice_status = fields.Selection([
        ('no', 'Nothing to Invoice'),
        ('to_invoice', 'To Invoice'),
        ('invoiced', 'Fully Invoiced'),
    ], string='Invoice Status', compute='_compute_invoice_status', store=True, default='no')
    
    # Budget expense related fields
    budget_expense_count = fields.Integer(string='Budget Expense Count', compute='_compute_budget_expense_count')
    
    # Permit related fields
    permit_required = fields.Boolean(
        string='Permit Required',
        default=False,
        tracking=True,
        help='Whether this work order requires a work permit'
    )
    
    permit_notes = fields.Text(
        string='Permit Notes',
        help='Notes about permit requirements or status'
    )
    
    permit_ids = fields.One2many(
        'facilities.workorder.permit',
        'workorder_id',
        string='Permits',
        help='Permits associated with this work order'
    )
    
    permit_count = fields.Integer(
        string='Permit Count',
        compute='_compute_permit_count',
        help='Number of permits for this work order'
    )
    
    permit_status = fields.Char(
        string='Permit Status',
        compute='_compute_permit_status',
        help='Overall permit status for this work order'
    )
    
    end_date = fields.Date(string='End Date', tracking=True)
    picking_count = fields.Integer(string='Parts Transfers', compute='_compute_picking_count')
    all_tasks_completed = fields.Boolean(string='All Tasks Completed', compute='_compute_all_tasks_completed')

    # SLA Response and Resolution Fields
    sla_response_deadline = fields.Datetime(string='SLA Response Deadline', compute='_compute_sla_response_deadline',
                                            store=True)
    sla_resolution_deadline = fields.Datetime(string='SLA Resolution Deadline',
                                              compute='_compute_sla_resolution_deadline', store=True)
    sla_response_status = fields.Selection([
        ('on_time', 'On Time'),
        ('at_risk', 'At Risk'),
        ('breached', 'Breached'),
        ('completed', 'Completed')
    ], string='SLA Response Status', compute='_compute_sla_response_status', store=True)
    sla_resolution_status = fields.Selection([
        ('on_time', 'On Time'),
        ('at_risk', 'At Risk'),
        ('breached', 'Breached'),
        ('completed', 'Completed')
    ], string='SLA Resolution Status', compute='_compute_sla_resolution_status', store=True)

    # Work Done and Related Fields
    work_done = fields.Html(string='Work Done', help='Description of work completed')
    action_taken_resolution = fields.Html(
        string='Action Taken/Resolution',
        help='Detailed description of what was done to resolve the issue, including troubleshooting steps and final resolution'
    )
    additional_notes = fields.Html(
        string='Additional Notes',
        help='Free-form text field for any miscellaneous notes during work execution'
    )
    assignment_ids = fields.One2many('facilities.workorder.assignment', 'workorder_id',
                                     string='Technician Assignments')
    parts_used_ids = fields.One2many('facilities.workorder.part_line', 'workorder_id', string='Parts Used')
    permit_ids = fields.One2many('facilities.workorder.permit', 'workorder_id', string='Permits')
    workorder_task_ids = fields.One2many('facilities.workorder.task', 'workorder_id', string='Work Order Tasks')

    # Status field for view compatibility
    status = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True, compute='_compute_status', store=True)

    @api.depends('state')
    def _compute_status(self):
        for record in self:
            record.status = record.state

    @api.depends('schedule_id', 'work_order_type')
    def _compute_is_schedule_generated(self):
        """Determine if workorder was generated from a maintenance schedule"""
        for record in self:
            record.is_schedule_generated = bool(record.schedule_id and record.work_order_type == 'preventive')

    @api.constrains('work_order_type', 'schedule_id')
    def _check_preventive_workorder(self):
        """Ensure preventive workorders can only be created from schedules"""
        for record in self:
            if record.work_order_type == 'preventive' and not record.schedule_id:
                raise UserError(_("Preventive work orders can only be generated from maintenance schedules. Please create a maintenance schedule first."))

    # Assignment completion status fields
    assignment_completion_percentage = fields.Float(
        string='Assignment Completion %',
        compute='_compute_assignment_completion_status',
        store=True,
        help='Percentage of technician assignments that are completed'
    )
    
    assignment_status_summary = fields.Char(
        string='Assignment Status',
        compute='_compute_assignment_completion_status',
        store=True,
        help='Summary of technician assignment statuses'
    )
    
    can_complete_workorder = fields.Boolean(
        string='Can Complete Work Order',
        compute='_compute_assignment_completion_status',
        store=True,
        help='Whether all technician assignments are completed and work order can be closed'
    )

    can_reopen_workorder = fields.Boolean(
        string='Can Reopen Work Order', 
        compute='_compute_can_reopen_workorder',
        store=False,
        help='Whether the current user can reopen this work order'
    )

    show_job_plan_warning = fields.Boolean(
        compute='_compute_show_job_plan_warning',
        string='Show Job Plan Warning'
    )

    # New fields for planned vs. reactive work orders
    is_planned_workorder = fields.Boolean(
        string='Is Planned Work Order',
        compute='_compute_is_planned_workorder',
        store=True,
        help='Indicates if this work order was generated from a maintenance schedule'
    )
    
    reported_by = fields.Many2one(
        'res.users',
        string='Reported By',
        default=lambda self: self.env.user,
        help='User who reported the issue (for reactive work orders)'
    )
    
    planned_start_datetime = fields.Date(
        string='Planned Start Date',
        related='start_date',
        store=False,
        help='Planned start date for planned work orders'
    )
    
    planned_end_datetime = fields.Date(
        string='Planned End Date',
        related='end_date',
        store=False,
        help='Planned end date for planned work orders'
    )
    
    # Computed field to control start_date readonly for PPM work orders
    start_date_readonly = fields.Boolean(
        string='Start Date Read Only',
        compute='_compute_start_date_readonly',
        store=False,
        help='Makes start date read-only for preventive work orders generated from schedules'
    )
    
    standard_operating_procedure = fields.Html(
        string='Standard Operating Procedure (SOP)',
        help='Standard operating procedure or task checklist for planned work orders'
    )
    
    reported_issue = fields.Html(
        string='Reported Issue/Description',
        help='Issue description for reactive work orders'
    )
    
    # Dynamic field behavior flags
    can_edit_asset_location = fields.Boolean(
        string='Can Edit Asset/Location',
        compute='_compute_field_editability',
        help='Whether asset and location fields can be edited'
    )
    
    can_edit_description = fields.Boolean(
        string='Can Edit Description',
        compute='_compute_field_editability',
        help='Whether description fields can be edited'
    )
    
    can_edit_labor_timings = fields.Boolean(
        string='Can Edit Labor/Timings',
        compute='_compute_field_editability',
        help='Whether labor and timing fields can be edited'
    )
    
    # Task count computed fields
    total_task_count = fields.Integer(
        string='Total Tasks',
        compute='_compute_task_counts',
        store=True,
        help='Total number of tasks in this work order'
    )
    
    completed_task_count = fields.Integer(
        string='Completed Tasks',
        compute='_compute_task_counts',
        store=True,
        help='Number of completed tasks in this work order'
    )
    
    pending_task_count = fields.Integer(
        string='Pending Tasks',
        compute='_compute_task_counts',
        store=True,
        help='Number of pending tasks in this work order'
    )
    
    task_completion_percentage = fields.Float(
        string='Task Completion %',
        compute='_compute_task_counts',
        store=True,
        help='Percentage of completed tasks in this work order'
    )
    
    show_standalone_tasks = fields.Boolean(
        string='Show Standalone Tasks',
        compute='_compute_show_standalone_tasks',
        help='Whether to show standalone tasks section'
    )
    
    show_maintenance_tasks = fields.Boolean(
        string='Show Maintenance Tasks',
        compute='_compute_show_maintenance_tasks',
        help='Whether to show the maintenance tasks section (only for preventive workorders from schedules)'
    )
    
    can_edit_parts_materials = fields.Boolean(
        string='Can Edit Parts/Materials',
        compute='_compute_field_editability',
        help='Whether parts and materials fields can be edited'
    )
    
    can_edit_work_summary = fields.Boolean(
        string='Can Edit Work Summary',
        compute='_compute_field_editability',
        help='Whether work summary fields can be edited'
    )

    @api.model_create_multi
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('facilities.workorder') or _('New')

            # Validate contract before any other processing
            if vals.get('contract_id'):
                contract = self.env['facilities.maintenance.contract'].browse(vals['contract_id'])
                if contract.state in ('expired', 'terminated'):
                    raise ValidationError(_(
                        'Cannot create work order for contract "%s" because it is %s. '
                        'Please select an active contract or create work order without contract.'
                    ) % (contract.name, contract.state))
                
                # Check date constraints
                work_date = vals.get('start_date')
                if work_date:
                    work_date = fields.Date.from_string(work_date) if isinstance(work_date, str) else work_date
                else:
                    work_date = fields.Date.today()
                
                if contract.end_date and work_date > contract.end_date:
                    raise ValidationError(_(
                        'Cannot create work order for contract "%s" because the work date (%s) '
                        'is after the contract end date (%s).'
                    ) % (contract.name, work_date, contract.end_date))

            # Auto-assign SLA if enabled
            if vals.get('auto_sla_assignment', True):
                sla_id = self._get_appropriate_sla(vals)
                if not sla_id:
                    raise ValidationError(_("No suitable SLA found for the given priority and facility. Please ensure SLAs are configured for this facility and priority level."))
                vals['sla_id'] = sla_id

        workorders = super().create(vals_list)

        # Set SLA deadline for all created workorders
        for workorder in workorders:
            if workorder.sla_id:
                workorder._compute_sla_deadline()

        return workorders

    def write(self, vals):
        """Override write to handle SLA recalculation and validation."""
        # Prevent asset changes when workorder is in progress or completed
        if 'asset_id' in vals:
            for record in self:
                if record.state == 'in_progress':
                    raise ValidationError(_("Asset cannot be changed when the work order is in progress. Please complete or pause the work order first."))
                elif record.state == 'completed':
                    raise ValidationError(_("Asset cannot be changed when the work order is completed. This is required to maintain data integrity and audit trail."))
        
        # Check if SLA is being manually changed or removed
        if 'sla_id' in vals:
            for record in self:
                # Prevent SLA removal once applied
                if record.sla_id and not vals['sla_id']:
                    raise ValidationError(_("SLA cannot be removed once it has been applied. This is required for audit trail and accountability."))
                # Prevent manual SLA changes
                if record.sla_id and vals['sla_id'] and record.sla_id.id != vals['sla_id']:
                    raise ValidationError(_("SLA cannot be manually changed. It is automatically assigned based on priority and facility."))
        
        # Recalculate SLA if priority or asset changes
        if 'priority' in vals or 'asset_id' in vals:
            for record in self:
                if record.asset_id and record.asset_id.facility_id:
                    new_sla_id = record._get_appropriate_sla({
                        'asset_id': record.asset_id.id,
                        'priority': vals.get('priority', record.priority),
                        'maintenance_type': record.maintenance_type
                    })
                    if new_sla_id and new_sla_id != record.sla_id.id:
                        vals['sla_id'] = new_sla_id
        
        result = super().write(vals)
        
        # Recompute SLA deadline if SLA changed
        if 'sla_id' in vals:
            for record in self:
                if record.sla_id:
                    record._compute_sla_deadline()
        
        return result

    @api.constrains('work_order_type', 'job_plan_id')
    def _check_job_plan_preventive_only(self):
        """Ensure job plans are only assigned to preventive work orders."""
        for record in self:
            if record.job_plan_id and record.work_order_type != 'preventive':
                raise UserError(_("Job plans can only be assigned to preventive maintenance work orders. "
                                "Current work order type: %s") % record.work_order_type)

    @api.constrains('sla_id')
    def _check_sla_assignment(self):
        """Ensure SLA is always assigned and cannot be manually changed or removed."""
        for record in self:
            if not record.sla_id:
                raise ValidationError(_("SLA is mandatory and must be automatically assigned based on priority and facility."))
            
            # Check if this is an update operation and SLA is being changed or removed
            if record._origin.id and record._origin.sla_id:
                if not record.sla_id:
                    raise ValidationError(_("SLA cannot be removed once it has been applied. This is required for audit trail and accountability."))
                elif record._origin.sla_id != record.sla_id:
                    raise ValidationError(_("SLA cannot be manually changed. It is automatically assigned based on priority and facility."))
    
    @api.constrains('asset_id', 'state')
    def _check_asset_change_restrictions(self):
        """Prevent asset changes when workorder is in progress or completed."""
        for record in self:
            if record._origin.id and record._origin.asset_id and record.asset_id != record._origin.asset_id:
                if record.state == 'in_progress' or record._origin.state == 'in_progress':
                    raise ValidationError(_("Asset cannot be changed when the work order is in progress. Please complete or pause the work order first."))
                elif record.state == 'completed' or record._origin.state == 'completed':
                    raise ValidationError(_("Asset cannot be changed when the work order is completed. This is required to maintain data integrity and audit trail."))
    
    @api.constrains('actual_start_date', 'actual_end_date')
    def _check_actual_dates(self):
        """Validate that actual end date is after actual start date."""
        for record in self:
            if record.actual_start_date and record.actual_end_date:
                if record.actual_end_date <= record.actual_start_date:
                    raise ValidationError(_("Actual end date must be after actual start date."))
    
    @api.constrains('state', 'actual_start_date', 'actual_end_date')
    def _check_completed_workorder_requirements(self):
        """Ensure completed workorders have required fields filled for audit trail."""
        for record in self:
            if record.state == 'completed':
                if not record.actual_start_date:
                    raise ValidationError(_("Actual start date is required for completed work orders."))
                if not record.actual_end_date:
                    raise ValidationError(_("Actual end date is required for completed work orders."))
    
    @api.constrains('state')
    def _check_state_transitions(self):
        """Validate state transitions follow business rules."""
        for record in self:
            if record._origin.id:  # Only check for existing records
                old_state = record._origin.state
                new_state = record.state
                
                # Define valid transitions
                valid_transitions = {
                    'draft': ['assigned', 'cancelled'],
                    'assigned': ['in_progress', 'cancelled'],
                    'in_progress': ['on_hold', 'completed', 'cancelled'],
                    'on_hold': ['in_progress', 'cancelled'],
                    'completed': [],  # No transitions from completed
                    'cancelled': []   # No transitions from cancelled
                }
                
                if new_state != old_state and new_state not in valid_transitions.get(old_state, []):
                    raise ValidationError(_("Invalid state transition from '%s' to '%s'. Please follow the proper workflow.") % (old_state, new_state))

    @api.constrains('asset_id', 'priority')
    def _check_sla_availability(self):
        """Ensure that a suitable SLA exists for the given asset and priority combination."""
        for record in self:
            if record.asset_id and record.asset_id.facility_id and record.priority:
                # Check if a suitable SLA exists
                suitable_sla = self.env['facilities.sla'].search([
                    ('active', '=', True),
                    ('facility_ids', 'in', record.asset_id.facility_id.id),
                    ('priority_level', '=', record.priority)
                ], limit=1)
                
                if not suitable_sla:
                    # Try with just facility
                    suitable_sla = self.env['facilities.sla'].search([
                        ('active', '=', True),
                        ('facility_ids', 'in', record.asset_id.facility_id.id)
                    ], limit=1)
                    
                    if not suitable_sla:
                        # Try with just priority
                        suitable_sla = self.env['facilities.sla'].search([
                            ('active', '=', True),
                            ('priority_level', '=', record.priority)
                        ], limit=1)
                        
                        if not suitable_sla:
                            # Try any active SLA
                            suitable_sla = self.env['facilities.sla'].search([
                                ('active', '=', True)
                            ], limit=1)
                            
                            if not suitable_sla:
                                raise ValidationError(_("No suitable SLA found for the given priority and facility. Please ensure SLAs are configured for this facility and priority level."))

    @api.onchange('work_order_type')
    def _onchange_work_order_type(self):
        """Clear job plan when work order type changes from preventive to something else."""
        if self.work_order_type != 'preventive':
            if self.job_plan_id:
                self.job_plan_id = False
                return {
                    'warning': {
                        'title': _('Job Plan Cleared'),
                        'message': _('Job plan has been cleared because this is not a preventive work order. '
                                   'All associated job plan tasks will be lost.')
                    }
                }
        else:
            # If changing to preventive, show info about job plan availability
            if not self.job_plan_id:
                return {
                    'warning': {
                        'title': _('Job Plan Available'),
                        'message': _('You can now assign a job plan to this preventive work order.')
                    }
                }

    @api.onchange('job_plan_id')
    def _onchange_job_plan_id(self):
        """Validate that job plan can only be assigned to preventive work orders."""
        if self.job_plan_id and self.work_order_type != 'preventive':
            self.job_plan_id = False
            return {
                'warning': {
                    'title': _('Invalid Selection'),
                    'message': _('Job plans can only be assigned to preventive work orders.')
                }
            }

    @api.depends('work_location_facility_id', 'work_location_building_id', 'work_location_floor_id', 'work_location_room_id', 'asset_id')
    def _compute_work_location_display(self):
        """Compute hierarchical display name for work location"""
        for record in self:
            location_parts = []
            
            # If asset is specified, use asset location as primary
            if record.asset_id:
                location_parts.append(f"Asset: {record.asset_id.name}")
                if record.asset_id.location != "Location not specified":
                    location_parts.append(f"({record.asset_id.location})")
            else:
                # Build hierarchical location from most specific to most general
                if record.work_location_room_id:
                    location_parts.append(f"Room {record.work_location_room_id.name}")
                if record.work_location_floor_id:
                    location_parts.append(f"Floor {record.work_location_floor_id.name}")
                if record.work_location_building_id:
                    location_parts.append(f"Building {record.work_location_building_id.name}")
                if record.work_location_facility_id:
                    location_parts.append(f"Facility {record.work_location_facility_id.name}")
            
            record.work_location_display = " > ".join(location_parts) if location_parts else "Location not specified"

    @api.constrains('asset_id', 'work_location_facility_id', 'work_location_building_id', 'work_location_floor_id', 'work_location_room_id')
    def _check_asset_or_location(self):
        """Ensure either asset or location is specified"""
        for record in self:
            has_asset = bool(record.asset_id)
            has_location = any([
                record.work_location_facility_id,
                record.work_location_building_id,
                record.work_location_floor_id,
                record.work_location_room_id
            ])
            
            if not has_asset and not has_location:
                raise ValidationError(_('Work order must specify either an asset or a work location.'))

    @api.constrains('contract_id')
    def _check_contract_validity(self):
        """Ensure work orders cannot be created for expired or terminated contracts"""
        for record in self:
            if record.contract_id:
                contract = record.contract_id
                work_date = record.start_date or fields.Date.today()
                
                # Check if contract is in valid state
                if contract.state in ('expired', 'terminated'):
                    raise ValidationError(_(
                        'Cannot create work order for contract "%s" because it is %s. '
                        'Please select an active contract or create work order without contract.'
                    ) % (contract.name, contract.state))
                
                # Check if work order date is within contract period
                if contract.end_date and work_date > contract.end_date:
                    raise ValidationError(_(
                        'Cannot create work order for contract "%s" because the work date (%s) '
                        'is after the contract end date (%s).'
                    ) % (contract.name, work_date, contract.end_date))
                
                if contract.start_date and work_date < contract.start_date:
                    raise ValidationError(_(
                        'Cannot create work order for contract "%s" because the work date (%s) '
                        'is before the contract start date (%s).'
                    ) % (contract.name, work_date, contract.start_date))


    @api.depends('sla_id', 'create_date')
    def _compute_sla_deadline(self):
        for workorder in self:
            try:
                if workorder.create_date and workorder.sla_id and workorder.sla_id.resolution_time_hours:
                    workorder.sla_deadline = workorder.create_date + timedelta(
                        hours=workorder.sla_id.resolution_time_hours)
                else:
                    workorder.sla_deadline = False
            except MissingError:
                workorder.sla_deadline = False

    @api.depends('sla_deadline', 'state', 'end_time')
    def _compute_sla_status(self):
        for workorder in self:
            try:
                if not workorder.sla_deadline or workorder.state == 'completed':
                    workorder.sla_status = 'completed' if workorder.state == 'completed' else 'on_time'
                    continue

                now = fields.Datetime.now()
                time_remaining = (workorder.sla_deadline - now).total_seconds() / 3600

                if workorder.state == 'completed':
                    workorder.sla_status = 'completed'
                elif time_remaining < 0:
                    workorder.sla_status = 'breached'
                    if not workorder.sla_breach_time:
                        workorder.sla_breach_time = now
                elif workorder.sla_id and time_remaining < workorder.sla_id.warning_threshold_hours:
                    workorder.sla_status = 'at_risk'
                else:
                    workorder.sla_status = 'on_time'
            except MissingError:
                workorder.sla_status = 'on_time'

    @api.depends('actual_start_date', 'actual_end_date')
    def _compute_actual_duration(self):
        for workorder in self:
            if workorder.actual_start_date and workorder.actual_end_date:
                duration = (workorder.actual_end_date - workorder.actual_start_date).total_seconds() / 3600
                workorder.actual_duration = duration
            else:
                workorder.actual_duration = 0.0

    @api.depends('actual_duration')
    def _compute_mttr(self):
        for workorder in self:
            workorder.mttr = workorder.actual_duration

    @api.depends('actual_start_date', 'actual_end_date', 'asset_id')
    def _compute_downtime_hours(self):
        for workorder in self:
            if workorder.actual_start_date and workorder.actual_end_date:
                downtime = (workorder.actual_end_date - workorder.actual_start_date).total_seconds() / 3600
                workorder.downtime_hours = downtime
            else:
                workorder.downtime_hours = 0.0

    @api.depends('labor_cost', 'parts_cost')
    def _compute_total_cost(self):
        for workorder in self:
            workorder.total_cost = workorder.labor_cost + workorder.parts_cost

    @api.depends('total_cost')
    def _compute_cost_per_workorder(self):
        for workorder in self:
            workorder.cost_per_workorder = workorder.total_cost

    @api.depends('cost_center_id')
    def _compute_analytic_account(self):
        """Automatically set analytic account from cost center"""
        for workorder in self:
            if workorder.cost_center_id and workorder.cost_center_id.analytic_account_id:
                workorder.analytic_account_id = workorder.cost_center_id.analytic_account_id
            else:
                workorder.analytic_account_id = False
    
    def _compute_invoice_count(self):
        for workorder in self:
            workorder.invoice_count = len(workorder.invoice_ids)
    
    def _compute_budget_expense_count(self):
        for workorder in self:
            expenses = self.env['facilities.budget.expense'].search([
                ('workorder_id', '=', workorder.id)
            ])
            workorder.budget_expense_count = len(expenses)
            _logger.debug('Work order %s has %d budget expenses', workorder.name, len(expenses))
    
    def _compute_permit_count(self):
        for workorder in self:
            workorder.permit_count = len(workorder.permit_ids)
    
    def _compute_permit_status(self):
        for workorder in self:
            if not workorder.permit_required:
                workorder.permit_status = 'Not Required'
            elif not workorder.permit_ids:
                workorder.permit_status = 'Required - Not Created'
            else:
                approved_permits = workorder.permit_ids.filtered(lambda p: p.status == 'approved')
                pending_permits = workorder.permit_ids.filtered(lambda p: p.status in ['requested', 'pending_manager_approval'])
                rejected_permits = workorder.permit_ids.filtered(lambda p: p.status == 'rejected')
                
                if approved_permits:
                    workorder.permit_status = f'Approved ({len(approved_permits)} permits)'
                elif rejected_permits and not pending_permits:
                    workorder.permit_status = f'Rejected ({len(rejected_permits)} permits)'
                elif pending_permits:
                    workorder.permit_status = f'Pending Approval ({len(pending_permits)} permits)'
                else:
                    workorder.permit_status = f'{len(workorder.permit_ids)} permits'
    
    @api.depends('invoice_ids', 'invoice_ids.state')
    def _compute_invoiced(self):
        for workorder in self:
            workorder.invoiced = any(invoice.state == 'posted' for invoice in workorder.invoice_ids)
    
    @api.depends('state', 'partner_id', 'total_cost', 'invoice_ids', 'invoice_ids.state')
    def _compute_invoice_status(self):
        for workorder in self:
            if workorder.state not in ('completed', 'cancelled'):
                workorder.invoice_status = 'no'
            elif any(invoice.state == 'posted' for invoice in workorder.invoice_ids):
                workorder.invoice_status = 'invoiced'
            else:
                workorder.invoice_status = 'to_invoice'
    
    @api.depends('assignment_ids.labor_cost')
    def _compute_labor_cost(self):
        for workorder in self:
            workorder.labor_cost = sum(workorder.assignment_ids.mapped('labor_cost'))
    
    @api.depends('parts_used_ids.total_cost')
    def _compute_parts_cost(self):
        for workorder in self:
            workorder.parts_cost = sum(workorder.parts_used_ids.mapped('total_cost'))
    
    @api.depends('assignment_ids.labor_cost')
    def _compute_total_assignment_labor_cost(self):
        for workorder in self:
            workorder.total_assignment_labor_cost = sum(workorder.assignment_ids.mapped('labor_cost'))
    
    @api.depends('assignment_ids.work_hours')
    def _compute_total_assignment_hours(self):
        for workorder in self:
            workorder.total_assignment_hours = sum(workorder.assignment_ids.mapped('work_hours'))
    
    @api.depends('assignment_ids.work_minutes')
    def _compute_total_assignment_minutes(self):
        for workorder in self:
            workorder.total_assignment_minutes = sum(workorder.assignment_ids.mapped('work_minutes'))

    # @api.depends('technician_ids', 'skill_requirements')
    # def _compute_skill_match_score(self):
    #     # Commented out - depends on hr.skill which is not available
    #     for workorder in self:
    #         if not workorder.technician_ids or not workorder.skill_requirements:
    #             workorder.skill_match_score = 0.0
    #             continue

    #         total_skills = len(workorder.skill_requirements)
    #         matched_skills = 0

    #         for technician in workorder.technician_ids:
    #             technician_skills = technician.skill_ids.mapped('name')
    #             for required_skill in workorder.skill_requirements:
    #                 if required_skill.name in technician_skills:
    #                     matched_skills += 1

    #         workorder.skill_match_score = (matched_skills / total_skills) * 100 if total_skills > 0 else 0.0

    @api.depends('sla_deadline', 'sla_escalation_level')
    def _compute_next_escalation_time(self):
        for workorder in self:
            try:
                if workorder.sla_deadline and workorder.sla_escalation_level < 3:
                    escalation_delay = workorder.sla_id.escalation_delay_hours if workorder.sla_id else 24
                    workorder.next_escalation_time = workorder.sla_deadline + timedelta(hours=escalation_delay)
                else:
                    workorder.next_escalation_time = False
            except MissingError:
                workorder.next_escalation_time = False

    def _get_appropriate_sla(self, vals):
        """Dynamically assign SLA based on priority and facility rules"""
        asset_id = vals.get('asset_id')
        maintenance_type = vals.get('maintenance_type')
        priority = vals.get('priority', '2')

        if not asset_id:
            return False

        asset = self.env['facilities.asset'].browse(asset_id)
        facility_id = asset.facility_id.id if asset.facility_id else False
        
        if not facility_id:
            return False

        # Build domain with priority on facility and priority level
        domain = [
            ('active', '=', True),
            ('facility_ids', 'in', facility_id),
            ('priority_level', '=', priority)
        ]
        
        # Try to find SLA with exact match on facility and priority
        sla = self.env['facilities.sla'].search(domain, limit=1, order='priority desc')
        
        if sla:
            return sla.id
            
        # If no exact match, try with just facility
        domain_facility = [
            ('active', '=', True),
            ('facility_ids', 'in', facility_id)
        ]
        sla = self.env['facilities.sla'].search(domain_facility, limit=1, order='priority desc')
        
        if sla:
            return sla.id
            
        # If still no match, try with just priority level
        domain_priority = [
            ('active', '=', True),
            ('priority_level', '=', priority)
        ]
        sla = self.env['facilities.sla'].search(domain_priority, limit=1, order='priority desc')
        
        if sla:
            return sla.id
            
        # Last resort: get any active SLA
        sla = self.env['facilities.sla'].search([('active', '=', True)], limit=1, order='priority desc')
        
        return sla.id if sla else False

    def action_start_work(self):
        """Start work order and record start time"""
        # Check user permissions
        if not self.env.user.has_group('facilities_management.group_maintenance_technician'):
            raise AccessError(_("Only technicians can start work orders."))
            
        for workorder in self:
            if workorder.state not in ['draft', 'assigned']:
                raise ValidationError(_("Work order can only be started from Draft or Assigned state. Current state: %s") % workorder.state)
            workorder.write({
                'state': 'in_progress',
                'start_time': fields.Datetime.now(),
                'actual_start_date': fields.Datetime.now()
            })
            workorder._check_sla_escalation()

    def action_complete_work(self):
        """Complete work order and record end time"""
        # Check user permissions
        if not self.env.user.has_group('facilities_management.group_maintenance_technician'):
            raise AccessError(_("Only technicians can complete work orders."))
            
        for workorder in self:
            if workorder.state != 'in_progress':
                raise ValidationError(_("Work order can only be completed from In Progress state. Current state: %s") % workorder.state)
            
            # Validate that all technician assignments are complete
            workorder._validate_technician_assignments_complete()
            
            # Set a flag to indicate this is a proper completion through the action
            # Use with_context to modify context instead of direct assignment
            workorder_with_context = workorder.with_context(skip_technician_validation=True)
            
            workorder_with_context.write({
                'state': 'completed',
                'approval_state': 'approved',
                'end_time': fields.Datetime.now(),
                'actual_end_date': fields.Datetime.now()
            })
            workorder._compute_kpis()

    def action_assign_technicians(self):
        """Auto-assign technicians based on skills and availability"""
        for workorder in self:
            if workorder.skill_requirements:
                available_technicians = self.env['hr.employee'].search([
                    ('skill_ids', 'in', workorder.skill_requirements.ids),
                    ('maintenance_team_id', '=', workorder.team_id.id)
                ])

                if available_technicians:
                    workorder.technician_ids = available_technicians[:3]  # Assign up to 3 technicians

    def _check_sla_escalation(self):
        """Enhanced SLA escalation check that considers multiple escalation levels and SLA configuration"""
        for workorder in self:
            if not workorder.sla_id or workorder.state in ['completed', 'cancelled']:
                continue
                
            # Check if escalation is already triggered
            if workorder.escalation_triggered:
                # Check if we need to escalate to next level based on time elapsed
                workorder._check_next_escalation_level()
            else:
                # Check if initial escalation should be triggered
                workorder._check_initial_escalation()
    
    def _check_initial_escalation(self):
        """Check if initial escalation should be triggered based on SLA breach"""
        self.ensure_one()
        
        if not self.sla_id:
            return
            
        current_time = fields.Datetime.now()
        
        # Check response SLA breach
        if (self.sla_response_deadline and 
            isinstance(self.sla_response_deadline, datetime) and
            current_time > self.sla_response_deadline and 
            self.state in ['draft', 'assigned']):
            
            self._trigger_escalation(
                level=1,
                reason=_(
                    "Response SLA Breach\n"
                    "Escalation Type: Response SLA Breach\n"
                    "Reason: Response SLA breached - Response deadline: %s\n"
                    "Current Time: %s\n"
                    "Immediate attention required - Response SLA has been breached."
                ) % (
                    self.sla_response_deadline.strftime("%Y-%m-%d %H:%M"),
                    fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ),
                escalation_type='response_breach'
            )
            return
            
        # Check resolution SLA breach
        if (self.sla_resolution_deadline and 
            isinstance(self.sla_resolution_deadline, datetime) and
            current_time > self.sla_resolution_deadline and 
            self.state not in ['completed', 'cancelled']):
            
            self._trigger_escalation(
                level=1,
                reason=_(
                    "Resolution SLA Breach\n"
                    "Escalation Type: Resolution SLA Breach\n"
                    "Reason: Resolution SLA breached - Resolution deadline: %s\n"
                    "Current Time: %s\n"
                    "Immediate attention required - Resolution SLA has been breached."
                ) % (
                    self.sla_resolution_deadline.strftime("%Y-%m-%d %H:%M"),
                    fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ),
                escalation_type='resolution_breach'
            )
            return
            
        # Check if approaching SLA deadline (warning escalation)
        if self.sla_deadline and isinstance(self.sla_deadline, datetime):
            warning_threshold = self.sla_id.warning_threshold_hours or 2  # Default 2 hours
            warning_time = self.sla_deadline - timedelta(hours=warning_threshold)
            
            if (current_time > warning_time and 
                not self.escalation_triggered and
                self.state not in ['completed', 'cancelled']):
                
                self._trigger_escalation(
                    level=1,
                    reason=_(
                        "SLA Warning Threshold\n"
                        "Escalation Type: Warning Threshold\n"
                        "Reason: Approaching SLA deadline - Warning threshold: %s hours before deadline\n"
                        "SLA Deadline: %s\n"
                        "Current Time: %s\n"
                        "Warning - SLA deadline is approaching. Take action to prevent breach."
                    ) % (
                        warning_threshold,
                        self.sla_deadline.strftime('%Y-%m-%d %H:%M:%S'),
                        fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ),
                    escalation_type='warning'
                )
    
    def _check_next_escalation_level(self):
        """Check if escalation should progress to next level based on time elapsed"""
        self.ensure_one()
        
        if not self.sla_id or not self.escalation_triggered:
            return
            
        current_time = fields.Datetime.now()
        last_escalation = self.escalation_history.sorted('escalation_date', reverse=True)[:1]
        
        if not last_escalation:
            return
            
        last_escalation = last_escalation[0]
        time_since_last_escalation = current_time - last_escalation.escalation_date
        
        # Get escalation intervals from SLA configuration
        escalation_intervals = []
        if self.sla_id.escalation_intervals_hours:
            try:
                escalation_intervals = [int(x.strip()) for x in self.sla_id.escalation_intervals_hours.split(',') if x.strip().isdigit()]
            except (ValueError, AttributeError):
                pass
        
        if not escalation_intervals:
            escalation_intervals = [2, 4, 8]  # Default intervals
        
        # Check if enough time has passed for next escalation level
        last_level = int(getattr(last_escalation, 'escalation_level', 0) or 0)
        if (last_level < len(escalation_intervals) and
            time_since_last_escalation.total_seconds() / 3600 >= escalation_intervals[last_level - 1 if last_level > 0 else 0]):
            
            next_level = last_level + 1
            self._trigger_escalation(
                level=next_level,
                reason=_(
                    "Progressive Escalation\n"
                    "Escalation Type: Progressive Escalation\n"
                    "Reason: Escalation Level %s - %.1f hours since last escalation\n"
                    "Previous Level: %s\n"
                    "Time Since Last Escalation: %.1f hours\n"
                    "Current Time: %s\n"
                    "Progressive escalation triggered due to time elapsed since last escalation."
                ) % (
                    next_level,
                    time_since_last_escalation.total_seconds() / 3600,
                    last_level,
                    time_since_last_escalation.total_seconds() / 3600,
                    fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ),
                escalation_type='progressive'
            )
    
    def _trigger_escalation(self, level, reason, escalation_type='automatic'):
        """Enhanced escalation triggering with better logging and notification"""
        self.ensure_one()
        
        try:
            # Don't escalate if already at max level
            max_escalation_level = self.sla_id.max_escalation_level or 3
            if level > max_escalation_level:
                _logger.warning(f"Escalation level {level} exceeds maximum level {max_escalation_level} for workorder {self.name}")
                return
                
            # Update workorder escalation status
            self.write({
                'escalation_triggered': True,
                'sla_escalation_level': level,
                'escalation_count': self.escalation_count + 1
            })
            
            # Determine escalation recipients based on level and SLA configuration
            escalation_recipients = self._get_escalation_recipients(level)
            
            if not escalation_recipients:
                _logger.warning(f"No escalation recipients found for workorder {self.name} at level {level}")
                # Still create escalation log even without recipients
            
            # Clean the reason text from HTML tags for storage
            clean_reason = reason
            if '<' in reason and '>' in reason:
                import re
                clean_reason = re.sub(r'<[^>]+>', ' ', reason)
                clean_reason = re.sub(r'\s+', ' ', clean_reason).strip()
            
            # Create escalation log with clean text reason
            escalation_log = self.env['facilities.escalation.log'].create({
                'workorder_id': self.id,
                'escalation_level': level,
                'escalation_date': fields.Datetime.now(),
                'escalation_reason': f"SLA Escalation Level {level}: {escalation_type.replace('_', ' ').title()}. {clean_reason}",
                'escalation_type': escalation_type,
                'status': 'open',
                'escalated_by_id': self.env.user.employee_id.id if self.env.user.employee_id else False,
                'escalated_to_id': escalation_recipients[0].id if escalation_recipients else False,
                'resolution_notes': f'Escalation Type: {escalation_type}. SLA: {self.sla_id.name if self.sla_id else "Not defined"}'
            })
            
            # Send notifications to escalation recipients
            if escalation_recipients:
                self._send_escalation_notification(escalation_log, escalation_recipients)
            else:
                _logger.info(f"Escalation log created for workorder {self.name} but no notifications sent (no recipients)")
            
            # Log escalation in workorder chatter with standard format
            escalation_message = f"""🚨 SLA Escalation Level {level} Triggered

Work Order: {self.name}
Asset: {self.asset_id.name if self.asset_id else 'N/A'}
Type: {escalation_type.replace('_', ' ').title()}
Current Status: {dict(self._fields['state'].selection).get(self.state, self.state).title()}
Priority: {dict(self._fields['priority'].selection).get(self.priority, 'N/A')}
Triggered: {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ Automatic escalation due to SLA breach - immediate action required"""
            
            self.message_post(
                body=escalation_message,
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
            
            # Update SLA status if not already breached
            if self.sla_status != 'breached':
                self.sla_status = 'breached'
                self.sla_breach_time = fields.Datetime.now()
                
        except Exception as e:
            # Log the escalation error to chatter with standard format
            error_message = f"""❌ SLA Escalation Error

Error: {str(e)}
Escalation Level: {level}
Type: {escalation_type}
Error Time: {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ Escalation process failed - please check system logs"""
            
            self.message_post(
                body=error_message,
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
            
            # Re-raise the exception to be handled by the calling method
            raise

    def _get_escalation_recipients(self, level):
        """Get escalation recipients based on escalation level and SLA configuration"""
        recipients = []
        
        try:
            # Get recipients from SLA configuration if available
            if self.sla_id and self.sla_id.escalation_recipients:
                recipients.extend(self.sla_id.escalation_recipients)
            
            # Add default recipients based on escalation level with error handling
            group_ids = []
            
            if level == 1:
                # First level: Facility managers and supervisors
                try:
                    group_ids.extend([
                        self.env.ref('facilities_management.group_facility_manager', raise_if_not_found=False),
                        self.env.ref('facilities_management.group_facility_supervisor', raise_if_not_found=False)
                    ])
                except Exception as e:
                    _logger.warning(f"Could not find facility management groups for level 1 escalation: {str(e)}")
                    
            elif level == 2:
                # Second level: Senior managers and facility directors
                try:
                    group_ids.extend([
                        self.env.ref('facilities_management.group_facility_director', raise_if_not_found=False),
                        self.env.ref('facilities_management.group_facility_manager', raise_if_not_found=False)
                    ])
                except Exception as e:
                    _logger.warning(f"Could not find facility management groups for level 2 escalation: {str(e)}")
                    
            elif level >= 3:
                # Third level and above: All facility managers and directors
                try:
                    group_ids.extend([
                        self.env.ref('facilities_management.group_facility_director', raise_if_not_found=False),
                        self.env.ref('facilities_management.group_facility_manager', raise_if_not_found=False)
                    ])
                except Exception as e:
                    _logger.warning(f"Could not find facility management groups for level 3+ escalation: {str(e)}")
            
            # Filter out None values and get valid group IDs
            valid_group_ids = [g.id for g in group_ids if g is not None]
            
            if valid_group_ids:
                group_users = self.env['res.users'].search([
                    ('groups_id', 'in', valid_group_ids)
                ])
                recipients.extend(group_users)
            
            # Fallback: If no recipients found, try to get admin users
            if not recipients:
                _logger.warning(f"No escalation recipients found for level {level}, falling back to admin users")
                admin_users = self.env['res.users'].search([
                    ('groups_id', 'in', [self.env.ref('base.group_system', raise_if_not_found=False).id])
                ], limit=5)
                if admin_users:
                    recipients.extend(admin_users)
            
        except Exception as e:
            _logger.error(f"Error getting escalation recipients for level {level}: {str(e)}")
            # Final fallback: try to get the work order creator or any user
            if self.create_uid:
                recipients.append(self.create_uid)
        
        # Remove duplicates and return unique recipients
        return list(set(recipients))
    
    def _send_escalation_notification(self, escalation_log, recipients):
        """Send escalation notifications to recipients"""
        self.ensure_one()
        
        if not recipients:
            return
            
        # Extract escalation type from escalation_reason HTML
        escalation_type = escalation_log.escalation_type or 'SLA Breach'
        escalation_type_display = escalation_type.replace('_', ' ').title()
        
        # Create clean notification message without nested HTML
        message_body = f"""
<div style="margin: 0; padding: 20px; font-family: Arial, sans-serif; background-color: #f8f9fa;">
    <div style="background-color: #dc3545; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
        <h2 style="margin: 0; color: white;">🚨 SLA Escalation Alert</h2>
        <p style="margin: 10px 0 0 0; opacity: 0.9;">Immediate Action Required</p>
    </div>
    
    <div style="background-color: white; padding: 20px; border-radius: 0 0 8px 8px; border-left: 4px solid #dc3545;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px 0; font-weight: bold; color: #495057;">Work Order:</td>
                <td style="padding: 8px 0; color: #212529;">{self.name}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold; color: #495057;">Asset:</td>
                <td style="padding: 8px 0; color: #212529;">{self.asset_id.name if self.asset_id else 'N/A'}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold; color: #495057;">Escalation Level:</td>
                <td style="padding: 8px 0; color: #212529;">Level {escalation_log.escalation_level}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold; color: #495057;">Escalation Type:</td>
                <td style="padding: 8px 0; color: #212529;">{escalation_type_display}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold; color: #495057;">Current Status:</td>
                <td style="padding: 8px 0; color: #212529;">{dict(self._fields['state'].selection).get(self.state, self.state).title()}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold; color: #495057;">Priority:</td>
                <td style="padding: 8px 0; color: #212529;">{dict(self._fields['priority'].selection).get(self.priority, 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold; color: #495057;">SLA Response Deadline:</td>
                <td style="padding: 8px 0; color: #212529;">{self.sla_response_deadline.strftime('%Y-%m-%d %H:%M:%S') if self.sla_response_deadline else 'N/A'}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold; color: #495057;">SLA Resolution Deadline:</td>
                <td style="padding: 8px 0; color: #212529;">{self.sla_resolution_deadline.strftime('%Y-%m-%d %H:%M:%S') if self.sla_resolution_deadline else 'N/A'}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold; color: #495057;">Triggered At:</td>
                <td style="padding: 8px 0; color: #212529;">{escalation_log.escalation_date.strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
        </table>
        
        <div style="margin-top: 20px; padding: 15px; background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px;">
            <p style="margin: 0; color: #856404; font-weight: bold;">⚠️ Action Required:</p>
            <p style="margin: 5px 0 0 0; color: #856404;">This escalation was automatically triggered due to SLA breach. Please review and take immediate action to resolve this work order.</p>
        </div>
    </div>
</div>
        """
        
        # Create standard Odoo notification message
        chatter_message = f"""🚨 SLA Escalation Alert - Level {escalation_log.escalation_level}

Work Order: {self.name}
Asset: {self.asset_id.name if self.asset_id else 'N/A'}
Escalation Type: {escalation_type_display}
Priority: {dict(self._fields['priority'].selection).get(self.priority, 'N/A')}
Triggered: {escalation_log.escalation_date.strftime('%Y-%m-%d %H:%M:%S')}

⚠️ Immediate action required - SLA breach detected"""
        
        # Send message to all recipients using both chatter and email
        for recipient in recipients:
            try:
                # Send clean chatter notification
                self.message_post(
                    body=chatter_message,
                    partner_ids=[recipient.partner_id.id] if recipient.partner_id else [],
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment'
                )
                
                # Send formal email using template if recipient has email
                if recipient.user_id and recipient.user_id.email:
                    try:
                        escalation_template = self.env.ref('facilities_management.email_template_sla_escalation', raise_if_not_found=False)
                        if escalation_template:
                            escalation_template.with_context(
                                lang=recipient.user_id.lang or 'en_US'
                            ).send_mail(
                                escalation_log.id,
                                force_send=True,
                                email_values={
                                    'email_to': recipient.user_id.email,
                                    'auto_delete': True
                                }
                            )
                            _logger.info(f"SLA escalation email sent to {recipient.name} ({recipient.user_id.email})")
                    except Exception as email_error:
                        _logger.error(f"Failed to send escalation email to {recipient.name}: {str(email_error)}")
                        
            except Exception as e:
                _logger.error(f"Failed to send escalation notification to {recipient.name}: {str(e)}")
        
        # Create activity for escalation recipients
        for recipient in recipients:
            try:
                self.activity_schedule(
                    'facilities_management.mail_activity_escalation',
                    user_id=recipient.user_id.id if recipient.user_id else recipient.id,
                    note=f'SLA Escalation Level {escalation_log.escalation_level} for Work Order {self.name}'
                )
            except Exception as e:
                _logger.error(f"Failed to create escalation activity for {recipient.name}: {str(e)}")

    def _compute_kpis(self):
        for workorder in self:
            if workorder.state == 'completed':
                workorder.mttr = workorder.actual_duration
                previous_workorders = self.search([
                    ('asset_id', '=', workorder.asset_id.id),
                    ('state', '=', 'completed'),
                    ('id', '!=', workorder.id)
                ], order='end_time desc', limit=1)
                if not previous_workorders:
                    workorder.first_time_fix = True
                else:
                    workorder.first_time_fix = False

    @api.model
    def cron_check_sla_breaches(self):
        """Legacy cron method - now calls the enhanced SLA escalation logic"""
        _logger.info("Legacy SLA breach check called - redirecting to enhanced escalation logic")
        return self.cron_auto_escalate_workorders()

    def action_assign_technician(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assign Technician',
            'res_model': 'assign.technician.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_workorder_id': self.id}
        }
    
    def action_add_technician_assignment(self):
        """Add a new technician assignment to the work order"""
        self.ensure_one()
        return {
            'name': _('Add Technician Assignment'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder.assignment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
                'default_start_date': fields.Datetime.now(),
                'default_status': 'not_started'
            }
        }
    
    def action_quick_add_technician(self, technician_id):
        """Quickly add a technician assignment"""
        self.ensure_one()
        if technician_id:
            # Check if technician is already assigned
            existing_assignment = self.assignment_ids.filtered(lambda a: a.technician_id.id == technician_id)
            if not existing_assignment:
                self.env['facilities.workorder.assignment'].create({
                    'workorder_id': self.id,
                    'technician_id': technician_id,
                    'start_date': fields.Datetime.now(),
                    'status': 'not_started'
                })
                return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                    'title': _('Success'),
                    'message': _('Technician added successfully'),
                    'type': 'success'
                }}
            else:
                return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                    'title': _('Warning'),
                    'message': _('Technician is already assigned'),
                    'type': 'warning'
                }}
        return False

    def action_report_downtime(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Report Downtime',
            'res_model': 'asset.downtime.report',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
                'default_asset_id': self.asset_id.id
            }
        }

    def action_mark_done(self):
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_("Work order must be in progress to mark as done."))
        
        # Validate that all technician assignments are complete
        self._validate_technician_assignments_complete()
        
        # Set a flag to indicate this is a proper completion through the action
        # Use with_context to modify context instead of direct assignment
        workorder_with_context = self.with_context(skip_technician_validation=True)
        
        workorder_with_context.write({
            'state': 'completed',
            'approval_state': 'approved',
            'end_time': fields.Datetime.now(),
            'actual_end_date': fields.Datetime.now()
        })
        workorder_with_context._compute_kpis()
        workorder_with_context.message_post(body=_("Work order marked as completed"))
        
        # Return action to reload the page
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_view_service_request(self):
        """View the originating service request"""
        self.ensure_one()
        if self.service_request_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'facilities.service.request',
                'res_id': self.service_request_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_view_picking(self):
        self.ensure_one()
        pickings = self.env['stock.picking'].search([
            ('move_ids.workorder_id', '=', self.id)
        ])
        if not pickings:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Transfers'),
                    'message': _('No stock transfers found for this work order.'),
                    'type': 'warning'
                }
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Stock Transfers',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', pickings.ids)],
            'context': {'search_default_workorder_id': self.id}
        }

    def action_submit_for_approval(self):
        self.ensure_one()
        self.write({
            'approval_state': 'submitted',
            'submitted_by_id': self.env.user.id,
            'approval_request_date': fields.Datetime.now()
        })
        self.message_post(body=_("Work order submitted for approval by %s") % self.env.user.name)

    def action_supervisor_approve(self):
        self.ensure_one()
        self.write({
            'approval_state': 'supervisor',
            'approved_by_id': self.env.user.id
        })
        self.message_post(body=_("Work order approved by supervisor %s") % self.env.user.name)

    def action_manager_approve(self):
        self.ensure_one()
        self.write({
            'approval_state': 'manager',
            'approved_by_id': self.env.user.id
        })
        self.message_post(body=_("Work order approved by manager %s") % self.env.user.name)

    def action_fully_approve(self):
        self.ensure_one()
        self.write({
            'approval_state': 'approved',
            'approved_by_id': self.env.user.id
        })
        self.message_post(body=_("Work order fully approved by %s") % self.env.user.name)

    def action_refuse(self):
        self.ensure_one()
        self.write({
            'approval_state': 'refused',
            'approved_by_id': self.env.user.id
        })
        self.message_post(body=_("Work order refused by %s") % self.env.user.name)

    def action_reset_to_draft(self):
        self.ensure_one()
        self.write({
            'approval_state': 'draft'
        })
        self.message_post(body=_("Work order reset to draft by %s") % self.env.user.name)

    def action_escalate(self):
        self.ensure_one()
        self.write({
            'approval_state': 'escalated',
            'escalation_count': self.escalation_count + 1
        })
        self.message_post(body=_("Work order manually escalated by %s") % self.env.user.name)
    
    def action_refresh_escalation_history(self):
        """Refresh escalation history to ensure all logs are visible"""
        self.ensure_one()
        # Since escalation_history is now a simple One2many field, no refresh needed
        # Return a message to confirm the action
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Escalation History Refreshed'),
                'message': _('Escalation history has been refreshed. Please check the Escalation History tab.'),
                'type': 'info',
                'sticky': False,
            }
        }





    def action_start_progress(self):
        """Start work order - check for permit requirements first"""
        self.ensure_one()
        
        _logger.info('Starting work order %s - Current state: %s, permit_required: %s, permit_count: %d', 
                    self.name, self.state, self.permit_required, len(self.permit_ids))
        
        if self.state not in ['draft', 'assigned']:
            raise UserError(_("Work order must be in draft or assigned state to start. Current state: %s") % self.state)
        
        # Check if there are already approved permits for this work order
        approved_permits = self.permit_ids.filtered(lambda p: p.status == 'approved')
        pending_permits = self.permit_ids.filtered(lambda p: p.status in ['requested', 'pending_manager_approval'])
        all_permits = self.permit_ids
        
        _logger.info('Work order %s permit analysis: approved=%d, pending=%d, total=%d', 
                    self.name, len(approved_permits), len(pending_permits), len(all_permits))
        
        if approved_permits:
            # If approved permits exist, start work order directly
            _logger.info('Found %d approved permits for work order %s, starting directly', 
                        len(approved_permits), self.name)
            
            try:
                self.write({
                    'state': 'in_progress',
                    'actual_start_date': fields.Datetime.now(),
                    'permit_required': True,
                    'permit_notes': f'Using existing approved permits: {", ".join(approved_permits.mapped("name"))}'
                })
                
                self.message_post(
                    body=_("Work order started by %s using existing approved permits: %s") % (
                        self.env.user.name,
                        ", ".join(approved_permits.mapped("name"))
                    )
                )
                
                _logger.info('Successfully started work order %s with approved permits', self.name)
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
                
            except Exception as e:
                _logger.error('Failed to start work order %s: %s', self.name, str(e))
                raise UserError(_('Failed to start work order: %s') % str(e))
        
        # For all other cases (no approved permits), open permit wizard
        else:
            _logger.info('No approved permits for work order %s (permit_required=%s), opening permit wizard', 
                        self.name, self.permit_required)
            
            return {
                'name': _('Start Work Order'),
                'type': 'ir.actions.act_window',
                'res_model': 'facilities.workorder.start.permit.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_workorder_id': self.id,
                }
            }

    def action_quick_start(self):
        """Quick start work order - bypass approval if needed"""
        self.ensure_one()
        if self.state not in ['draft', 'assigned']:
            raise UserError(_("Work order must be in draft or assigned state to quick start."))
        
        # Auto-approve if in draft approval state
        if self.approval_state == 'draft':
            self.write({
                'approval_state': 'approved',
                'approved_by_id': self.env.user.id
            })
        
        self.write({
            'approval_state': 'in_progress',
            'state': 'in_progress',
            'actual_start_date': fields.Datetime.now()
        })
        self.message_post(body=_("Work order quick started by %s (bypassing approval)") % self.env.user.name)

    def action_resume_work(self):
        """Resume work order from on-hold state"""
        self.ensure_one()
        if self.state != 'on_hold':
            raise UserError(_("Work order must be on hold to resume."))
        
        self.write({
            'state': 'in_progress',
            'approval_state': 'in_progress'
        })
        self.message_post(body=_("Work order resumed by %s") % self.env.user.name)

    def action_request_onhold(self):
        """Request to put work order on hold - requires facilities manager approval"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_("Only work orders in progress can be put on hold."))
        
        if not self.onhold_reason:
            raise UserError(_("Please select a reason for putting the work order on hold."))
        
        # Open wizard for on-hold request
        return {
            'name': _('Request On-Hold Approval'),
            'type': 'ir.actions.act_window',
            'res_model': 'workorder.onhold.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
                'default_onhold_reason': self.onhold_reason,
                'default_onhold_comment': self.onhold_comment,
            }
        }

    def action_approve_onhold(self):
        """Approve on-hold request (facilities manager only)"""
        self.ensure_one()
        if not self.env.user.has_group('facilities_management.group_facilities_manager'):
            raise UserError(_("Only facilities managers can approve on-hold requests."))
        
        if self.onhold_approval_state != 'pending':
            raise UserError(_("No pending on-hold request to approve."))
        
        self.write({
            'state': 'on_hold',
            'onhold_approval_state': 'approved',
            'onhold_approved_by': self.env.user.id,
            'onhold_approval_date': fields.Datetime.now()
        })
        self.message_post(body=_("On-hold request approved by %s. Reason: %s") % (
            self.env.user.name, dict(self._fields['onhold_reason'].selection).get(self.onhold_reason)))

    def action_reject_onhold(self):
        """Reject on-hold request (facilities manager only)"""
        self.ensure_one()
        if not self.env.user.has_group('facilities_management.group_facilities_manager'):
            raise UserError(_("Only facilities managers can reject on-hold requests."))
        
        if self.onhold_approval_state != 'pending':
            raise UserError(_("No pending on-hold request to reject."))
        
        self.write({
            'onhold_approval_state': 'rejected',
            'onhold_approved_by': self.env.user.id,
            'onhold_approval_date': fields.Datetime.now()
        })
        self.message_post(body=_("On-hold request rejected by %s") % self.env.user.name)

    def action_complete(self):
        """Mark work order as completed"""
        self.ensure_one()
        
        # Check if work order can be completed
        if self.state in ['completed', 'cancelled']:
            raise UserError(_("Cannot complete a work order that is already %s.") % self.state)
        
        # Validate that all technician assignments are complete
        self._validate_technician_assignments_complete()
        
        # Set a flag to indicate this is a proper completion through the action
        # Use with_context to modify context instead of direct assignment
        workorder_with_context = self.with_context(skip_technician_validation=True)
        
        workorder_with_context.write({
            'state': 'completed',
            'approval_state': 'approved',
            'actual_end_date': fields.Datetime.now(),
        })
        workorder_with_context.message_post(body=_("Work order marked as completed by %s") % self.env.user.name)
        
        # Create budget expenses if cost center is assigned and costs exist
        self._create_budget_expenses('work_order_completion')
        
        # Return action to reload the page
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_complete_disabled(self):
        """Disabled version of action_complete - shows message when work order cannot be completed"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cannot Complete Work Order'),
                'message': _('This work order cannot be completed at this time. Please ensure all technician assignments are completed first.'),
                'type': 'warning',
            }
        }

    def action_reopen_workorder(self):
        """
        Open the reopen wizard for completed work orders.
        Only facilities managers can reopen work orders.
        """
        self.ensure_one()
        
        if self.state != 'completed':
            raise UserError(_("Only completed work orders can be reopened."))
        
        if not self.env.user.has_group('facilities_management.group_facilities_manager'):
            raise UserError(_("Only facilities managers can reopen work orders."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reopen Work Order'),
            'res_model': 'workorder.reopen.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
            }
        }
    

    def action_stop_work(self):
        """Stop work and record the stop time"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_("Only work orders in progress can be stopped."))
        
        self.write({
            'state': 'on_hold',
            'actual_end_date': fields.Datetime.now()
        })
        self.message_post(body=_("Work stopped by %s") % self.env.user.name)

    def action_cancel(self):
        self.ensure_one()
        self.write({
            'approval_state': 'cancelled',
            'state': 'cancelled'
        })
        self.message_post(body=_("Work order cancelled by %s") % self.env.user.name)

    def action_toggle_task_completion(self, task_id):
        """Toggle task completion from mobile view"""
        self.ensure_one()
        task = self.env['facilities.workorder.task'].browse(task_id)
        if task and task.workorder_id == self:
            task.toggle_task_completion()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Task Updated'),
                    'message': _('Task "%s" marked as %s') % (task.name, task.is_done and 'completed' or 'pending'),
                    'type': 'success',
                }
            }
        return False

    @api.depends('section_ids.task_ids.is_done', 'workorder_task_ids.is_done')
    def _compute_all_tasks_completed(self):
        for workorder in self:
            sectioned_tasks = workorder.section_ids.mapped('task_ids')
            flat_tasks = workorder.workorder_task_ids
            all_tasks = sectioned_tasks | flat_tasks
            if not all_tasks:
                workorder.all_tasks_completed = True
            else:
                workorder.all_tasks_completed = all(task.is_done for task in all_tasks if task.is_checklist_item)

    @api.depends('assignment_ids.status')
    def _compute_assignment_completion_status(self):
        """Compute assignment completion status fields"""
        for workorder in self:
            assignments = workorder.assignment_ids
            
            if not assignments:
                workorder.assignment_completion_percentage = 100.0
                workorder.assignment_status_summary = _('No assignments')
                workorder.can_complete_workorder = True
            else:
                completed = assignments.filtered(lambda a: a.status == 'completed')
                in_progress = assignments.filtered(lambda a: a.status == 'in_progress')
                pending = assignments.filtered(lambda a: a.status == 'pending')
                
                completion_percentage = (len(completed) / len(assignments)) * 100.0
                workorder.assignment_completion_percentage = round(completion_percentage, 1)
                
                # Create status summary
                status_parts = []
                if completed:
                    status_parts.append(f"{len(completed)} completed")
                if in_progress:
                    status_parts.append(f"{len(in_progress)} in progress")
                if pending:
                    status_parts.append(f"{len(pending)} pending")
                
                workorder.assignment_status_summary = ', '.join(status_parts)
                workorder.can_complete_workorder = len(in_progress) == 0 and len(pending) == 0

    def _compute_can_reopen_workorder(self):
        """Compute whether the current user can reopen this work order"""
        for workorder in self:
            workorder.can_reopen_workorder = (workorder.state == 'completed' and 
                                            self.env.user.has_group('facilities_management.group_facilities_manager'))

    def _compute_picking_count(self):
        for workorder in self:
            pickings = self.env['stock.picking'].search([
                ('move_ids.workorder_id', '=', workorder.id)
            ])
            workorder.picking_count = len(pickings)

    @api.depends('sla_id', 'create_date')
    def _compute_sla_response_deadline(self):
        for workorder in self:
            try:
                if workorder.sla_id and workorder.create_date:
                    workorder.sla_response_deadline = workorder.create_date + timedelta(
                        hours=workorder.sla_id.response_time_hours)
                else:
                    workorder.sla_response_deadline = False
            except MissingError:
                workorder.sla_response_deadline = False

    @api.depends('sla_id', 'create_date')
    def _compute_sla_resolution_deadline(self):
        for workorder in self:
            try:
                if workorder.sla_id and workorder.create_date:
                    workorder.sla_resolution_deadline = workorder.create_date + timedelta(
                        hours=workorder.sla_id.resolution_time_hours)
                else:
                    workorder.sla_resolution_deadline = False
            except MissingError:
                workorder.sla_resolution_deadline = False

    @api.depends('sla_response_deadline', 'state')
    def _compute_sla_response_status(self):
        for workorder in self:
            try:
                if not workorder.sla_response_deadline:
                    workorder.sla_response_status = 'on_time'
                    continue

                now = fields.Datetime.now()
                time_remaining = (workorder.sla_response_deadline - now).total_seconds() / 3600

                if workorder.state == 'completed':
                    workorder.sla_response_status = 'completed'
                elif time_remaining < 0:
                    workorder.sla_response_status = 'breached'
                elif workorder.sla_id and time_remaining < workorder.sla_id.warning_threshold_hours:
                    workorder.sla_response_status = 'at_risk'
                else:
                    workorder.sla_response_status = 'on_time'
            except MissingError:
                workorder.sla_response_status = 'on_time'

    @api.depends('sla_resolution_deadline', 'state')
    def _compute_sla_resolution_status(self):
        for workorder in self:
            try:
                if not workorder.sla_resolution_deadline:
                    workorder.sla_resolution_status = 'on_time'
                    continue

                now = fields.Datetime.now()
                time_remaining = (workorder.sla_resolution_deadline - now).total_seconds() / 3600

                if workorder.state == 'completed':
                    workorder.sla_resolution_status = 'completed'
                elif time_remaining < 0:
                    workorder.sla_resolution_status = 'breached'
                elif workorder.sla_id and time_remaining < workorder.sla_id.warning_threshold_hours:
                    workorder.sla_resolution_status = 'at_risk'
                else:
                    workorder.sla_resolution_status = 'on_time'
            except MissingError:
                workorder.sla_resolution_status = 'on_time'

    @api.depends('work_order_type', 'job_plan_id')
    def _compute_show_job_plan_warning(self):
        for rec in self:
            rec.show_job_plan_warning = (
                rec.work_order_type == 'preventive' and not rec.job_plan_id
            )

    @api.depends('schedule_id', 'work_order_type')
    def _compute_is_planned_workorder(self):
        """Compute whether this is a planned work order based on schedule_id"""
        for rec in self:
            rec.is_planned_workorder = bool(rec.schedule_id) and rec.work_order_type == 'preventive'

    @api.depends('state', 'is_planned_workorder', 'schedule_id')
    def _compute_field_editability(self):
        """
        Compute field editability based on work order status and type.
        This implements the dynamic field behavior as specified in the requirements.
        """
        for rec in self:
            # Asset and Location fields
            if rec.state == 'draft':
                # In draft state, allow editing for reactive work orders
                rec.can_edit_asset_location = not rec.is_planned_workorder
            elif rec.state == 'in_progress':
                # In progress state, make asset/location read-only to prevent changes mid-task
                rec.can_edit_asset_location = False
            else:
                # In other states (completed, cancelled, etc.), make all fields read-only
                rec.can_edit_asset_location = False

            # Description fields
            if rec.state == 'draft':
                # In draft state, allow editing for reactive work orders
                rec.can_edit_description = not rec.is_planned_workorder
            elif rec.state == 'in_progress':
                # In progress state, make description read-only
                rec.can_edit_description = False
            else:
                rec.can_edit_description = False

            # Labor and Timings fields
            if rec.state == 'in_progress':
                # Only enable labor/timings editing when work is in progress
                rec.can_edit_labor_timings = True
            else:
                rec.can_edit_labor_timings = False

            # Parts and Materials fields
            if rec.state == 'in_progress':
                # Only enable parts/materials editing when work is in progress
                rec.can_edit_parts_materials = True
            else:
                rec.can_edit_parts_materials = False

            # Work Summary fields
            if rec.state == 'in_progress':
                # Allow editing work summary when work is in progress
                rec.can_edit_work_summary = True
            elif rec.state == 'completed':
                # Allow editing work summary when completed (for final notes)
                rec.can_edit_work_summary = True
            else:
                rec.can_edit_work_summary = False

    @api.depends('workorder_task_ids.is_done', 'section_ids.task_ids.is_done')
    def _compute_task_counts(self):
        """
        Compute total and completed task counts for the work order.
        """
        for rec in self:
            # Get all unique tasks (standalone tasks + tasks in sections)
            # Use a set to avoid double counting if a task exists in both places
            all_task_ids = set()
            
            # Add standalone tasks
            for task in rec.workorder_task_ids:
                all_task_ids.add(task.id)
            
            # Add tasks from sections
            if rec.section_ids:
                for section in rec.section_ids:
                    for task in section.task_ids:
                        all_task_ids.add(task.id)
            
            # Get the actual task records
            all_tasks = self.env['facilities.workorder.task'].browse(list(all_task_ids))
            
            # Count total and completed tasks
            total_tasks = len(all_tasks)
            completed_tasks = len([t for t in all_tasks if t.is_done])
            
            rec.total_task_count = total_tasks
            rec.completed_task_count = completed_tasks
            rec.pending_task_count = total_tasks - completed_tasks
            rec.task_completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0

    @api.depends('workorder_task_ids', 'section_ids', 'work_order_type', 'schedule_id')
    def _compute_show_standalone_tasks(self):
        """
        Compute whether to show standalone tasks section.
        Only show tasks for preventive workorders that are created from schedules.
        """
        for rec in self:
            # Only show tasks for preventive workorders created from schedules
            if rec.work_order_type == 'preventive' and rec.schedule_id:
                rec.show_standalone_tasks = bool(rec.workorder_task_ids) and not bool(rec.section_ids)
            else:
                rec.show_standalone_tasks = False

    @api.depends('work_order_type', 'schedule_id', 'job_plan_id')
    def _compute_show_maintenance_tasks(self):
        """
        Compute whether to show the maintenance tasks section.
        Only show for preventive workorders that are created from schedules and have a job plan.
        """
        for rec in self:
            # Only show maintenance tasks for preventive workorders created from schedules with job plans
            rec.show_maintenance_tasks = (
                rec.work_order_type == 'preventive' and 
                rec.schedule_id and 
                rec.job_plan_id
            )

    @api.depends('work_order_type', 'schedule_id', 'is_planned_workorder')
    def _compute_start_date_readonly(self):
        """
        Compute whether the start_date field should be readonly.
        Makes start_date read-only for preventive work orders generated from schedules (PPM).
        """
        for rec in self:
            # Start date should be readonly for preventive work orders generated from schedules
            rec.start_date_readonly = (
                rec.work_order_type == 'preventive' and 
                rec.schedule_id and 
                rec.is_planned_workorder
            )

    # Computed field to control all date fields readonly for SLA work orders
    sla_dates_readonly = fields.Boolean(
        string='SLA Dates Read Only',
        compute='_compute_sla_dates_readonly',
        store=False,
        help='Makes all date fields read-only for work orders with SLA to prevent manipulation'
    )

    @api.depends('sla_id', 'state')
    def _compute_sla_dates_readonly(self):
        """
        Compute whether all date fields should be readonly for SLA work orders.
        Makes all date fields read-only for work orders with SLA to prevent manipulation.
        """
        for rec in self:
            # All date fields should be readonly for work orders with SLA
            # This prevents manipulation of critical timing data for SLA compliance
            rec.sla_dates_readonly = bool(rec.sla_id)

    def action_refresh_tasks(self):
        """Refresh tasks from job plan if they are missing"""
        self.ensure_one()
        if self.job_plan_id and not self.workorder_task_ids:
            # Copy tasks from job plan if they don't exist
            self.env['asset.maintenance.schedule']._copy_job_plan_tasks_to_workorder(
                self.job_plan_id, self
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Tasks Refreshed'),
                    'message': _('Tasks have been refreshed from the job plan.'),
                    'type': 'success',
                }
            }
        return True

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """Override to ensure tasks are loaded when form is opened"""
        result = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        
        if view_type == 'form' and self.env.context.get('mobile_view'):
            # Ensure tasks are loaded for mobile view
            for record in self:
                if record.job_plan_id and not record.workorder_task_ids:
                    record.env['asset.maintenance.schedule']._copy_job_plan_tasks_to_workorder(
                        record.job_plan_id, record
                    )
        
        return result

    def action_load_mobile_tasks(self):
        """Action to load tasks for mobile view"""
        self.ensure_one()
        if self.job_plan_id and not self.workorder_task_ids:
            # Copy tasks from job plan if they don't exist
            self.env['asset.maintenance.schedule']._copy_job_plan_tasks_to_workorder(
                self.job_plan_id, self
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Tasks Loaded'),
                    'message': _('Tasks have been loaded from the job plan for mobile view.'),
                    'type': 'success',
                }
            }
        return True

    @api.model
    def cron_auto_escalate_workorders(self):
        """Enhanced cron job to automatically escalate work orders based on SLA breaches"""
        _logger.info("Starting automatic SLA escalation check for work orders")
        
        try:
            # Check if escalation is enabled globally
            escalation_cron = self.env['ir.cron'].search([
                ('name', '=', 'Auto Escalate Maintenance Work Orders')
            ], limit=1)
            
            if not escalation_cron or not escalation_cron.active:
                _logger.info("SLA escalation cron job is disabled, skipping escalation check")
                return {
                    'escalated_count': 0,
                    'total_checked': 0,
                    'message': 'Escalation cron job is disabled'
                }
            
            # Find ALL work orders that have SLA defined and are not completed/cancelled
            # We let the individual escalation check methods determine if escalation is needed
            workorders = self.search([
                ('state', 'not in', ['completed', 'cancelled']),
                ('sla_id', '!=', False),  # Only work orders with SLA defined
            ])
            
            _logger.info(f"Found {len(workorders)} work orders with SLA for escalation checks")
            
            escalated_count = 0
            checked_count = 0
            
            for workorder in workorders:
                try:
                    checked_count += 1
                    # Check if escalation is needed using the SLA-based logic
                    # This method will determine if escalation should be triggered
                    initial_escalation_count = workorder.escalation_count
                    workorder._check_sla_escalation()
                    
                    # Count as escalated if escalation count increased
                    if workorder.escalation_count > initial_escalation_count:
                        escalated_count += 1
                        _logger.info(f"Escalation triggered for work order {workorder.name}")
                    
                except Exception as e:
                    _logger.error(f"Error checking escalation for work order {workorder.name}: {str(e)}")
                    continue
            
            _logger.info(f"Completed SLA escalation check. {escalated_count} escalations triggered out of {checked_count} work orders checked.")
            
            return {
                'escalated_count': escalated_count,
                'total_checked': checked_count
            }
            
        except Exception as e:
            _logger.error(f"Error in SLA escalation cron: {str(e)}")
            return {
                'escalated_count': 0,
                'total_checked': 0,
                'error': str(e)
            }

    @api.model
    def toggle_escalation_cron(self, active=True):
        """Toggle the escalation cron job on/off"""
        try:
            escalation_cron = self.env['ir.cron'].search([
                ('name', '=', 'Auto Escalate Maintenance Work Orders')
            ], limit=1)
            
            if escalation_cron:
                escalation_cron.write({'active': active})
                _logger.info(f"Escalation cron job {'activated' if active else 'deactivated'}")
                return True
            else:
                _logger.warning("Escalation cron job not found")
                return False
        except Exception as e:
            _logger.error(f"Error toggling escalation cron: {str(e)}")
            return False

    def action_toggle_escalation_cron(self):
        """Action to toggle escalation cron job from workorder form"""
        self.ensure_one()
        
        # Security check: Only SLA Escalation Managers can control escalation
        if not self._can_manage_escalation():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Access Denied',
                    'message': 'You do not have permission to manage SLA escalation settings. Only SLA Escalation Managers can perform this action.',
                    'type': 'danger',
                }
            }
        
        try:
            escalation_cron = self.env['ir.cron'].search([
                ('name', '=', 'Auto Escalate Maintenance Work Orders')
            ], limit=1)
            
            if escalation_cron:
                new_state = not escalation_cron.active
                escalation_cron.write({'active': new_state})
                
                message = f"Auto escalation {'enabled' if new_state else 'disabled'} successfully by {self.env.user.name}"
                self.message_post(body=message)
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Escalation Control',
                        'message': message,
                        'type': 'success',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': 'Escalation cron job not found',
                        'type': 'danger',
                    }
                }
        except Exception as e:
            _logger.error(f"Error toggling escalation cron: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error toggling escalation: {str(e)}',
                    'type': 'danger',
                }
            }

    @api.model
    def _can_manage_escalation(self):
        """Check if current user can manage SLA escalation settings"""
        return self.env.user.has_group('facilities_management.group_sla_escalation_manager')

    def action_manual_escalation_check(self):
        """Action to manually trigger escalation check for this work order"""
        self.ensure_one()
        
        # Security check: Only SLA Escalation Managers can manually trigger escalation checks
        if not self._can_manage_escalation():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Access Denied',
                    'message': 'You do not have permission to manually trigger SLA escalation checks. Only SLA Escalation Managers can perform this action.',
                    'type': 'danger',
                }
            }
        
        try:
            if not self.sla_id:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'No SLA',
                        'message': 'This work order has no SLA configured',
                        'type': 'warning',
                    }
                }
            
            # Trigger escalation check
            initial_escalation_count = self.escalation_count
            self._check_sla_escalation()
            
            if self.escalation_count > initial_escalation_count:
                message = f"Escalation triggered! Level: {self.sla_escalation_level} (triggered by {self.env.user.name})"
                message_type = 'success'
            else:
                message = f"No escalation needed at this time (checked by {self.env.user.name})"
                message_type = 'info'
            
            # Log the manual check in workorder chatter
            self.message_post(body=f"Manual SLA escalation check performed by {self.env.user.name}")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Escalation Check',
                    'message': message,
                    'type': message_type,
                }
            }
        except Exception as e:
            _logger.error(f"Error in manual escalation check: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error checking escalation: {str(e)}',
                    'type': 'danger',
                }
            }

    def log_escalation_resolution(self, workorder, escalation_log):
        """Log escalation resolution for audit trail"""
        try:
            # Create a message in the workorder chatter
            resolution_message = _(
                "Escalation Resolved\n"
                "Escalation Level: %s\n"
                "Escalation Type: %s\n"
                "Reason: %s\n"
                "Escalated To: %s\n"
                "Resolution Time: %s\n"
                "Work Order: %s\n"
                "Escalation has been successfully resolved."
            ) % (
                escalation_log.escalation_level,
                escalation_log.escalation_type,
                escalation_log.escalation_reason,
                escalation_log.escalated_to_id.name if escalation_log.escalated_to_id else 'N/A',
                escalation_log.resolution_date.strftime('%Y-%m-%d %H:%M:%S') if escalation_log.resolution_date else 'N/A',
                workorder.name
            )
            
            workorder.message_post(
                body=resolution_message,
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
            
            # Update workorder escalation status if all escalations are resolved
            open_escalations = workorder.escalation_history.filtered(lambda e: e.status in ['open', 'in_progress'])
            if not open_escalations:
                workorder.write({
                    'escalation_triggered': False,
                    'escalation_count': len(workorder.escalation_history.filtered(lambda e: e.status == 'resolved'))
                })
                
        except Exception as e:
            _logger.error(f"Error logging escalation resolution: {str(e)}")

    def _validate_technician_assignments_complete(self):
        """
        Validate that all technician assignments are completed before allowing work order completion.
        Raises ValidationError if any assignments are not completed.
        """
        self.ensure_one()
        
        # Get all technician assignments for this work order
        assignments = self.assignment_ids
        
        if not assignments:
            # If no assignments exist, allow completion (work order without technicians)
            return True
            
        # Check if all assignments are completed
        incomplete_assignments = assignments.filtered(lambda a: a.status != 'completed')
        
        if incomplete_assignments:
            # Create a detailed error message listing incomplete assignments
            incomplete_names = ', '.join([f"{a.technician_id.name or 'Unknown Technician'}" for a in incomplete_assignments])
            raise ValidationError(_(
                "Cannot complete work order until all technician assignments are finished. "
                "The following assignments are still in progress: %s"
            ) % incomplete_names)
        
        return True

    def can_complete_from_mobile(self):
        """
        Check if a work order can be completed from the mobile form.
        Returns a dictionary with status and message for mobile UI.
        """
        self.ensure_one()
        
        try:
            self._validate_technician_assignments_complete()
            return {
                'can_complete': True,
                'message': _('Work order is ready to be completed.'),
                'type': 'success'
            }
        except ValidationError as e:
            return {
                'can_complete': False,
                'message': str(e),
                'type': 'error'
            }

    def get_technician_assignment_status(self):
        """
        Get a summary of technician assignment statuses for display in mobile form.
        Returns a dictionary with assignment counts and details.
        """
        self.ensure_one()
        
        assignments = self.assignment_ids
        if not assignments:
            return {
                'total_assignments': 0,
                'completed_assignments': 0,
                'in_progress_assignments': 0,
                'pending_assignments': 0,
                'completion_percentage': 100.0,
                'can_complete': True,
                'message': _('No technician assignments found.')
            }
        
        completed = assignments.filtered(lambda a: a.status == 'completed')
        in_progress = assignments.filtered(lambda a: a.status == 'in_progress')
        pending = assignments.filtered(lambda a: a.status == 'pending')
        
        completion_percentage = (len(completed) / len(assignments)) * 100.0
        
        return {
            'total_assignments': len(assignments),
            'completed_assignments': len(completed),
            'in_progress_assignments': len(in_progress),
            'pending_assignments': len(pending),
            'completion_percentage': round(completion_percentage, 1),
            'can_complete': len(in_progress) == 0 and len(pending) == 0,
            'message': _('Assignment progress: %d/%d completed') % (len(completed), len(assignments)),
            'assignments_detail': [{
                'technician_name': a.technician_id.name or _('Unknown Technician'),
                'status': a.status,
                'status_display': dict(a._fields['status'].selection).get(a.status, a.status),
                'start_time': a.start_time,
                'end_time': a.end_time,
                'work_hours': a.work_hours
            } for a in assignments]
        }

    def write(self, vals):
        """Override write to handle SLA recalculation and validation."""
        # Check if SLA is being manually changed
        if 'sla_id' in vals:
            for record in self:
                if record.sla_id and record.sla_id.id != vals['sla_id']:
                    raise ValidationError(_("SLA cannot be manually changed. It is automatically assigned based on priority and facility."))
        
        # Recalculate SLA if priority or asset changes
        if 'priority' in vals or 'asset_id' in vals:
            for record in self:
                if record.asset_id and record.asset_id.facility_id:
                    new_sla_id = record._get_appropriate_sla({
                        'asset_id': record.asset_id.id,
                        'priority': vals.get('priority', record.priority),
                        'maintenance_type': record.maintenance_type
                    })
                    if new_sla_id and new_sla_id != record.sla_id.id:
                        vals['sla_id'] = new_sla_id
        
        result = super().write(vals)
        
        # Recompute SLA deadline if SLA changed
        if 'sla_id' in vals:
            for record in self:
                if record.sla_id:
                    record._compute_sla_deadline()
        
        return result

    @api.constrains('work_order_type', 'job_plan_id')
    def _check_job_plan_preventive_only(self):
        """Ensure job plans are only assigned to preventive work orders."""
        for record in self:
            if record.job_plan_id and record.work_order_type != 'preventive':
                raise UserError(_("Job plans can only be assigned to preventive maintenance work orders. "
                                "Current work order type: %s") % record.work_order_type)

    @api.constrains('sla_id')
    def _check_sla_assignment(self):
        """Ensure SLA is always assigned and cannot be manually changed."""
        for record in self:
            if not record.sla_id:
                raise ValidationError(_("SLA is mandatory and must be automatically assigned based on priority and facility."))
            
            # Check if this is an update operation and SLA is being changed
            if record._origin.id and record._origin.sla_id and record._origin.sla_id != record.sla_id:
                raise ValidationError(_("SLA cannot be manually changed. It is automatically assigned based on priority and facility."))

    @api.onchange('work_order_type')
    def _onchange_work_order_type(self):
        """Clear job plan when work order type changes from preventive to something else."""
        if self.work_order_type != 'preventive':
            if self.job_plan_id:
                self.job_plan_id = False
                return {
                    'warning': {
                        'title': _('Job Plan Cleared'),
                        'message': _('Job plan has been cleared because this is not a preventive work order. '
                                   'All associated job plan tasks will be lost.')
                    }
                }
        else:
            # If changing to preventive, show info about job plan availability
            if not self.job_plan_id:
                return {
                    'warning': {
                        'title': _('Job Plan Available'),
                        'message': _('You can now assign a job plan to this preventive work order.')
                    }
                }

    @api.onchange('job_plan_id')
    def _onchange_job_plan_id(self):
        """Validate that job plan can only be assigned to preventive work orders."""
        if self.job_plan_id and self.work_order_type != 'preventive':
            self.job_plan_id = False
            return {
                'warning': {
                    'title': _('Invalid Selection'),
                    'message': _('Job plans can only be assigned to preventive work orders.')
                }
            }

    @api.onchange('priority')
    def _onchange_priority(self):
        """Recalculate SLA when priority changes."""
        if self.priority and self.asset_id and self.asset_id.facility_id:
            # Force SLA recalculation
            self.sla_id = self._get_appropriate_sla({
                'asset_id': self.asset_id.id,
                'priority': self.priority,
                'maintenance_type': self.maintenance_type
            })
            if self.sla_id:
                self._compute_sla_deadline()

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        """Auto-fill related fields and recalculate SLA when asset changes."""
        if self.asset_id:
            # Auto-fill location-related fields
            self.facility_id = self.asset_id.facility_id
            self.building_id = self.asset_id.building_id
            self.floor_id = self.asset_id.floor_id
            self.room_id = self.asset_id.room_id
            
            # Auto-fill asset-related information
            if hasattr(self.asset_id, 'asset_category_id') and self.asset_id.asset_category_id:
                self.asset_category_id = self.asset_id.asset_category_id
            if hasattr(self.asset_id, 'asset_tag') and self.asset_id.asset_tag:
                self.asset_tag = self.asset_id.asset_tag
            if hasattr(self.asset_id, 'serial_number') and self.asset_id.serial_number:
                self.serial_number = self.asset_id.serial_number
            
            # Recalculate SLA when asset (and thus facility) changes
            if self.asset_id.facility_id and self.priority:
                # Force SLA recalculation
                self.sla_id = self._get_appropriate_sla({
                    'asset_id': self.asset_id.id,
                    'priority': self.priority,
                    'maintenance_type': self.maintenance_type
                })
                if self.sla_id:
                    self._compute_sla_deadline()

    # Note: technician contact information is accessible through technician_id relation

    # Note: supervisor contact information is accessible through supervisor_id relation

    # Note: facility_id is a related field from asset_id.facility_id, so no onchange needed

    def _recalculate_sla(self):
        """Recalculate SLA based on current priority and facility."""
        for workorder in self:
            if workorder.asset_id and workorder.asset_id.facility_id and workorder.priority:
                new_sla_id = workorder._get_appropriate_sla({
                    'asset_id': workorder.asset_id.id,
                    'priority': workorder.priority,
                    'maintenance_type': workorder.maintenance_type
                })
                if new_sla_id and new_sla_id != workorder.sla_id.id:
                    workorder.sla_id = new_sla_id
                    workorder._compute_sla_deadline()

    def action_recalculate_sla(self):
        """Action method to manually recalculate SLA for existing workorders."""
        self.ensure_one()
        try:
            self._recalculate_sla()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('SLA Recalculated'),
                    'message': _('SLA has been recalculated based on current priority and facility.'),
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('SLA Recalculation Failed'),
                    'message': _('Failed to recalculate SLA: %s') % str(e),
                    'type': 'danger',
                }
            }

    def action_test_escalation_mechanism(self):
        """Test the escalation mechanism for this work order"""
        self.ensure_one()
        
        try:
            # Log the test action
            test_message = _(
                "Escalation Mechanism Test\n"
                "Work Order: %s\n"
                "Current SLA Status: %s\n"
                "SLA Deadline: %s\n"
                "Escalation Level: %s\n"
                "Tested By: %s\n"
                "Test Time: %s\n"
                "This is a test of the escalation mechanism. No actual escalation was triggered."
            ) % (
                self.name,
                self.sla_status,
                self.sla_deadline or 'Not set',
                self.sla_escalation_level,
                self.env.user.name,
                fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            
            self.message_post(
                body=test_message,
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
            
            # Return a user-friendly message
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Escalation Test'),
                    'message': _('Escalation mechanism test completed successfully. Check the chatter for details.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error('Failed to test escalation mechanism: %s', str(e))
            raise UserError(_('Failed to test escalation mechanism: %s') % str(e))


    def action_add_task(self):
        """Add a new task to this work order"""
        self.ensure_one()
        
        # Create a default section if none exists
        if not self.section_ids:
            default_section = self.env['facilities.workorder.section'].create({
                'name': _('General Tasks'),
                'sequence': 10,
                'workorder_id': self.id,
            })
        else:
            default_section = self.section_ids[0]
        
        # Create a new task
        new_task = self.env['facilities.workorder.task'].create({
            'workorder_id': self.id,
            'section_id': default_section.id,
            'name': _('New Task'),
            'sequence': len(default_section.task_ids) + 10,
            'is_checklist_item': True,
        })
        
        # Return action to open the new task in form view
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Task'),
            'res_model': 'facilities.workorder.task',
            'view_mode': 'form',
            'res_id': new_task.id,
            'target': 'current',
            'context': {'default_workorder_id': self.id, 'default_section_id': default_section.id},
        }

    def action_import_job_plan(self):
        """Import tasks from the selected job plan"""
        self.ensure_one()
        
        if not self.job_plan_id:
            raise UserError(_('Please select a Job Plan first before importing tasks.'))
        
        if self.work_order_type != 'preventive':
            raise UserError(_('Job plans can only be imported for preventive maintenance work orders.'))
        
        try:
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
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Job Plan Imported'),
                    'message': _('Successfully imported %d tasks from Job Plan "%s"') % (task_count, self.job_plan_id.name),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error('Failed to import job plan: %s', str(e))
            raise UserError(_('Failed to import job plan: %s') % str(e))
    
    def action_create_invoice(self):
        """Create invoice from work order"""
        self.ensure_one()
        
        # Check work order state
        if self.state not in ('completed', 'cancelled'):
            raise UserError(_('Work order must be completed before creating an invoice.'))
        
        # Check if vendor is set
        if not self.partner_id:
            raise UserError(_('Please set a vendor in the "Additional Info" tab before creating an invoice.'))
        
        # Check if there are costs to invoice
        if self.total_cost <= 0:
            raise UserError(_(
                'Cannot create invoice with zero cost.\n\n'
                'Please add costs in one of these ways:\n'
                '• Add labor costs in the "Personnel" tab\n'
                '• Add parts costs in the "Parts Used" tab\n'
                '• Set labor_cost or parts_cost in the "Additional Info" tab'
            ))
        
        # Create invoice
        invoice_vals = {
            'move_type': 'in_invoice',  # Vendor bill
            'partner_id': self.partner_id.id,
            'workorder_id': self.id,
            'invoice_date': fields.Date.today(),
            'ref': self.name,
            'narration': f'Invoice for work order: {self.name}\nDescription: {self.description or ""}',
        }
        
        invoice = self.env['account.move'].create(invoice_vals)
        
        # Create invoice lines
        invoice_lines = []
        
        # Add labor cost line
        if self.labor_cost > 0:
            labor_line = {
                'move_id': invoice.id,
                'name': f'Labor costs for {self.name}',
                'quantity': 1,
                'price_unit': self.labor_cost,
                'account_id': self._get_labor_account_id(),
            }
                # Skip analytic account for now - will be handled by Odoo's analytic system
                # if self.analytic_account_id:
                #     labor_line['analytic_account_id'] = self.analytic_account_id.id
            invoice_lines.append((0, 0, labor_line))
        
        # Add parts cost line
        if self.parts_cost > 0:
            parts_line = {
                'move_id': invoice.id,
                'name': f'Parts and materials for {self.name}',
                'quantity': 1,
                'price_unit': self.parts_cost,
                'account_id': self._get_parts_account_id(),
            }
                # Skip analytic account for now - will be handled by Odoo's analytic system
                # if self.analytic_account_id:
                #     parts_line['analytic_account_id'] = self.analytic_account_id.id
            invoice_lines.append((0, 0, parts_line))
        
        # Add detailed parts lines if available
        for part in self.parts_used_ids:
            if part.product_id and part.quantity > 0:
                part_line = {
                    'move_id': invoice.id,
                    'product_id': part.product_id.id,
                    'name': part.product_id.name,
                    'quantity': part.quantity,
                    'product_uom_id': part.uom_id.id if part.uom_id else part.product_id.uom_id.id,
                    'price_unit': part.product_id.standard_price,
                    'account_id': part.product_id.categ_id.property_account_expense_categ_id.id or self._get_parts_account_id(),
                }
                # Skip analytic account for now - will be handled by Odoo's analytic system
                # if self.analytic_account_id:
                #     part_line['analytic_account_id'] = self.analytic_account_id.id
                invoice_lines.append((0, 0, part_line))
        
        if invoice_lines:
            invoice.write({'invoice_line_ids': invoice_lines})
        
        # Post a message
        self.message_post(
            body=_('Invoice %s created for work order %s') % (invoice.name, self.name),
            message_type='notification'
        )
        
        # Create budget expenses if not already created
        # Note: _create_budget_expenses() has built-in duplicate prevention
        self._create_budget_expenses('invoice_creation')
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_invoices(self):
        """View invoices related to this work order"""
        self.ensure_one()
        action = self.env.ref('account.action_move_in_invoice_type').read()[0]
        
        if len(self.invoice_ids) > 1:
            action['domain'] = [('id', 'in', self.invoice_ids.ids)]
        elif len(self.invoice_ids) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = self.invoice_ids.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        
        return action
    
    def _get_labor_account_id(self):
        """Get the account for labor costs"""
        # Try to get from company settings or use a default expense account
        company = self.env.company
        
        # Try different search criteria for Odoo 18
        account = self.env['account.account'].search([
            ('code', 'like', '6%'),  # Expense accounts typically start with 6
            ('deprecated', '=', False)
        ], limit=1)
        
        if not account:
            # Fallback to any expense account
            account = self.env['account.account'].search([
                ('account_type', 'in', ['expense', 'other']),
                ('deprecated', '=', False)
            ], limit=1)
        
        if not account:
            # Final fallback - get any account
            account = self.env['account.account'].search([
                ('deprecated', '=', False)
            ], limit=1)
        
        return account.id if account else False
    
    def _get_parts_account_id(self):
        """Get the account for parts/materials costs"""
        # Try to get from company settings or use a default expense account
        company = self.env.company
        
        # Try different search criteria for Odoo 18
        account = self.env['account.account'].search([
            ('code', 'like', '6%'),  # Expense accounts typically start with 6
            ('deprecated', '=', False)
        ], limit=1)
        
        if not account:
            # Fallback to any expense account
            account = self.env['account.account'].search([
                ('account_type', 'in', ['expense', 'other']),
                ('deprecated', '=', False)
            ], limit=1)
        
        if not account:
            # Final fallback - get any account
            account = self.env['account.account'].search([
                ('deprecated', '=', False)
            ], limit=1)
        
        return account.id if account else False
    
    def _create_budget_expenses(self, trigger_source='unknown'):
        """Create budget expenses when work order is completed"""
        self.ensure_one()
        
        _logger.info('Starting budget expense creation for work order %s (triggered by: %s)', self.name, trigger_source)
        _logger.info('Cost center: %s, Total cost: %s, Labor cost: %s, Parts cost: %s', 
                    self.cost_center_id.name if self.cost_center_id else 'None',
                    self.total_cost, self.labor_cost, self.parts_cost)
        
        # Only create expenses if analytic account is assigned and there are costs
        if not self.analytic_account_id:
            _logger.warning('No analytic account assigned to work order %s, cannot create budget expenses', self.name)
            return
            
        if self.total_cost <= 0:
            _logger.warning('Work order %s has no costs (total_cost=%s), cannot create budget expenses', 
                          self.name, self.total_cost)
            return
        
        # Check if budget expenses already exist for this work order
        existing_expenses = self.env['facilities.budget.expense'].search([
            ('workorder_id', '=', self.id)
        ])
        if existing_expenses:
            _logger.info('Budget expenses already exist for work order %s (%d expenses found), skipping creation', 
                        self.name, len(existing_expenses))
            # Log details of existing expenses for transparency
            for expense in existing_expenses:
                _logger.info('  - Existing expense: %s (Amount: %s, Category: %s)', 
                           expense.description, expense.amount, expense.category_id.name)
            return
        
        # Find active budget for the cost center
        active_budgets = self.env['facilities.financial.budget'].search([
            ('state', '=', 'active'),
            ('start_date', '<=', fields.Date.today()),
            ('end_date', '>=', fields.Date.today()),
        ])
        
        if not active_budgets:
            _logger.warning('No active budget found for work order %s completion', self.name)
            return
        
        # Find the best matching budget (prefer one with matching analytic account)
        budget = None
        for active_budget in active_budgets:
            budget_lines = active_budget.budget_line_ids.filtered(
                lambda l: l.analytic_account_id == self.analytic_account_id
            )
            if budget_lines:
                budget = active_budget
                break
        
        # If no budget with matching analytic account, use first active budget
        if not budget:
            budget = active_budgets[0]
        
        # Find existing budget lines for this analytic account to get the correct categories
        budget_lines = budget.budget_line_ids.filtered(
            lambda l: l.analytic_account_id == self.analytic_account_id
        )
        
        if not budget_lines:
            message = _(
                'No budget lines found for analytic account "%s" in budget "%s". '
                'Please create budget lines for this analytic account before completing work orders.'
            ) % (self.analytic_account_id.name, budget.name)
            _logger.warning(message)
            self.message_post(body=message, message_type='notification')
            return
        
        expenses_created = []
        
        # Create labor expense if labor cost > 0
        if self.labor_cost > 0:
            # Find budget line for labor costs (look for keywords)
            labor_budget_line = None
            for line in budget_lines:
                category_name = line.category_id.name.lower()
                if any(keyword in category_name for keyword in ['labor', 'labour', 'work', 'technician', 'staff']):
                    labor_budget_line = line
                    break
            
            if labor_budget_line:
                labor_expense = self.env['facilities.budget.expense'].create({
                    'budget_id': budget.id,
                    'analytic_account_id': self.analytic_account_id.id,
                    'cost_center_id': self.cost_center_id.id if self.cost_center_id else None,
                    'category_id': labor_budget_line.category_id.id,
                    'date': fields.Date.today(),
                    'amount': self.labor_cost,
                    'description': f'Labor costs for work order {self.name}',
                    'reference': self.name,
                    'workorder_id': self.id,
                    'vendor_id': self.vendor_partner_id.id if self.vendor_partner_id else None,
                    'state': 'confirmed',
                })
                expenses_created.append(labor_expense)
            else:
                available_categories = ', '.join([line.category_id.name for line in budget_lines])
                message = _(
                    'No labor budget line found for analytic account "%s". '
                    'Available categories: %s. '
                    'Please create a budget line with a category containing keywords like "labor", "work", or "staff".'
                ) % (self.analytic_account_id.name, available_categories)
                _logger.warning(message)
                self.message_post(body=message, message_type='notification')
        
        # Create parts expense if parts cost > 0
        if self.parts_cost > 0:
            # Find budget line for parts/materials costs
            parts_budget_line = None
            for line in budget_lines:
                category_name = line.category_id.name.lower()
                if any(keyword in category_name for keyword in ['part', 'material', 'spare', 'component', 'supply']):
                    parts_budget_line = line
                    break
            
            if parts_budget_line:
                parts_expense = self.env['facilities.budget.expense'].create({
                    'budget_id': budget.id,
                    'analytic_account_id': self.analytic_account_id.id,
                    'cost_center_id': self.cost_center_id.id if self.cost_center_id else None,
                    'category_id': parts_budget_line.category_id.id,
                    'date': fields.Date.today(),
                    'amount': self.parts_cost,
                    'description': f'Parts and materials for work order {self.name}',
                    'reference': self.name,
                    'workorder_id': self.id,
                    'vendor_id': self.vendor_partner_id.id if self.vendor_partner_id else None,
                    'state': 'confirmed',
                })
                expenses_created.append(parts_expense)
            else:
                available_categories = ', '.join([line.category_id.name for line in budget_lines])
                message = _(
                    'No parts budget line found for analytic account "%s". '
                    'Available categories: %s. '
                    'Please create a budget line with a category containing keywords like "parts", "materials", or "spare".'
                ) % (self.analytic_account_id.name, available_categories)
                _logger.warning(message)
                self.message_post(body=message, message_type='notification')
        
        if expenses_created:
            expense_names = ', '.join([e.description for e in expenses_created])
            self.message_post(
                body=_('Budget expenses created: %s (Total: %s)') % (expense_names, self.total_cost),
                message_type='notification'
            )
            _logger.info('Created %d budget expenses for work order %s with total cost %s', 
                        len(expenses_created), self.name, self.total_cost)
    
    
    def action_view_budget_expenses(self):
        """View budget expenses related to this work order"""
        self.ensure_one()
        
        # Debug: Log search parameters
        _logger.info('Searching for budget expenses with workorder_id=%s', self.id)
        
        expenses = self.env['facilities.budget.expense'].search([
            ('workorder_id', '=', self.id)
        ])
        
        _logger.info('Found %d budget expenses for work order %s', len(expenses), self.name)
        
        # If no expenses found, try to create them manually
        if not expenses and self.state == 'completed' and self.total_cost > 0:
            _logger.info('No expenses found but work order is completed with costs. Attempting to create budget expenses.')
            try:
                self._create_budget_expenses('manual_view_trigger')
                # Search again after creation
                expenses = self.env['facilities.budget.expense'].search([
                    ('workorder_id', '=', self.id)
                ])
                _logger.info('After manual creation: Found %d budget expenses', len(expenses))
            except Exception as e:
                _logger.error('Failed to create budget expenses: %s', str(e))
        
        action = {
            'name': _('Budget Expenses'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.expense',
            'view_mode': 'list,form',
            'context': {
                'default_workorder_id': self.id,
                'default_cost_center_id': self.cost_center_id.id if self.cost_center_id else False,
            }
        }
        
        if len(expenses) > 1:
            action['domain'] = [('id', 'in', expenses.ids)]
        elif len(expenses) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = expenses.id
        else:
            action['domain'] = [('workorder_id', '=', self.id)]
            
        return action
    
    def action_create_missing_budget_lines(self):
        """Helper action to create missing budget lines for this cost center"""
        self.ensure_one()
        
        if not self.cost_center_id:
            raise UserError(_('Please assign a cost center to this work order first.'))
        
        # Find active budget
        active_budgets = self.env['facilities.financial.budget'].search([
            ('state', '=', 'active'),
            ('start_date', '<=', fields.Date.today()),
            ('end_date', '>=', fields.Date.today()),
        ])
        
        if not active_budgets:
            raise UserError(_('No active budget found. Please create and activate a budget first.'))
        
        budget = active_budgets[0]
        
        # Get or create default expense categories
        labor_category = self._get_or_create_default_category('LABOR', 'Labor Costs')
        parts_category = self._get_or_create_default_category('PARTS', 'Spare Parts')
        
        # Create budget lines if they don't exist
        existing_lines = budget.budget_line_ids.filtered(
            lambda l: l.cost_center_id == self.cost_center_id
        )
        
        lines_to_create = []
        
        # Check if labor category line exists
        if not existing_lines.filtered(lambda l: l.category_id == labor_category):
            lines_to_create.append({
                'budget_id': budget.id,
                'cost_center_id': self.cost_center_id.id,
                'category_id': labor_category.id,
                'allocated_amount': 5000.0,  # Default allocation
                'description': f'Labor costs budget line for {self.cost_center_id.name}'
            })
        
        # Check if parts category line exists  
        if not existing_lines.filtered(lambda l: l.category_id == parts_category):
            lines_to_create.append({
                'budget_id': budget.id,
                'cost_center_id': self.cost_center_id.id,
                'category_id': parts_category.id,
                'allocated_amount': 10000.0,  # Default allocation
                'description': f'Parts and materials budget line for {self.cost_center_id.name}'
            })
        
        if lines_to_create:
            created_lines = self.env['facilities.budget.line'].create(lines_to_create)
            self.message_post(
                body=_('Created %d missing budget lines for cost center %s') % (
                    len(created_lines), self.cost_center_id.name
                ),
                message_type='notification'
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Budget Lines Created'),
                    'message': _('Created %d budget lines. You can now complete the work order.') % len(created_lines),
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Budget Lines Exist'),
                    'message': _('Budget lines already exist for this cost center.'),
                    'type': 'info',
                }
            }
    
    def _get_or_create_default_category(self, code, name):
        """Get or create a default expense category"""
        category = self.env['facilities.expense.category'].search([
            ('code', '=', code),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not category:
            category = self.env['facilities.expense.category'].create({
                'code': code,
                'name': name,
                'company_id': self.env.company.id,
                'description': f'Default category for {name.lower()}'
            })
        
        return category
    
    def action_start_with_permit_wizard(self):
        """Force open permit wizard for testing"""
        self.ensure_one()
        
        _logger.info('Force opening permit wizard for work order %s', self.name)
        
        return {
            'name': _('Start Work Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder.start.permit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
            }
        }
    
    def action_start_direct(self):
        """Direct start work order for testing"""
        self.ensure_one()
        
        _logger.info('Direct starting work order %s', self.name)
        
        if self.state not in ['draft', 'assigned']:
            raise UserError(_("Work order must be in draft or assigned state to start. Current state: %s") % self.state)
        
        try:
            self.write({
                'state': 'in_progress',
                'actual_start_date': fields.Datetime.now()
            })
            
            self.message_post(body=_("Work order started directly by %s") % self.env.user.name)
            
            _logger.info('Successfully started work order %s directly', self.name)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
            
        except Exception as e:
            _logger.error('Failed to start work order %s directly: %s', self.name, str(e))
            raise UserError(_('Failed to start work order: %s') % str(e))
    
    def action_view_permits(self):
        """View permits related to this work order"""
        self.ensure_one()
        
        action = {
            'name': _('Work Order Permits'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder.permit',
            'view_mode': 'list,form',
            'context': {
                'default_workorder_id': self.id,
            }
        }
        
        if len(self.permit_ids) > 1:
            action['domain'] = [('id', 'in', self.permit_ids.ids)]
        elif len(self.permit_ids) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.permit_ids.id
        else:
            action['domain'] = [('workorder_id', '=', self.id)]
            
        return action
    

