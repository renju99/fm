# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import json
import logging

_logger = logging.getLogger(__name__)


class FacilitiesManagementDashboard(models.Model):
    """
    Main Facilities Management Dashboard
    
    Provides comprehensive overview of all facilities management operations including:
    - Facility and asset metrics
    - Maintenance and work order statistics
    - Financial performance
    - Space utilization
    - Energy consumption
    - Safety incidents
    - Security rounds
    """
    _name = 'facilities.management.dashboard'
    _description = 'Facilities Management Dashboard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # Basic Information
    name = fields.Char(
        string='Dashboard Name',
        required=True,
        default='Facilities Dashboard',
        tracking=True
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Dashboard Owner',
        default=lambda self: self.env.user,
        tracking=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        tracking=True,
        index=True
    )
    
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    # Date Range Configuration
    period_type = fields.Selection([
        ('today', 'Today'),
        ('week', 'This Week'),
        ('month', 'This Month'),
        ('quarter', 'This Quarter'),
        ('year', 'This Year'),
        ('custom', 'Custom Period')
    ], string='Period', default='month', required=True, tracking=True)
    
    date_from = fields.Date(
        string='Start Date',
        default=lambda self: fields.Date.today().replace(day=1),
        tracking=True
    )
    
    date_to = fields.Date(
        string='End Date',
        default=fields.Date.today,
        tracking=True
    )
    
    # Filters
    facility_ids = fields.Many2many(
        'facilities.facility',
        string='Facilities',
        help='Filter by specific facilities. Leave empty to include all.'
    )
    
    # Dashboard Data (JSON fields for frontend consumption)
    dashboard_data = fields.Text(
        string='Dashboard Data',
        compute='_compute_dashboard_data',
        help='JSON data containing all dashboard metrics'
    )
    
    # ==================== KPI FIELDS ====================
    
    # Facility & Asset KPIs
    total_facilities = fields.Integer(
        string='Total Facilities',
        compute='_compute_facility_kpis',
        store=True
    )
    
    total_buildings = fields.Integer(
        string='Total Buildings',
        compute='_compute_facility_kpis',
        store=True
    )
    
    total_rooms = fields.Integer(
        string='Total Rooms',
        compute='_compute_facility_kpis',
        store=True
    )
    
    total_assets = fields.Integer(
        string='Total Assets',
        compute='_compute_asset_kpis',
        store=True
    )
    
    total_asset_value = fields.Monetary(
        string='Total Asset Value',
        currency_field='currency_id',
        compute='_compute_asset_kpis',
        store=True
    )
    
    active_assets = fields.Integer(
        string='Active Assets',
        compute='_compute_asset_kpis',
        store=True
    )
    
    assets_under_maintenance = fields.Integer(
        string='Assets Under Maintenance',
        compute='_compute_asset_kpis',
        store=True
    )
    
    # Work Order KPIs
    total_workorders = fields.Integer(
        string='Total Work Orders',
        compute='_compute_workorder_kpis',
        store=True
    )
    
    open_workorders = fields.Integer(
        string='Open Work Orders',
        compute='_compute_workorder_kpis',
        store=True
    )
    
    in_progress_workorders = fields.Integer(
        string='In Progress Work Orders',
        compute='_compute_workorder_kpis',
        store=True
    )
    
    completed_workorders = fields.Integer(
        string='Completed Work Orders',
        compute='_compute_workorder_kpis',
        store=True
    )
    
    overdue_workorders = fields.Integer(
        string='Overdue Work Orders',
        compute='_compute_workorder_kpis',
        store=True
    )
    
    workorder_completion_rate = fields.Float(
        string='Completion Rate (%)',
        compute='_compute_workorder_kpis',
        store=True
    )
    
    avg_workorder_duration = fields.Float(
        string='Avg Duration (hours)',
        compute='_compute_workorder_kpis',
        store=True
    )
    
    # Maintenance KPIs
    preventive_maintenance_count = fields.Integer(
        string='Preventive Maintenance',
        compute='_compute_maintenance_kpis',
        store=True
    )
    
    corrective_maintenance_count = fields.Integer(
        string='Corrective Maintenance',
        compute='_compute_maintenance_kpis',
        store=True
    )
    
    total_maintenance_cost = fields.Monetary(
        string='Total Maintenance Cost',
        currency_field='currency_id',
        compute='_compute_maintenance_kpis',
        store=True
    )
    
    # Financial KPIs
    total_budget = fields.Monetary(
        string='Total Budget',
        currency_field='currency_id',
        compute='_compute_financial_kpis',
        store=True
    )
    
    total_expenses = fields.Monetary(
        string='Total Expenses',
        currency_field='currency_id',
        compute='_compute_financial_kpis',
        store=True
    )
    
    budget_utilization = fields.Float(
        string='Budget Utilization (%)',
        compute='_compute_financial_kpis',
        store=True
    )
    
    # Space Booking KPIs
    total_bookings = fields.Integer(
        string='Total Bookings',
        compute='_compute_booking_kpis',
        store=True
    )
    
    active_bookings = fields.Integer(
        string='Active Bookings',
        compute='_compute_booking_kpis',
        store=True
    )
    
    space_utilization = fields.Float(
        string='Space Utilization (%)',
        compute='_compute_booking_kpis',
        store=True
    )
    
    # Service Request KPIs
    total_service_requests = fields.Integer(
        string='Total Service Requests',
        compute='_compute_service_request_kpis',
        store=True
    )
    
    pending_service_requests = fields.Integer(
        string='Pending Service Requests',
        compute='_compute_service_request_kpis',
        store=True
    )
    
    resolved_service_requests = fields.Integer(
        string='Resolved Service Requests',
        compute='_compute_service_request_kpis',
        store=True
    )
    
    # Safety KPIs
    safety_incidents = fields.Integer(
        string='Safety Incidents',
        compute='_compute_safety_kpis',
        store=True
    )
    
    # Energy KPIs
    total_energy_consumption = fields.Float(
        string='Total Energy Consumption (kWh)',
        compute='_compute_energy_kpis',
        store=True
    )
    
    energy_cost = fields.Monetary(
        string='Energy Cost',
        currency_field='currency_id',
        compute='_compute_energy_kpis',
        store=True
    )
    
    # ==================== COMPUTE METHODS ====================
    
    @api.onchange('period_type')
    def _onchange_period_type(self):
        """Update date range based on selected period type"""
        today = fields.Date.today()
        
        if self.period_type == 'today':
            self.date_from = today
            self.date_to = today
        elif self.period_type == 'week':
            self.date_from = today - timedelta(days=today.weekday())
            self.date_to = today
        elif self.period_type == 'month':
            self.date_from = today.replace(day=1)
            self.date_to = today
        elif self.period_type == 'quarter':
            quarter = (today.month - 1) // 3
            self.date_from = date(today.year, quarter * 3 + 1, 1)
            self.date_to = today
        elif self.period_type == 'year':
            self.date_from = date(today.year, 1, 1)
            self.date_to = today
    
    @api.depends('facility_ids')
    def _compute_facility_kpis(self):
        """Compute facility-related KPIs"""
        for record in self:
            domain = []
            if record.facility_ids:
                domain = [('id', 'in', record.facility_ids.ids)]
            
            facilities = self.env['facilities.facility'].search(domain)
            record.total_facilities = len(facilities)
            
            building_domain = []
            if record.facility_ids:
                building_domain = [('facility_id', 'in', record.facility_ids.ids)]
            record.total_buildings = self.env['facilities.building'].search_count(building_domain)
            
            room_domain = []
            if record.facility_ids:
                room_domain = [('facility_id', 'in', record.facility_ids.ids)]
            record.total_rooms = self.env['facilities.room'].search_count(room_domain)
    
    @api.depends('facility_ids')
    def _compute_asset_kpis(self):
        """Compute asset-related KPIs"""
        for record in self:
            domain = []
            if record.facility_ids:
                domain = [('facility_id', 'in', record.facility_ids.ids)]
            
            assets = self.env['facilities.asset'].search(domain)
            record.total_assets = len(assets)
            record.total_asset_value = sum(assets.mapped('purchase_cost'))
            record.active_assets = len(assets.filtered(lambda a: a.state == 'active'))
            
            # Assets under maintenance
            maintenance_domain = domain + [('state', '=', 'maintenance')]
            record.assets_under_maintenance = self.env['facilities.asset'].search_count(
                maintenance_domain
            )
    
    @api.depends('facility_ids', 'date_from', 'date_to')
    def _compute_workorder_kpis(self):
        """Compute work order KPIs"""
        for record in self:
            domain = [
                ('start_date', '>=', record.date_from),
                ('start_date', '<=', record.date_to),
            ]
            
            if record.facility_ids:
                domain.append(('work_location_facility_id', 'in', record.facility_ids.ids))
            
            workorders = self.env['facilities.workorder'].search(domain)
            record.total_workorders = len(workorders)
            record.open_workorders = len(workorders.filtered(lambda w: w.state == 'open'))
            record.in_progress_workorders = len(workorders.filtered(lambda w: w.state == 'in_progress'))
            record.completed_workorders = len(workorders.filtered(lambda w: w.state == 'done'))
            
            # Overdue work orders
            today = fields.Date.today()
            record.overdue_workorders = len(workorders.filtered(
                lambda w: w.start_date and w.start_date < today and w.state not in ['done', 'cancelled']
            ))
            
            # Completion rate
            if record.total_workorders > 0:
                record.workorder_completion_rate = (record.completed_workorders / record.total_workorders) * 100
            else:
                record.workorder_completion_rate = 0.0
            
            # Average duration for completed work orders
            completed_with_duration = workorders.filtered(
                lambda w: w.state == 'done' and w.actual_start_date and w.actual_end_date
            )
            if completed_with_duration:
                total_duration = sum(
                    (wo.actual_end_date - wo.actual_start_date).total_seconds() / 3600
                    for wo in completed_with_duration
                )
                record.avg_workorder_duration = total_duration / len(completed_with_duration)
            else:
                record.avg_workorder_duration = 0.0
    
    @api.depends('facility_ids', 'date_from', 'date_to')
    def _compute_maintenance_kpis(self):
        """Compute maintenance-related KPIs"""
        for record in self:
            domain = [
                ('start_date', '>=', record.date_from),
                ('start_date', '<=', record.date_to),
            ]
            
            if record.facility_ids:
                domain.append(('work_location_facility_id', 'in', record.facility_ids.ids))
            
            # Preventive vs Corrective maintenance
            preventive_domain = domain + [('maintenance_type', '=', 'preventive')]
            record.preventive_maintenance_count = self.env['facilities.workorder'].search_count(
                preventive_domain
            )
            
            corrective_domain = domain + [('maintenance_type', '=', 'corrective')]
            record.corrective_maintenance_count = self.env['facilities.workorder'].search_count(
                corrective_domain
            )
            
            # Total maintenance cost (from work order parts and labor)
            workorders = self.env['facilities.workorder'].search(domain)
            
            # Sum part costs and labor costs
            part_cost = sum(workorders.mapped('parts_cost'))
            labor_cost = sum(workorders.mapped('labor_cost'))
            
            record.total_maintenance_cost = part_cost + labor_cost
    
    @api.depends('facility_ids', 'date_from', 'date_to')
    def _compute_financial_kpis(self):
        """Compute financial KPIs"""
        for record in self:
            try:
                # Get budget data
                budget_domain = []
                if record.facility_ids:
                    # Get cost centers associated with these facilities
                    cost_centers = self.env['facilities.cost.center'].search([
                        ('facility_id', 'in', record.facility_ids.ids)
                    ])
                    if cost_centers:
                        budget_domain.append(('cost_center_id', 'in', cost_centers.ids))
                
                budget_lines = self.env['facilities.budget.line'].search(budget_domain)
                record.total_budget = sum(budget_lines.mapped('allocated_amount'))
                
                # Get expense data
                expense_domain = [
                    ('date', '>=', record.date_from),
                    ('date', '<=', record.date_to),
                    ('state', 'in', ['confirmed', 'approved', 'paid'])
                ]
                
                if budget_domain and cost_centers:
                    expense_domain.append(('cost_center_id', 'in', cost_centers.ids))
                
                expenses = self.env['facilities.budget.expense'].search(expense_domain)
                record.total_expenses = sum(expenses.mapped('amount'))
                
                # Budget utilization
                if record.total_budget > 0:
                    record.budget_utilization = (record.total_expenses / record.total_budget) * 100
                else:
                    record.budget_utilization = 0.0
                    
            except Exception as e:
                _logger.warning(f"Error computing financial KPIs: {str(e)}")
                record.total_budget = 0.0
                record.total_expenses = 0.0
                record.budget_utilization = 0.0
    
    @api.depends('facility_ids', 'date_from', 'date_to')
    def _compute_booking_kpis(self):
        """Compute space booking KPIs"""
        for record in self:
            try:
                domain = [
                    ('booking_date', '>=', record.date_from),
                    ('booking_date', '<=', record.date_to),
                ]
                
                if record.facility_ids:
                    # Get rooms for selected facilities
                    rooms = self.env['facilities.room'].search([
                        ('facility_id', 'in', record.facility_ids.ids)
                    ])
                    if rooms:
                        domain.append(('room_id', 'in', rooms.ids))
                
                bookings = self.env['facilities.space.booking'].search(domain)
                record.total_bookings = len(bookings)
                record.active_bookings = len(bookings.filtered(lambda b: b.state == 'confirmed'))
                
                # Calculate space utilization (simplified)
                if record.total_rooms > 0:
                    record.space_utilization = (record.active_bookings / record.total_rooms) * 10
                    if record.space_utilization > 100:
                        record.space_utilization = 100.0
                else:
                    record.space_utilization = 0.0
                    
            except Exception as e:
                _logger.warning(f"Error computing booking KPIs: {str(e)}")
                record.total_bookings = 0
                record.active_bookings = 0
                record.space_utilization = 0.0
    
    @api.depends('facility_ids', 'date_from', 'date_to')
    def _compute_service_request_kpis(self):
        """Compute service request KPIs"""
        for record in self:
            try:
                domain = [
                    ('create_date', '>=', record.date_from),
                    ('create_date', '<=', record.date_to),
                ]
                
                if record.facility_ids:
                    domain.append(('facility_id', 'in', record.facility_ids.ids))
                
                requests = self.env['facilities.service.request'].search(domain)
                record.total_service_requests = len(requests)
                record.pending_service_requests = len(requests.filtered(
                    lambda r: r.state in ['draft', 'submitted', 'in_progress']
                ))
                record.resolved_service_requests = len(requests.filtered(lambda r: r.state == 'resolved'))
                
            except Exception as e:
                _logger.warning(f"Error computing service request KPIs: {str(e)}")
                record.total_service_requests = 0
                record.pending_service_requests = 0
                record.resolved_service_requests = 0
    
    @api.depends('facility_ids', 'date_from', 'date_to')
    def _compute_safety_kpis(self):
        """Compute safety-related KPIs"""
        for record in self:
            try:
                domain = [
                    ('incident_date', '>=', record.date_from),
                    ('incident_date', '<=', record.date_to),
                ]
                
                if record.facility_ids:
                    domain.append(('facility_id', 'in', record.facility_ids.ids))
                
                record.safety_incidents = self.env['facilities.safety.incident'].search_count(domain)
                
            except Exception as e:
                _logger.warning(f"Error computing safety KPIs: {str(e)}")
                record.safety_incidents = 0
    
    @api.depends('facility_ids', 'date_from', 'date_to')
    def _compute_energy_kpis(self):
        """Compute energy-related KPIs"""
        for record in self:
            try:
                domain = [
                    ('reading_date', '>=', record.date_from),
                    ('reading_date', '<=', record.date_to),
                ]
                
                if record.facility_ids:
                    # Get utility meters for selected facilities
                    meters = self.env['facilities.utility.meter'].search([
                        ('facility_id', 'in', record.facility_ids.ids)
                    ])
                    if meters:
                        domain.append(('meter_id', 'in', meters.ids))
                
                consumptions = self.env['facilities.energy.consumption'].search(domain)
                record.total_energy_consumption = sum(consumptions.mapped('consumption_value'))
                record.energy_cost = sum(consumptions.mapped('cost'))
                
            except Exception as e:
                _logger.warning(f"Error computing energy KPIs: {str(e)}")
                record.total_energy_consumption = 0.0
                record.energy_cost = 0.0
    
    @api.depends('facility_ids', 'date_from', 'date_to')
    def _compute_dashboard_data(self):
        """Compute complete dashboard data as JSON for frontend consumption"""
        for record in self:
            try:
                record.dashboard_data = json.dumps({
                    'kpis': record._get_kpi_data(),
                    'charts': record._get_chart_data(),
                    'tables': record._get_table_data(),
                    'metadata': {
                        'period_type': record.period_type,
                        'date_from': record.date_from.isoformat() if record.date_from else None,
                        'date_to': record.date_to.isoformat() if record.date_to else None,
                        'last_updated': fields.Datetime.now().isoformat()
                    }
                })
            except Exception as e:
                _logger.error(f"Error computing dashboard data: {str(e)}")
                record.dashboard_data = json.dumps({'error': str(e)})
    
    def _get_kpi_data(self):
        """Get KPI data for dashboard"""
        self.ensure_one()
        
        # Calculate previous period for comparison
        period_days = (self.date_to - self.date_from).days
        previous_date_to = self.date_from - timedelta(days=1)
        previous_date_from = previous_date_to - timedelta(days=period_days)
        
        # Get previous period work orders for comparison
        prev_domain = [
            ('start_date', '>=', previous_date_from),
            ('start_date', '<=', previous_date_to),
        ]
        if self.facility_ids:
            prev_domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
        
        prev_workorders = self.env['facilities.workorder'].search_count(prev_domain)
        prev_completed = self.env['facilities.workorder'].search_count(
            prev_domain + [('state', '=', 'done')]
        )
        
        return [
            # Facility & Infrastructure
            {
                'name': _('Total Facilities'),
                'value': self.total_facilities,
                'previous_value': self.total_facilities,
                'icon': 'fa-building',
                'color': 'primary',
                'action': 'action_view_facilities'
            },
            {
                'name': _('Buildings'),
                'value': self.total_buildings,
                'previous_value': self.total_buildings,
                'icon': 'fa-building-o',
                'color': 'primary',
                'action': None
            },
            {
                'name': _('Rooms'),
                'value': self.total_rooms,
                'previous_value': self.total_rooms,
                'icon': 'fa-home',
                'color': 'primary',
                'action': None
            },
            
            # Assets
            {
                'name': _('Total Assets'),
                'value': self.total_assets,
                'previous_value': self.total_assets,
                'icon': 'fa-cube',
                'color': 'info',
                'action': 'action_view_assets'
            },
            {
                'name': _('Asset Value'),
                'value': f"${self.total_asset_value:,.0f}",
                'previous_value': 0,
                'icon': 'fa-money',
                'color': 'success',
                'action': 'action_view_assets'
            },
            {
                'name': _('Active Assets'),
                'value': self.active_assets,
                'previous_value': self.active_assets,
                'icon': 'fa-check-square-o',
                'color': 'success',
                'action': None
            },
            {
                'name': _('Under Maintenance'),
                'value': self.assets_under_maintenance,
                'previous_value': 0,
                'icon': 'fa-wrench',
                'color': 'warning',
                'action': None
            },
            
            # Work Orders
            {
                'name': _('Total Work Orders'),
                'value': self.total_workorders,
                'previous_value': prev_workorders,
                'icon': 'fa-tasks',
                'color': 'primary',
                'action': None
            },
            {
                'name': _('Assigned'),
                'value': self.open_workorders,
                'previous_value': 0,
                'icon': 'fa-clipboard',
                'color': 'info',
                'action': 'action_view_active_workorders'
            },
            {
                'name': _('In Progress'),
                'value': self.in_progress_workorders,
                'previous_value': 0,
                'icon': 'fa-cog fa-spin',
                'color': 'warning',
                'action': 'action_view_active_workorders'
            },
            {
                'name': _('Completed'),
                'value': self.completed_workorders,
                'previous_value': prev_completed,
                'icon': 'fa-check-circle',
                'color': 'success',
                'action': 'action_view_completed_workorders'
            },
            {
                'name': _('Overdue'),
                'value': self.overdue_workorders,
                'previous_value': 0,
                'icon': 'fa-exclamation-triangle',
                'color': 'danger',
                'action': 'action_view_overdue_workorders'
            },
            {
                'name': _('Completion Rate'),
                'value': f"{self.workorder_completion_rate:.1f}%",
                'previous_value': 0,
                'icon': 'fa-percent',
                'color': 'success' if self.workorder_completion_rate >= 80 else 'warning',
                'action': None
            },
            {
                'name': _('Avg Duration'),
                'value': f"{self.avg_workorder_duration:.1f}h",
                'previous_value': 0,
                'icon': 'fa-clock-o',
                'color': 'info',
                'action': None
            },
            
            # Maintenance
            {
                'name': _('Preventive Maintenance'),
                'value': self.preventive_maintenance_count,
                'previous_value': 0,
                'icon': 'fa-calendar-check-o',
                'color': 'success',
                'action': None
            },
            {
                'name': _('Corrective Maintenance'),
                'value': self.corrective_maintenance_count,
                'previous_value': 0,
                'icon': 'fa-wrench',
                'color': 'warning',
                'action': None
            },
            {
                'name': _('Maintenance Cost'),
                'value': f"${self.total_maintenance_cost:,.0f}",
                'previous_value': 0,
                'icon': 'fa-dollar',
                'color': 'info',
                'action': 'action_view_maintenance_costs'
            },
            
            # Financial
            {
                'name': _('Total Budget'),
                'value': f"${self.total_budget:,.0f}",
                'previous_value': 0,
                'icon': 'fa-pie-chart',
                'color': 'primary',
                'action': None
            },
            {
                'name': _('Total Expenses'),
                'value': f"${self.total_expenses:,.0f}",
                'previous_value': 0,
                'icon': 'fa-credit-card',
                'color': 'danger',
                'action': None
            },
            {
                'name': _('Budget Utilization'),
                'value': f"{self.budget_utilization:.1f}%",
                'previous_value': 0,
                'icon': 'fa-line-chart',
                'color': 'danger' if self.budget_utilization > 90 else 'warning' if self.budget_utilization > 75 else 'success',
                'action': None
            },
            
            # Space & Services
            {
                'name': _('Total Bookings'),
                'value': self.total_bookings,
                'previous_value': 0,
                'icon': 'fa-calendar',
                'color': 'primary',
                'action': 'action_view_bookings'
            },
            {
                'name': _('Active Bookings'),
                'value': self.active_bookings,
                'previous_value': 0,
                'icon': 'fa-calendar-check-o',
                'color': 'success',
                'action': 'action_view_bookings'
            },
            {
                'name': _('Space Utilization'),
                'value': f"{self.space_utilization:.1f}%",
                'previous_value': 0,
                'icon': 'fa-inbox',
                'color': 'info',
                'action': 'action_view_bookings'
            },
            {
                'name': _('Service Requests'),
                'value': self.total_service_requests,
                'previous_value': 0,
                'icon': 'fa-life-ring',
                'color': 'primary',
                'action': None
            },
            {
                'name': _('Pending Requests'),
                'value': self.pending_service_requests,
                'previous_value': 0,
                'icon': 'fa-hourglass-half',
                'color': 'warning',
                'action': None
            },
            {
                'name': _('Resolved Requests'),
                'value': self.resolved_service_requests,
                'previous_value': 0,
                'icon': 'fa-check',
                'color': 'success',
                'action': None
            },
            
            # Safety & Energy
            {
                'name': _('Safety Incidents'),
                'value': self.safety_incidents,
                'previous_value': 0,
                'icon': 'fa-shield',
                'color': 'danger' if self.safety_incidents > 0 else 'success',
                'action': None
            },
            {
                'name': _('Energy Consumption'),
                'value': f"{self.total_energy_consumption:,.0f} kWh",
                'previous_value': 0,
                'icon': 'fa-bolt',
                'color': 'warning',
                'action': None
            },
            {
                'name': _('Energy Cost'),
                'value': f"${self.energy_cost:,.0f}",
                'previous_value': 0,
                'icon': 'fa-usd',
                'color': 'danger',
                'action': None
            },
        ]
    
    def _get_chart_data(self):
        """Get chart data for dashboard"""
        self.ensure_one()
        
        return [
            self._get_workorder_status_chart(),
            self._get_maintenance_type_chart(),
            self._get_workorder_trend_chart(),
            self._get_asset_status_chart(),
            self._get_workorder_priority_chart(),
            self._get_monthly_maintenance_cost_chart(),
            self._get_technician_workload_chart(),
            self._get_asset_value_by_facility_chart(),
        ]
    
    def _get_workorder_status_chart(self):
        """Get work order status distribution chart"""
        return {
            'type': 'doughnut',
            'title': _('Work Order Status'),
            'labels': [_('Assigned'), _('In Progress'), _('Completed'), _('Overdue')],
            'datasets': [{
                'label': _('Work Orders'),
                'data': [
                    self.open_workorders,
                    self.in_progress_workorders,
                    self.completed_workorders,
                    self.overdue_workorders
                ],
                'backgroundColor': [
                    'rgba(54, 162, 235, 0.7)',
                    'rgba(255, 206, 86, 0.7)',
                    'rgba(75, 192, 192, 0.7)',
                    'rgba(255, 99, 132, 0.7)'
                ]
            }],
            'drilldown': 'action_drilldown_by_status'
        }
    
    def _get_maintenance_type_chart(self):
        """Get maintenance type distribution chart"""
        return {
            'type': 'pie',
            'title': _('Maintenance Type Distribution'),
            'labels': [_('Preventive'), _('Corrective')],
            'datasets': [{
                'label': _('Maintenance'),
                'data': [
                    self.preventive_maintenance_count,
                    self.corrective_maintenance_count
                ],
                'backgroundColor': [
                    'rgba(75, 192, 192, 0.7)',
                    'rgba(255, 99, 132, 0.7)'
                ]
            }],
            'drilldown': 'action_drilldown_by_maintenance_type'
        }
    
    def _get_workorder_trend_chart(self):
        """Get work order trend over time"""
        labels = []
        completed_data = []
        created_data = []
        
        # Get last 7 days of data
        for i in range(6, -1, -1):
            day = fields.Date.today() - timedelta(days=i)
            labels.append(day.strftime('%a'))
            
            domain = [
                ('start_date', '=', day),
            ]
            if self.facility_ids:
                domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
            
            created = self.env['facilities.workorder'].search_count(domain)
            completed = self.env['facilities.workorder'].search_count(
                domain + [('state', '=', 'done')]
            )
            
            created_data.append(created)
            completed_data.append(completed)
        
        return {
            'type': 'line',
            'title': _('Work Orders - Last 7 Days'),
            'labels': labels,
            'datasets': [
                {
                    'label': _('Created'),
                    'data': created_data,
                    'borderColor': 'rgba(54, 162, 235, 1)',
                    'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                    'fill': True
                },
                {
                    'label': _('Completed'),
                    'data': completed_data,
                    'borderColor': 'rgba(75, 192, 192, 1)',
                    'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                    'fill': True
                }
            ]
        }
    
    def _get_asset_status_chart(self):
        """Get asset status distribution chart"""
        domain = []
        if self.facility_ids:
            domain = [('facility_id', 'in', self.facility_ids.ids)]
        
        assets = self.env['facilities.asset'].search(domain)
        
        status_counts = {}
        for asset in assets:
            status = asset.state or 'unknown'
            status_counts[status] = status_counts.get(status, 0) + 1
        
        labels = [dict(self.env['facilities.asset']._fields['state'].selection).get(s, s) 
                  for s in status_counts.keys()]
        data = list(status_counts.values())
        
        return {
            'type': 'bar',
            'title': _('Asset Status Distribution'),
            'labels': labels,
            'datasets': [{
                'label': _('Assets'),
                'data': data,
                'backgroundColor': 'rgba(153, 102, 255, 0.7)',
                'borderColor': 'rgba(153, 102, 255, 1)',
                'borderWidth': 1
            }],
            'drilldown': 'action_drilldown_assets_by_status'
        }
    
    def _get_table_data(self):
        """Get table data for dashboard"""
        self.ensure_one()
        
        # Get recent work orders
        domain = [
            ('start_date', '>=', self.date_from),
            ('start_date', '<=', self.date_to),
        ]
        if self.facility_ids:
            domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
        
        workorders = self.env['facilities.workorder'].search(
            domain,
            limit=10,
            order='start_date desc'
        )
        
        rows = []
        for wo in workorders:
            rows.append([
                wo.name,
                wo.work_location_facility_id.name if wo.work_location_facility_id else '',
                wo.asset_id.name if wo.asset_id else '',
                wo.state,
                wo.start_date.strftime('%Y-%m-%d') if wo.start_date else '',
                wo.priority
            ])
        
        return {
            'title': _('Recent Work Orders'),
            'columns': [
                _('Work Order'),
                _('Facility'),
                _('Asset'),
                _('Status'),
                _('Scheduled Date'),
                _('Priority')
            ],
            'rows': rows
        }
    
    # ==================== ACTION METHODS ====================
    
    def action_refresh_dashboard(self):
        """Refresh dashboard data"""
        self.ensure_one()
        self._compute_facility_kpis()
        self._compute_asset_kpis()
        self._compute_workorder_kpis()
        self._compute_maintenance_kpis()
        self._compute_financial_kpis()
        self._compute_booking_kpis()
        self._compute_service_request_kpis()
        self._compute_safety_kpis()
        self._compute_energy_kpis()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def action_view_facilities(self):
        """View all facilities"""
        domain = []
        if self.facility_ids:
            domain = [('id', 'in', self.facility_ids.ids)]
        
        return {
            'name': _('Facilities'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.facility',
            'view_mode': 'kanban,list,form',
            'domain': domain,
        }
    
    def action_view_assets(self):
        """View all assets"""
        domain = []
        if self.facility_ids:
            domain = [('facility_id', 'in', self.facility_ids.ids)]
        
        return {
            'name': _('Assets'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.asset',
            'view_mode': 'kanban,list,form',
            'domain': domain,
        }
    
    def action_view_active_workorders(self):
        """View active work orders"""
        domain = [
            ('start_date', '>=', self.date_from),
            ('start_date', '<=', self.date_to),
            ('state', 'in', ['open', 'in_progress']),
        ]
        if self.facility_ids:
            domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
        
        return {
            'name': _('Active Work Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'kanban,list,form',
            'domain': domain,
        }
    
    def action_view_completed_workorders(self):
        """View completed work orders"""
        domain = [
            ('start_date', '>=', self.date_from),
            ('start_date', '<=', self.date_to),
            ('state', '=', 'done'),
        ]
        if self.facility_ids:
            domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
        
        return {
            'name': _('Completed Work Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,form',
            'domain': domain,
        }
    
    def action_view_overdue_workorders(self):
        """View overdue work orders"""
        today = fields.Date.today()
        domain = [
            ('start_date', '<', today),
            ('state', 'not in', ['done', 'cancelled']),
        ]
        if self.facility_ids:
            domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
        
        return {
            'name': _('Overdue Work Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'search_default_group_by_facility': 1}
        }
    
    def action_view_maintenance_costs(self):
        """View maintenance costs breakdown"""
        domain = [
            ('start_date', '>=', self.date_from),
            ('start_date', '<=', self.date_to),
        ]
        if self.facility_ids:
            domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
        
        return {
            'name': _('Maintenance Costs'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,form',
            'domain': domain,
        }
    
    def action_view_bookings(self):
        """View space bookings"""
        domain = [
            ('booking_date', '>=', self.date_from),
            ('booking_date', '<=', self.date_to),
        ]
        if self.facility_ids:
            rooms = self.env['facilities.room'].search([
                ('facility_id', 'in', self.facility_ids.ids)
            ])
            if rooms:
                domain.append(('room_id', 'in', rooms.ids))
        
        return {
            'name': _('Space Bookings'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.space.booking',
            'view_mode': 'calendar,list,form',
            'domain': domain,
        }
    
    @api.model
    def get_dashboard_data_api(self, dashboard_id=None, filters=None):
        """
        API method for fetching dashboard data via RPC
        
        Args:
            dashboard_id: ID of dashboard record (optional, will use first if not provided)
            filters: Dictionary of filters to apply (optional)
        
        Returns:
            Dictionary containing dashboard data
        """
        if dashboard_id:
            dashboard = self.browse(dashboard_id)
        else:
            dashboard = self.search([], limit=1)
            if not dashboard:
                # Create a default dashboard if none exists
                dashboard = self.create({
                    'name': 'Main Dashboard',
                    'period_type': 'month',
                })
        
        # Apply filters if provided
        if filters:
            dashboard.write(filters)
        
        return json.loads(dashboard.dashboard_data)
    
    def _get_workorder_priority_chart(self):
        """Get work order priority distribution chart"""
        domain = [
            ('start_date', '>=', self.date_from),
            ('start_date', '<=', self.date_to),
        ]
        if self.facility_ids:
            domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
        
        workorders = self.env['facilities.workorder'].search(domain)
        
        priority_counts = {}
        priority_labels = {
            '0': 'Very Low',
            '1': 'Low',
            '2': 'Normal',
            '3': 'High',
            '4': 'Critical'
        }
        
        for wo in workorders:
            priority = wo.priority or '0'
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        labels = [priority_labels.get(p, p) for p in sorted(priority_counts.keys())]
        data = [priority_counts[p] for p in sorted(priority_counts.keys())]
        
        return {
            'type': 'bar',
            'title': _('Work Orders by Priority'),
            'labels': labels,
            'datasets': [{
                'label': _('Work Orders'),
                'data': data,
                'backgroundColor': [
                    'rgba(108, 117, 125, 0.7)',  # Very Low - gray
                    'rgba(13, 202, 240, 0.7)',   # Low - info
                    'rgba(13, 110, 253, 0.7)',   # Normal - primary
                    'rgba(255, 193, 7, 0.7)',    # High - warning
                    'rgba(220, 53, 69, 0.7)',    # Critical - danger
                ],
                'borderColor': [
                    'rgba(108, 117, 125, 1)',
                    'rgba(13, 202, 240, 1)',
                    'rgba(13, 110, 253, 1)',
                    'rgba(255, 193, 7, 1)',
                    'rgba(220, 53, 69, 1)',
                ],
                'borderWidth': 1
            }],
            'drilldown': 'action_drilldown_by_priority'
        }
    
    def _get_monthly_maintenance_cost_chart(self):
        """Get maintenance cost trend over last 6 months"""
        labels = []
        cost_data = []
        
        # Get last 6 months
        for i in range(5, -1, -1):
            month_date = fields.Date.today() - timedelta(days=30 * i)
            month_start = month_date.replace(day=1)
            
            # Calculate month end
            if month_date.month == 12:
                month_end = month_date.replace(day=31)
            else:
                next_month = month_date.replace(month=month_date.month + 1, day=1)
                month_end = next_month - timedelta(days=1)
            
            labels.append(month_date.strftime('%b %Y'))
            
            domain = [
                ('start_date', '>=', month_start),
                ('start_date', '<=', month_end),
            ]
            if self.facility_ids:
                domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
            
            workorders = self.env['facilities.workorder'].search(domain)
            total_cost = sum(workorders.mapped('labor_cost')) + sum(workorders.mapped('parts_cost'))
            cost_data.append(total_cost)
        
        return {
            'type': 'line',
            'title': _('Maintenance Cost Trend (6 Months)'),
            'labels': labels,
            'datasets': [{
                'label': _('Total Cost ($)'),
                'data': cost_data,
                'borderColor': 'rgba(13, 110, 253, 1)',
                'backgroundColor': 'rgba(13, 110, 253, 0.1)',
                'fill': True,
                'tension': 0.4
            }]
        }
    
    def _get_technician_workload_chart(self):
        """Get technician workload distribution"""
        domain = [
            ('start_date', '>=', self.date_from),
            ('start_date', '<=', self.date_to),
        ]
        if self.facility_ids:
            domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
        
        workorders = self.env['facilities.workorder'].search(domain)
        
        tech_workload = {}
        for wo in workorders:
            if wo.technician_id:
                tech_name = wo.technician_id.name
                tech_workload[tech_name] = tech_workload.get(tech_name, 0) + 1
        
        # Sort by workload and get top 10
        sorted_techs = sorted(tech_workload.items(), key=lambda x: x[1], reverse=True)[:10]
        
        labels = [tech[0] for tech in sorted_techs]
        data = [tech[1] for tech in sorted_techs]
        
        return {
            'type': 'bar',
            'title': _('Top Technicians by Work Orders'),
            'labels': labels,
            'datasets': [{
                'label': _('Work Orders'),
                'data': data,
                'backgroundColor': 'rgba(75, 192, 192, 0.7)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 1
            }],
            'drilldown': 'action_drilldown_by_technician'
        }
    
    def _get_asset_value_by_facility_chart(self):
        """Get asset value distribution by facility"""
        domain = []
        if self.facility_ids:
            domain = [('id', 'in', self.facility_ids.ids)]
        
        facilities = self.env['facilities.facility'].search(domain, limit=10)
        
        labels = []
        data = []
        
        for facility in facilities:
            assets = self.env['facilities.asset'].search([('facility_id', '=', facility.id)])
            total_value = sum(assets.mapped('purchase_cost'))
            if total_value > 0:
                labels.append(facility.name)
                data.append(total_value)
        
        return {
            'type': 'bar',
            'title': _('Asset Value by Facility'),
            'labels': labels,
            'datasets': [{
                'label': _('Asset Value ($)'),
                'data': data,
                'backgroundColor': 'rgba(255, 159, 64, 0.7)',
                'borderColor': 'rgba(255, 159, 64, 1)',
                'borderWidth': 1
            }],
            'drilldown': 'action_drilldown_by_facility'
        }
    
    # ==================== DRILL-DOWN ACTION METHODS ====================
    
    def action_drilldown_by_status(self, label=None, index=None, **kwargs):
        """Drill-down work orders by status from chart click"""
        self.ensure_one()
        
        # Map chart labels to state values
        state_mapping = {
            'Assigned': 'assigned',
            'In Progress': 'in_progress',
            'Completed': 'completed',
            'Overdue': 'assigned',  # Overdue items are actually in assigned state but past due
        }
        
        domain = [
            ('start_date', '>=', self.date_from),
            ('start_date', '<=', self.date_to),
        ]
        
        if self.facility_ids:
            domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
        
        if label and label in state_mapping:
            if label == 'Overdue':
                # Overdue: assigned/in_progress but start date in the past
                domain.extend([
                    ('state', 'not in', ['completed', 'cancelled']),
                    ('start_date', '<', fields.Date.today())
                ])
            else:
                domain.append(('state', '=', state_mapping[label]))
        
        return {
            'name': _('Work Orders - %s') % (label or 'All'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,kanban,form',
            'domain': domain,
            'context': {'create': False}
        }
    
    def action_drilldown_by_maintenance_type(self, label=None, index=None, **kwargs):
        """Drill-down work orders by maintenance type"""
        self.ensure_one()
        
        domain = [
            ('start_date', '>=', self.date_from),
            ('start_date', '<=', self.date_to),
        ]
        
        if self.facility_ids:
            domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
        
        if label:
            if 'Preventive' in label:
                domain.append(('maintenance_type', '=', 'preventive'))
            elif 'Corrective' in label:
                domain.append(('maintenance_type', '=', 'corrective'))
        
        return {
            'name': _('Work Orders - %s') % (label or 'All Types'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,kanban,form',
            'domain': domain,
            'context': {'create': False}
        }
    
    def action_drilldown_assets_by_status(self, label=None, index=None, **kwargs):
        """Drill-down assets by status from chart click"""
        self.ensure_one()
        
        domain = []
        if self.facility_ids:
            domain = [('facility_id', 'in', self.facility_ids.ids)]
        
        # Map display label back to state value
        state_reverse_map = {
            'Draft': 'draft',
            'Active': 'active',
            'Under Maintenance': 'maintenance',
            'Disposed': 'disposed'
        }
        
        if label and label in state_reverse_map:
            domain.append(('state', '=', state_reverse_map[label]))
        
        return {
            'name': _('Assets - %s') % (label or 'All'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.asset',
            'view_mode': 'list,kanban,form',
            'domain': domain,
            'context': {'create': False}
        }
    
    def action_drilldown_by_priority(self, label=None, index=None, **kwargs):
        """Drill-down work orders by priority"""
        self.ensure_one()
        
        domain = [
            ('start_date', '>=', self.date_from),
            ('start_date', '<=', self.date_to),
        ]
        
        if self.facility_ids:
            domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
        
        # Map priority label to value
        priority_map = {
            'Very Low': '0',
            'Low': '1',
            'Normal': '2',
            'High': '3',
            'Critical': '4'
        }
        
        if label and label in priority_map:
            domain.append(('priority', '=', priority_map[label]))
        
        return {
            'name': _('Work Orders - Priority: %s') % (label or 'All'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,kanban,form',
            'domain': domain,
            'context': {'create': False}
        }
    
    def action_drilldown_by_technician(self, label=None, index=None, **kwargs):
        """Drill-down work orders by technician"""
        self.ensure_one()
        
        domain = [
            ('start_date', '>=', self.date_from),
            ('start_date', '<=', self.date_to),
        ]
        
        if self.facility_ids:
            domain.append(('work_location_facility_id', 'in', self.facility_ids.ids))
        
        if label:
            # Find technician by name
            technician = self.env['hr.employee'].search([('name', '=', label)], limit=1)
            if technician:
                domain.append(('technician_id', '=', technician.id))
        
        return {
            'name': _('Work Orders - Technician: %s') % (label or 'All'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,kanban,form',
            'domain': domain,
            'context': {'create': False}
        }
    
    def action_drilldown_by_facility(self, label=None, index=None, **kwargs):
        """Drill-down assets by facility"""
        self.ensure_one()
        
        domain = []
        
        if label:
            # Find facility by name
            facility = self.env['facilities.facility'].search([('name', '=', label)], limit=1)
            if facility:
                domain.append(('facility_id', '=', facility.id))
        elif self.facility_ids:
            domain = [('facility_id', 'in', self.facility_ids.ids)]
        
        return {
            'name': _('Assets - Facility: %s') % (label or 'All'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.asset',
            'view_mode': 'list,kanban,form',
            'domain': domain,
            'context': {'create': False}
        }

