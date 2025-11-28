from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
import logging
from datetime import datetime, timedelta, date

_logger = logging.getLogger(__name__)


class AssetPerformanceDashboard(models.Model):
    _name = 'facilities.asset.performance.dashboard'
    _description = 'Asset Performance Dashboard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # Basic Information
    name = fields.Char(string='Performance Analysis Name', required=True, tracking=True)
    date_from = fields.Date(string='Date From', required=True, default=fields.Date.context_today, tracking=True)
    date_to = fields.Date(string='Date To', required=True, default=fields.Date.context_today, tracking=True)
    
    # Asset Selection
    facility_id = fields.Many2one('facilities.facility', string='Filter by Facility', tracking=True,
                                 help='Filter assets by specific facility. Leave empty to include all facilities.')
    asset_ids = fields.Many2many('facilities.asset', string='Assets', tracking=True)
    
    # State Management
    state = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error')
    ], string='State', default='draft', tracking=True, required=True)
    
    # Performance Metrics
    total_assets = fields.Integer(string='Total Assets', compute='_compute_metrics', store=True)
    total_value = fields.Float(string='Total Value', compute='_compute_metrics', store=True)
    avg_roi = fields.Float(string='Average ROI (%)', compute='_compute_metrics', store=True)
    efficiency_score = fields.Float(string='Efficiency Score', compute='_compute_metrics', store=True)
    
    # Operational Metrics
    utilization_rate = fields.Float(string='Utilization Rate (%)', compute='_compute_metrics', store=True)
    downtime_hours = fields.Float(string='Downtime Hours', compute='_compute_metrics', store=True)
    uptime_percentage = fields.Float(string='Uptime Percentage (%)', compute='_compute_metrics', store=True)
    
    # Financial Metrics
    revenue_generated = fields.Float(string='Revenue Generated', compute='_compute_metrics', store=True)
    operating_cost = fields.Float(string='Operating Cost', compute='_compute_metrics', store=True)
    net_profit = fields.Float(string='Net Profit', compute='_compute_metrics', store=True)
    profit_margin = fields.Float(string='Profit Margin (%)', compute='_compute_metrics', store=True)
    
    # Maintenance Metrics
    maintenance_cost = fields.Float(string='Maintenance Cost', compute='_compute_metrics', store=True)
    maintenance_efficiency = fields.Float(string='Maintenance Efficiency (%)', compute='_compute_metrics', store=True)
    asset_health_score = fields.Float(string='Asset Health Score', compute='_compute_metrics', store=True)
    
    # Work Order Metrics
    total_workorders = fields.Integer(string='Total Work Orders', compute='_compute_metrics', store=True)
    completed_workorders = fields.Integer(string='Completed Work Orders', compute='_compute_metrics', store=True)
    pending_workorders = fields.Integer(string='Pending Work Orders', compute='_compute_metrics', store=True)
    overdue_workorders = fields.Integer(string='Overdue Work Orders', compute='_compute_metrics', store=True)
    workorder_completion_rate = fields.Float(string='Work Order Completion Rate (%)', compute='_compute_metrics', store=True)
    avg_workorder_duration = fields.Float(string='Average Work Order Duration (hours)', compute='_compute_metrics', store=True)
    total_labor_hours = fields.Float(string='Total Labor Hours', compute='_compute_metrics', store=True)
    total_labor_cost = fields.Float(string='Total Labor Cost', compute='_compute_metrics', store=True)
    
    # Results Storage
    performance_data = fields.Text(string='Performance Data', readonly=True)
    
    # Technical fields
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company, 
                                tracking=True, index=True)
    create_date = fields.Datetime(string='Created on', readonly=True)
    write_date = fields.Datetime(string='Last Updated on', readonly=True)
    create_uid = fields.Many2one('res.users', string='Created by', readonly=True)
    write_uid = fields.Many2one('res.users', string='Last Updated by', readonly=True)

    @api.onchange('facility_id')
    def _onchange_facility_id(self):
        """Filter assets by selected facility"""
        if self.facility_id:
            return {'domain': {'asset_ids': [('facility_id', '=', self.facility_id.id)]}}
        else:
            return {'domain': {'asset_ids': []}}

    @api.depends('asset_ids', 'date_from', 'date_to', 'facility_id')
    def _compute_metrics(self):
        """Compute all performance metrics using unified calculation method"""
        for record in self:
            if record.date_from and record.date_to:
                try:
                    # Use the unified calculation method from asset.performance model
                    _logger.info(f"Form Dashboard calling unified method - Assets: {len(record.asset_ids)}, Facility: {record.facility_id}")
                    metrics = self.env['facilities.asset.performance']._get_unified_dashboard_metrics(
                        record.date_from, 
                        record.date_to, 
                        record.facility_id.id if record.facility_id else None,
                        record.asset_ids.ids if record.asset_ids else None
                    )
                    
                    # Apply all calculated metrics to the record
                    for field_name, value in metrics.items():
                        if hasattr(record, field_name):
                            setattr(record, field_name, value)
                    
                    _logger.info(f"Form Dashboard metrics applied - Assets: {record.total_assets}, Value: ${record.total_value}")
                    
                except Exception as e:
                    _logger.error(f"Error computing metrics for dashboard {record.id}: {str(e)}")
                    # Set default values on error
                    default_metrics = self.env['facilities.asset.performance']._get_default_metrics()
                    for field_name, value in default_metrics.items():
                        if hasattr(record, field_name):
                            setattr(record, field_name, value)
                    
                    # Override asset count with manual calculation as fallback
                    record.total_assets = len(record.asset_ids) if record.asset_ids else 0
                    record.total_value = sum(asset.purchase_cost or 0 for asset in record.asset_ids) if record.asset_ids else 0
            else:
                # Reset all computed fields when no date range
                default_metrics = self.env['facilities.asset.performance']._get_default_metrics()
                for field_name, value in default_metrics.items():
                    if hasattr(record, field_name):
                        setattr(record, field_name, value)

    def action_process(self):
        """Process the asset performance analysis"""
        self.ensure_one()
        self.state = 'processing'
        try:
            # Force recomputation of all metrics
            self._compute_metrics()
            
            # Store performance data as JSON
            performance_data = {
                'analysis_date': fields.Datetime.now().isoformat(),
                'period': {
                    'from': self.date_from.isoformat() if self.date_from else None,
                    'to': self.date_to.isoformat() if self.date_to else None
                },
                'assets': {
                    'total': self.total_assets,
                    'selected': [{'id': asset.id, 'name': asset.name} for asset in self.asset_ids]
                },
                'metrics': {
                    'total_value': self.total_value,
                    'avg_roi': self.avg_roi,
                    'efficiency_score': self.efficiency_score,
                    'utilization_rate': self.utilization_rate,
                    'downtime_hours': self.downtime_hours,
                    'uptime_percentage': self.uptime_percentage,
                    'revenue_generated': self.revenue_generated,
                    'operating_cost': self.operating_cost,
                    'net_profit': self.net_profit,
                    'profit_margin': self.profit_margin,
                    'maintenance_cost': self.maintenance_cost,
                    'maintenance_efficiency': self.maintenance_efficiency,
                    'asset_health_score': self.asset_health_score
                }
            }
            
            self.performance_data = json.dumps(performance_data, indent=2)
            self.state = 'completed'
            
        except Exception as e:
            self.state = 'error'
            _logger.error(f"Error processing asset performance analysis: {str(e)}")
            raise ValidationError(f"Analysis processing failed: {str(e)}")

    def action_reset(self):
        """Reset to draft state"""
        self.ensure_one()
        self.write({
            'state': 'draft',
            'performance_data': ''
        })

    def _calculate_revenue(self, performance_records):
        """Calculate revenue generated by assets"""
        if not performance_records:
            return 0.0
        
        # Simplified calculation: $100 per hour of operation
        total_runtime = sum(performance_records.mapped('actual_runtime'))
        return total_runtime * 100

    def _calculate_operating_costs(self):
        """Calculate operating costs"""
        if not self.asset_ids or not self.date_from or not self.date_to:
            return 0.0
        
        # Note: Standard maintenance.request model doesn't have asset_id field
        # For now, return default value. In a full implementation, you would need to:
        # 1. Create a custom maintenance request model extending maintenance.request
        # 2. Or create a mapping between facilities.asset and maintenance.equipment
        return 0.0  # Default operating cost

    def _calculate_efficiency_score(self, performance_records):
        """Calculate overall efficiency score"""
        if not performance_records:
            return 0.0
        
        # Calculate based on utilization and availability
        utilization = self.utilization_rate
        avg_availability = sum(performance_records.mapped('availability_percentage')) / len(performance_records)
        
        return (utilization + avg_availability) / 2

    def _calculate_asset_health_score(self, performance_records):
        """Calculate asset health score"""
        if not performance_records:
            return 0.0
        
        # Calculate based on average availability and performance status
        avg_availability = sum(performance_records.mapped('availability_percentage')) / len(performance_records)
        
        # Bonus for excellent performance records
        excellent_count = len(performance_records.filtered(lambda r: r.performance_status == 'excellent'))
        bonus = (excellent_count / len(performance_records)) * 10 if performance_records else 0
        
        return min(100, avg_availability + bonus)

    def _calculate_maintenance_efficiency(self):
        """Calculate maintenance efficiency"""
        # Note: Standard maintenance.request model doesn't have asset_id field
        # For now, return default value. In a full implementation, you would need to:
        # 1. Create a custom maintenance request model extending maintenance.request
        # 2. Or create a mapping between facilities.asset and maintenance.equipment
        return 85.0  # Default efficiency score

    def _calculate_maintenance_costs(self):
        """Calculate maintenance costs"""
        # Note: Standard maintenance.request model doesn't have asset_id field
        # For now, return default value. In a full implementation, you would need to:
        # 1. Create a custom maintenance request model extending maintenance.request
        # 2. Or create a mapping between facilities.asset and maintenance.equipment
        return 0.0  # Default maintenance cost

    def _calculate_workorder_metrics(self):
        """Calculate work order metrics for the selected assets and date range"""
        if not self.asset_ids or not self.date_from or not self.date_to:
            return {
                'total_workorders': 0,
                'completed_workorders': 0,
                'pending_workorders': 0,
                'overdue_workorders': 0,
                'completion_rate': 0,
                'avg_duration': 0,
                'total_labor_hours': 0,
                'total_labor_cost': 0,
            }
        
        try:
            # Get work orders for the selected assets within the date range
            workorders = self.env['facilities.workorder'].search([
                ('asset_id', 'in', self.asset_ids.ids),
                '|',
                ('date_scheduled', '>=', self.date_from),
                ('date_scheduled', '<=', self.date_to),
                '|',
                ('date_scheduled', '=', False),  # Include work orders without scheduled date
                ('create_date', '>=', self.date_from),
            ])
            
            # Also include facility-based work orders if facility filter is set
            if self.facility_id:
                facility_workorders = self.env['facilities.workorder'].search([
                    ('work_location_facility_id', '=', self.facility_id.id),
                    '|',
                    ('date_scheduled', '>=', self.date_from),
                    ('date_scheduled', '<=', self.date_to),
                    '|',
                    ('date_scheduled', '=', False),
                    ('create_date', '>=', self.date_from),
                ])
                workorders = workorders | facility_workorders
            
            total_workorders = len(workorders)
            completed_workorders = len(workorders.filtered(lambda w: w.state == 'done'))
            pending_workorders = len(workorders.filtered(lambda w: w.state in ['draft', 'open', 'in_progress']))
            
            # Calculate overdue work orders
            today = fields.Date.context_today(self)
            overdue_workorders = len(workorders.filtered(
                lambda w: w.date_scheduled and w.date_scheduled < today and w.state not in ['done', 'cancelled']
            ))
            
            completion_rate = (completed_workorders / total_workorders * 100) if total_workorders > 0 else 0
            
            # Calculate average duration for completed work orders
            completed_with_duration = workorders.filtered(lambda w: w.state == 'done' and w.date_start and w.date_done)
            if completed_with_duration:
                total_duration = 0
                for wo in completed_with_duration:
                    duration = (wo.date_done - wo.date_start).total_seconds() / 3600  # Convert to hours
                    total_duration += duration
                avg_duration = total_duration / len(completed_with_duration)
            else:
                avg_duration = 0
            
            # Calculate labor hours and costs from assignments
            assignments = self.env['facilities.workorder.assignment'].search([
                ('workorder_id', 'in', workorders.ids)
            ])
            
            total_labor_hours = sum(assignments.mapped('work_hours'))
            total_labor_cost = sum(assignments.mapped('labor_cost'))
            
            return {
                'total_workorders': total_workorders,
                'completed_workorders': completed_workorders,
                'pending_workorders': pending_workorders,
                'overdue_workorders': overdue_workorders,
                'completion_rate': completion_rate,
                'avg_duration': avg_duration,
                'total_labor_hours': total_labor_hours,
                'total_labor_cost': total_labor_cost,
            }
            
        except Exception as e:
            _logger.error(f"Error calculating work order metrics: {str(e)}")
            return {
                'total_workorders': 0,
                'completed_workorders': 0,
                'pending_workorders': 0,
                'overdue_workorders': 0,
                'completion_rate': 0,
                'avg_duration': 0,
                'total_labor_hours': 0,
                'total_labor_cost': 0,
            }

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set initial state"""
        for vals in vals_list:
            vals['state'] = 'draft'
        return super().create(vals_list)
    
    @api.model
    def get_dashboard_data_api(self, dashboard_id=None, filters=None):
        """API method for KPI card dashboard"""
        today = fields.Date.today()
        period_type = filters.get('period_type', 'month') if filters else 'month'
        
        # Calculate date range
        if filters and filters.get('date_from') and filters.get('date_to'):
            date_from = fields.Date.from_string(filters['date_from'])
            date_to = fields.Date.from_string(filters['date_to'])
        elif period_type == 'today':
            date_from = date_to = today
        elif period_type == 'week':
            date_from = today - timedelta(days=today.weekday())
            date_to = today
        elif period_type == 'month':
            date_from = today.replace(day=1)
            date_to = today
        elif period_type == 'quarter':
            quarter = (today.month - 1) // 3
            date_from = date(today.year, quarter * 3 + 1, 1)
            date_to = today
        elif period_type == 'year':
            date_from = date(today.year, 1, 1)
            date_to = today
        else:
            date_from = today.replace(day=1)
            date_to = today
        
        facility_id = filters.get('facility_id') if filters else None
        
        # Get metrics
        metrics = self.env['facilities.asset.performance']._get_unified_dashboard_metrics(
            date_from, date_to, facility_id, None
        )
        
        # Build KPIs with drilldown keys
        kpis = [
            {'name': _('Total Assets'), 'value': metrics.get('total_assets', 0), 'icon': 'fa-cubes', 'color': 'primary', 'key': 'total_assets'},
            {'name': _('Asset Value'), 'value': f"${metrics.get('total_value', 0):,.0f}", 'icon': 'fa-money', 'color': 'success', 'key': 'total_value'},
            {'name': _('Avg Health Score'), 'value': f"{metrics.get('asset_health_score', 0):.1f}%", 'icon': 'fa-heartbeat', 
             'color': 'success' if metrics.get('asset_health_score', 0) >= 80 else 'warning', 'key': 'asset_health_score'},
            {'name': _('Uptime'), 'value': f"{metrics.get('uptime_percentage', 0):.1f}%", 'icon': 'fa-check-circle', 
             'color': 'success' if metrics.get('uptime_percentage', 0) >= 95 else 'warning', 'key': 'utilization_rate'},
            {'name': _('Utilization'), 'value': f"{metrics.get('utilization_rate', 0):.1f}%", 'icon': 'fa-tasks', 'color': 'info', 'key': 'utilization_rate'},
            {'name': _('Downtime'), 'value': f"{metrics.get('downtime_hours', 0):.1f}h", 'icon': 'fa-pause-circle', 
             'color': 'danger' if metrics.get('downtime_hours', 0) > 10 else 'warning', 'key': 'downtime_hours'},
            {'name': _('Work Orders'), 'value': metrics.get('total_workorders', 0), 'icon': 'fa-clipboard', 'color': 'primary', 'key': 'total_workorders'},
            {'name': _('Completed'), 'value': metrics.get('completed_workorders', 0), 'icon': 'fa-check', 'color': 'success', 'key': 'completed_workorders'},
            {'name': _('Pending'), 'value': metrics.get('pending_workorders', 0), 'icon': 'fa-hourglass-half', 'color': 'warning', 'key': 'pending_workorders'},
            {'name': _('Overdue'), 'value': metrics.get('overdue_workorders', 0), 'icon': 'fa-exclamation-triangle', 'color': 'danger', 'key': 'overdue_workorders'},
            {'name': _('Completion Rate'), 'value': f"{metrics.get('workorder_completion_rate', 0):.1f}%", 'icon': 'fa-percent', 
             'color': 'success' if metrics.get('workorder_completion_rate', 0) >= 80 else 'warning', 'key': 'total_workorders'},
            {'name': _('Avg Duration'), 'value': f"{metrics.get('avg_workorder_duration', 0):.1f}h", 'icon': 'fa-clock-o', 'color': 'info', 'key': 'total_workorders'},
            {'name': _('Maint. Cost'), 'value': f"${metrics.get('maintenance_cost', 0):,.0f}", 'icon': 'fa-dollar', 'color': 'danger', 'key': 'maintenance_cost'},
            {'name': _('Maint. Efficiency'), 'value': f"{metrics.get('maintenance_efficiency', 0):.1f}%", 'icon': 'fa-line-chart', 
             'color': 'success' if metrics.get('maintenance_efficiency', 0) >= 85 else 'warning', 'key': 'maintenance_efficiency'},
            {'name': _('Labor Hours'), 'value': f"{metrics.get('total_labor_hours', 0):.1f}h", 'icon': 'fa-users', 'color': 'info', 'key': 'total_labor_cost'},
            {'name': _('Labor Cost'), 'value': f"${metrics.get('total_labor_cost', 0):,.0f}", 'icon': 'fa-usd', 'color': 'warning', 'key': 'total_labor_cost'},
            {'name': _('ROI'), 'value': f"{metrics.get('avg_roi', 0):.1f}%", 'icon': 'fa-trending-up', 
             'color': 'success' if metrics.get('avg_roi', 0) > 0 else 'danger', 'key': 'avg_roi'},
            {'name': _('Efficiency'), 'value': f"{metrics.get('efficiency_score', 0):.1f}%", 'icon': 'fa-tachometer', 
             'color': 'success' if metrics.get('efficiency_score', 0) >= 80 else 'warning', 'key': 'efficiency_score'},
        ]
        
        charts = self._build_asset_charts(date_from, date_to, facility_id)
        
        return {'kpis': kpis, 'charts': charts}
    
    def _build_asset_charts(self, date_from, date_to, facility_id=None):
        """Build chart data"""
        domain = []
        if facility_id:
            domain.append(('facility_id', '=', facility_id))
        
        assets = self.env['facilities.asset'].search(domain)
        
        # Asset Status
        status_counts = {}
        for asset in assets:
            state = asset.state or 'unknown'
            status_counts[state] = status_counts.get(state, 0) + 1
        
        status_labels = [dict(self.env['facilities.asset']._fields['state'].selection).get(s, s) 
                        for s in status_counts.keys()]
        
        # Asset Health
        health_ranges = {'Excellent': 0, 'Good': 0, 'Fair': 0, 'Poor': 0}
        for asset in assets:
            health = asset.asset_health_score or 0
            if health >= 90:
                health_ranges['Excellent'] += 1
            elif health >= 70:
                health_ranges['Good'] += 1
            elif health >= 50:
                health_ranges['Fair'] += 1
            else:
                health_ranges['Poor'] += 1
        
        return [
            {'type': 'doughnut', 'title': _('Asset Status'), 'labels': status_labels,
             'datasets': [{'data': list(status_counts.values()),
                         'backgroundColor': ['rgba(108, 117, 125, 0.7)', 'rgba(75, 192, 192, 0.7)', 
                                           'rgba(255, 206, 86, 0.7)', 'rgba(220, 53, 69, 0.7)']}]},
            {'type': 'pie', 'title': _('Asset Health'), 'labels': list(health_ranges.keys()),
             'datasets': [{'data': list(health_ranges.values()),
                         'backgroundColor': ['rgba(25, 135, 84, 0.7)', 'rgba(75, 192, 192, 0.7)', 
                                           'rgba(255, 193, 7, 0.7)', 'rgba(220, 53, 69, 0.7)']}]}
        ]