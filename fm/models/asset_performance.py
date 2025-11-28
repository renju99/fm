from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date
import logging
import json

_logger = logging.getLogger(__name__)


class AssetPerformance(models.Model):
    _name = 'facilities.asset.performance'
    _description = 'Asset Performance Tracking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, asset_id'
    _rec_name = 'display_name'

    # Basic Information
    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True,
                               ondelete='cascade', index=True, tracking=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today,
                       tracking=True, index=True)

    # Performance Metrics (in hours)
    expected_daily_runtime = fields.Float(string='Expected Daily Runtime (Hours)',
                                          default=8.0, required=True, tracking=True,
                                          help="Expected operating hours per day for this asset")
    actual_runtime = fields.Float(string='Actual Runtime (Hours)',
                                  required=True, tracking=True,
                                  help="Actual operating hours recorded for this day")
    downtime_hours = fields.Float(string='Downtime (Hours)',
                                  tracking=True, default=0.0,
                                  help="Hours the asset was down/not operational")

    # Computed Performance Indicators
    runtime_percentage = fields.Float(string='Runtime Efficiency (%)',
                                      compute='_compute_performance_metrics',
                                      store=True, aggregator='avg')
    availability_percentage = fields.Float(string='Availability (%)',
                                           compute='_compute_performance_metrics',
                                           store=True, aggregator='avg')
    utilization_percentage = fields.Float(string='Utilization (%)',
                                          compute='_compute_performance_metrics',
                                          store=True, aggregator='avg')

    # Additional Information
    notes = fields.Html(string='Performance Notes')
    operator_id = fields.Many2one('res.users', string='Operator/Responsible',
                                  default=lambda self: self.env.user, tracking=True)
    shift = fields.Selection([
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('night', 'Night'),
        ('full_day', 'Full Day')
    ], string='Shift', default='full_day', tracking=True)

    # Performance Status
    performance_status = fields.Selection([
        ('excellent', 'Excellent (≥95%)'),
        ('good', 'Good (80-94%)'),
        ('average', 'Average (60-79%)'),
        ('poor', 'Poor (<60%)')
    ], string='Performance Status', compute='_compute_performance_status',
        store=True, tracking=True)

    # Downtime Reasons
    downtime_reason_ids = fields.Many2many('asset.downtime.reason',
                                           string='Downtime Reasons')

    # Technical fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company,
                                 help="Company this performance record belongs to")

    _sql_constraints = [
        ('unique_asset_date_shift', 'unique(asset_id, date, shift)',
         'Performance record already exists for this asset, date, and shift!'),
        ('positive_expected_runtime', 'CHECK(expected_daily_runtime > 0)',
         'Expected daily runtime must be positive!'),
        ('positive_actual_runtime', 'CHECK(actual_runtime >= 0)',
         'Actual runtime cannot be negative!'),
        ('positive_downtime', 'CHECK(downtime_hours >= 0)',
         'Downtime cannot be negative!'),
    ]

    @api.depends('asset_id', 'date', 'shift')
    def _compute_display_name(self):
        for record in self:
            if record.asset_id and record.date:
                record.display_name = f"{record.asset_id.name} - {record.date} ({record.shift or 'N/A'})"
            else:
                record.display_name = "New Performance Record"

    @api.depends('expected_daily_runtime', 'actual_runtime', 'downtime_hours')
    def _compute_performance_metrics(self):
        for record in self:
            if record.expected_daily_runtime > 0:
                # Runtime Efficiency: Actual vs Expected
                record.runtime_percentage = (record.actual_runtime / record.expected_daily_runtime) * 100

                # Availability: (Expected - Downtime) / Expected
                available_time = max(0, record.expected_daily_runtime - record.downtime_hours)
                record.availability_percentage = (available_time / record.expected_daily_runtime) * 100

                # Utilization: Actual / Available Time
                if available_time > 0:
                    record.utilization_percentage = min(100, (record.actual_runtime / available_time) * 100)
                else:
                    record.utilization_percentage = 0.0
            else:
                record.runtime_percentage = 0.0
                record.availability_percentage = 0.0
                record.utilization_percentage = 0.0

    @api.depends('availability_percentage')
    def _compute_performance_status(self):
        for record in self:
            if record.availability_percentage >= 95:
                record.performance_status = 'excellent'
            elif record.availability_percentage >= 80:
                record.performance_status = 'good'
            elif record.availability_percentage >= 60:
                record.performance_status = 'average'
            else:
                record.performance_status = 'poor'

    @api.constrains('actual_runtime', 'downtime_hours', 'expected_daily_runtime')
    def _check_time_logic(self):
        for record in self:
            # Check if actual runtime + downtime doesn't exceed 24 hours unreasonably
            total_time = record.actual_runtime + record.downtime_hours
            if total_time > 24:
                raise ValidationError(_("Total runtime and downtime cannot exceed 24 hours per day."))

            # Warn if actual runtime exceeds expected significantly
            if record.actual_runtime > record.expected_daily_runtime * 1.5:
                _logger.warning(f"Asset {record.asset_id.name} actual runtime ({record.actual_runtime}h) "
                                f"significantly exceeds expected ({record.expected_daily_runtime}h) on {record.date}")

    def action_view_performance_analysis(self):
        """Open performance analysis for this asset"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Performance Analysis - {self.asset_id.name}',
            'res_model': 'facilities.asset.performance',
            'view_mode': 'graph,pivot,list',
            'domain': [('asset_id', '=', self.asset_id.id)],
            'context': {
                'search_default_group_by_date': 1,
                'search_default_last_30_days': 1,
            }
        }

    # Dashboard Methods
    def get_comprehensive_dashboard_data(self, period='current_year', category='all', date_from=None, date_to=None, facility_id=None):
        """Get comprehensive dashboard data for the frontend - now using unified calculation"""
        try:
            # Determine date range based on period
            today = fields.Date.today()
            if period == 'custom_range':
                # Use provided custom dates
                if date_from:
                    date_from = fields.Date.from_string(date_from) if isinstance(date_from, str) else date_from
                else:
                    date_from = today.replace(month=1, day=1)  # Default to start of year
                
                if date_to:
                    date_to = fields.Date.from_string(date_to) if isinstance(date_to, str) else date_to
                else:
                    date_to = today  # Default to today
                
                # Validate date range
                if date_from > date_to:
                    date_from, date_to = date_to, date_from  # Swap if needed
                    
            elif period == 'current_month':
                date_from = today.replace(day=1)
                date_to = today
            elif period == 'current_quarter':
                quarter_start = today.replace(day=1)
                while quarter_start.month % 3 != 1:
                    quarter_start = (quarter_start - timedelta(days=1)).replace(day=1)
                date_from = quarter_start
                date_to = today
            elif period == 'current_year':
                date_from = today.replace(month=1, day=1)
                date_to = today
            elif period == 'last_year':
                date_from = today.replace(year=today.year-1, month=1, day=1)
                date_to = today.replace(year=today.year-1, month=12, day=31)
            else:
                date_from = today.replace(month=1, day=1)
                date_to = today

            # Use the unified calculation method
            _logger.info(f"JavaScript Dashboard calling unified method - Period: {period}, Facility: {facility_id}")
            metrics = self._get_unified_dashboard_metrics(date_from, date_to, facility_id, None)
            
            # Add trends data
            try:
                trends = self._get_trends_data(date_from, date_to)
            except Exception as e:
                _logger.warning(f"Error getting trends data: {e}")
                trends = {
                    'roi_trend': [],
                    'utilization_trend': [],
                    'maintenance_cost_trend': []
                }
            
            # Add summary data
            try:
                summary = self._get_summary_data(date_from, date_to)
            except Exception as e:
                _logger.warning(f"Error getting summary data: {e}")
                summary = {
                    'total_assets': 0,
                    'total_maintenance_requests': 0,
                    'completed_maintenance': 0,
                    'last_updated': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            
            return {
                'period': period,
                'category': category,
                'date_range': {
                    'from': date_from.strftime('%Y-%m-%d'),
                    'to': date_to.strftime('%Y-%m-%d')
                },
                'metrics': metrics,
                'trends': trends,
                'summary': summary,
            }
            
        except Exception as e:
            _logger.error(f"Error getting dashboard data: {e}")
            return {'error': str(e)}

    def _get_maintenance_costs(self, date_from, date_to):
        """Get maintenance costs for the period"""
        try:
            maintenance_requests = self.env['facilities.workorder'].search([
                ('request_date', '>=', date_from),
                ('request_date', '<=', date_to)
            ])
            
            # Maintenance request model doesn't have a cost field, so estimate based on duration
            total_duration = sum(maintenance_requests.mapped('duration') or [0])
            # Estimate $50 per hour for maintenance
            return total_duration * 50
        except Exception as e:
            _logger.warning(f"Error calculating maintenance costs: {e}")
            return 0.0

    def _get_revenue_generated(self, performance_records):
        """Get revenue generated by assets (simplified)"""
        # This would typically come from sales or production data
        # For demo purposes, using a simplified calculation based on runtime
        total_runtime = sum(performance_records.mapped('actual_runtime'))
        return total_runtime * 100  # $100 per hour of operation

    def _calculate_utilization_rate(self, performance_records):
        """Calculate asset utilization rate"""
        if not performance_records:
            return 0.0
        
        total_expected = sum(performance_records.mapped('expected_daily_runtime'))
        total_actual = sum(performance_records.mapped('actual_runtime'))
        
        return (total_actual / total_expected * 100) if total_expected > 0 else 0

    def _get_operating_costs(self, date_from, date_to):
        """Get operating costs"""
        return self._get_maintenance_costs(date_from, date_to) * 1.5  # Maintenance + other operating costs

    def _calculate_efficiency_score(self, performance_records):
        """Calculate overall efficiency score"""
        if not performance_records:
            return 0.0
        
        utilization = self._calculate_utilization_rate(performance_records)
        avg_availability = sum(performance_records.mapped('availability_percentage')) / len(performance_records)
        
        return (utilization + avg_availability) / 2

    def _calculate_maintenance_efficiency(self, date_from, date_to):
        """Calculate maintenance efficiency"""
        try:
            maintenance_requests = self.env['facilities.workorder'].search([
                ('request_date', '>=', date_from),
                ('request_date', '<=', date_to)
            ])
            
            if not maintenance_requests:
                return 100.0
            
            completed = len(maintenance_requests.filtered(lambda r: r.stage_id.done))
            total = len(maintenance_requests)
            
            return (completed / total * 100) if total > 0 else 0
        except Exception as e:
            _logger.warning(f"Error calculating maintenance efficiency: {e}")
            return 85.0  # Default efficiency score

    def _calculate_asset_health_score(self, performance_records):
        """Calculate asset health score"""
        if not performance_records:
            return 0.0
        
        # Calculate based on average availability and performance status
        avg_availability = sum(performance_records.mapped('availability_percentage')) / len(performance_records)
        
        # Bonus for excellent performance records
        excellent_count = len(performance_records.filtered(lambda r: r.performance_status == 'excellent'))
        bonus = (excellent_count / len(performance_records)) * 10
        
        return min(100, avg_availability + bonus)

    def _get_trends_data(self, date_from, date_to):
        """Get trends data for charts"""
        # Get monthly data for trends
        trends_data = []
        current_date = date_from.replace(day=1)
        
        while current_date <= date_to:
            month_end = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            month_end = min(month_end, date_to)
            
            month_records = self.search([
                ('date', '>=', current_date),
                ('date', '<=', month_end)
            ])
            
            if month_records:
                avg_roi = self._calculate_monthly_roi(month_records)
                utilization = self._calculate_utilization_rate(month_records)
                maintenance_cost = self._get_maintenance_costs(current_date, month_end)
                
                trends_data.append({
                    'date': current_date.strftime('%Y-%m'),
                    'roi': avg_roi,
                    'utilization': utilization,
                    'maintenance_cost': maintenance_cost
                })
            
            current_date = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1)
        
        return {
            'roi_trend': [{'date': item['date'], 'value': item['roi']} for item in trends_data],
            'utilization_trend': [{'date': item['date'], 'value': item['utilization']} for item in trends_data],
            'maintenance_cost_trend': [{'date': item['date'], 'value': item['maintenance_cost']} for item in trends_data],
        }

    def _calculate_monthly_roi(self, month_records):
        """Calculate monthly ROI"""
        total_cost = sum(month_records.mapped('asset_id.purchase_cost') or [0])
        total_revenue = self._get_revenue_generated(month_records)
        
        return ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0

    def _get_summary_data(self, date_from, date_to):
        """Get summary data"""
        try:
            assets = self.env['facilities.asset'].search([])
            maintenance_requests = self.env['facilities.workorder'].search([
                ('request_date', '>=', date_from),
                ('request_date', '<=', date_to)
            ])
            
            return {
                'total_assets': len(assets),
                'total_maintenance_requests': len(maintenance_requests),
                'completed_maintenance': len(maintenance_requests.filtered(lambda r: r.stage_id.done)),
                'last_updated': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            _logger.warning(f"Error getting summary data: {e}")
            return {
                'total_assets': 0,
                'total_maintenance_requests': 0,
                'completed_maintenance': 0,
                'last_updated': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

    def export_dashboard_data(self, period='current_year', category='all'):
        """Export dashboard data for reports"""
        data = self.get_comprehensive_dashboard_data(period, category)
        if 'error' in data:
            return []
        
        # Convert to exportable format
        export_data = []
        metrics = data.get('metrics', {})
        
        for key, value in metrics.items():
            export_data.append({
                'metric': key.replace('_', ' ').title(),
                'value': value,
                'period': period,
                'category': category
            })
        
        return export_data

    @api.model
    def _get_unified_dashboard_metrics(self, date_from, date_to, facility_id=None, asset_ids=None):
        """Unified method to calculate dashboard metrics consistently across JS and form dashboards"""
        try:
            _logger.info(f"=== UNIFIED DASHBOARD CALCULATION ===")
            _logger.info(f"Date range: {date_from} to {date_to}")
            _logger.info(f"Facility ID: {facility_id}")
            _logger.info(f"Asset IDs provided: {len(asset_ids) if asset_ids else 0}")
            
            # Step 1: Determine which assets to include
            if asset_ids:
                # Form dashboard: use explicitly selected assets
                all_assets = self.env['facilities.asset'].browse(asset_ids)
                _logger.info(f"Using provided asset IDs: {len(all_assets)} assets")
            elif facility_id:
                # JavaScript dashboard with facility filter: get all assets from facility
                all_assets = self.env['facilities.asset'].search([('facility_id', '=', facility_id)])
                _logger.info(f"Found {len(all_assets)} assets in facility {facility_id}")
            else:
                # JavaScript dashboard without facility filter: get all assets
                all_assets = self.env['facilities.asset'].search([])
                _logger.info(f"Found {len(all_assets)} total assets in system")
            
            # Step 2: Get performance records for these assets in the date range
            perf_domain = [
                ('date', '>=', date_from),
                ('date', '<=', date_to)
            ]
            if all_assets:
                perf_domain.append(('asset_id', 'in', all_assets.ids))
            
            performance_records = self.search(perf_domain)
            _logger.info(f"Found {len(performance_records)} performance records")
            
            # Step 3: Calculate basic metrics
            total_assets = len(all_assets)
            total_value = sum(all_assets.mapped('purchase_cost') or [0])
            
            # Step 4: Calculate performance metrics
            if performance_records:
                total_expected = sum(performance_records.mapped('expected_daily_runtime'))
                total_actual = sum(performance_records.mapped('actual_runtime'))
                utilization_rate = (total_actual / total_expected * 100) if total_expected > 0 else 0
                downtime_hours = sum(performance_records.mapped('downtime_hours'))
                uptime_percentage = 100 - (downtime_hours / total_expected * 100) if total_expected > 0 else 100
                
                # Efficiency and health scores
                avg_availability = sum(performance_records.mapped('availability_percentage')) / len(performance_records)
                efficiency_score = (utilization_rate + avg_availability) / 2
                asset_health_score = avg_availability
            else:
                utilization_rate = 0
                downtime_hours = 0
                uptime_percentage = 100
                efficiency_score = 0
                asset_health_score = 0
            
            # Step 5: Calculate work order metrics
            workorder_metrics = self._calculate_workorder_metrics_unified(date_from, date_to, facility_id, all_assets)
            
            # Step 6: Calculate financial metrics (simplified)
            revenue_generated = sum(performance_records.mapped('actual_runtime')) * 100 if performance_records else 0
            operating_cost = total_value * 0.1  # 10% of asset value as operating cost
            maintenance_cost = workorder_metrics.get('total_labor_cost', 0)
            net_profit = revenue_generated - operating_cost - maintenance_cost
            profit_margin = (net_profit / revenue_generated * 100) if revenue_generated > 0 else 0
            avg_roi = (net_profit / total_value * 100) if total_value > 0 else 0
            
            metrics = {
                'total_assets': total_assets,
                'total_value': total_value,
                'avg_roi': avg_roi,
                'utilization_rate': utilization_rate,
                'downtime_hours': downtime_hours,
                'efficiency_score': efficiency_score,
                'revenue_generated': revenue_generated,
                'operating_cost': operating_cost,
                'net_profit': net_profit,
                'profit_margin': profit_margin,
                'uptime_percentage': uptime_percentage,
                'maintenance_efficiency': 85.0,  # Default
                'asset_health_score': asset_health_score,
                'maintenance_cost': maintenance_cost,
                # Work order metrics
                **workorder_metrics
            }
            
            _logger.info(f"CALCULATED METRICS: Assets={total_assets}, Value=${total_value}, ROI={avg_roi:.1f}%")
            return metrics
            
        except Exception as e:
            _logger.error(f"Error in unified dashboard calculation: {str(e)}")
            return self._get_default_metrics()
    
    def _get_default_metrics(self):
        """Return default metrics when calculation fails"""
        return {
            'total_assets': 0,
            'total_value': 0,
            'avg_roi': 0,
            'utilization_rate': 0,
            'downtime_hours': 0,
            'efficiency_score': 0,
            'revenue_generated': 0,
            'operating_cost': 0,
            'net_profit': 0,
            'profit_margin': 0,
            'uptime_percentage': 100,
            'maintenance_efficiency': 0,
            'asset_health_score': 0,
            'maintenance_cost': 0,
            'total_workorders': 0,
            'completed_workorders': 0,
            'pending_workorders': 0,
            'overdue_workorders': 0,
            'workorder_completion_rate': 0,
            'avg_workorder_duration': 0,
            'total_labor_hours': 0,
            'total_labor_cost': 0,
        }

    def _calculate_workorder_metrics_unified(self, date_from, date_to, facility_id=None, assets=None):
        """Unified work order calculation method"""
        try:
            # Build domain for work orders
            workorder_domain = [
                '|',
                ('date_scheduled', '>=', date_from),
                ('date_scheduled', '<=', date_to),
                '|',
                ('date_scheduled', '=', False),
                ('create_date', '>=', date_from),
            ]
            
            # Add asset/facility filter
            if assets and len(assets) > 0:
                if facility_id:
                    workorder_domain.extend([
                        '|',
                        ('asset_id', 'in', assets.ids),
                        ('work_location_facility_id', '=', facility_id),
                    ])
                else:
                    workorder_domain.append(('asset_id', 'in', assets.ids))
            elif facility_id:
                workorder_domain.append(('work_location_facility_id', '=', facility_id))
            
            # Search for work orders
            workorders = self.env['facilities.workorder'].search(workorder_domain)
            
            total_workorders = len(workorders)
            completed_workorders = len(workorders.filtered(lambda w: w.state == 'done'))
            pending_workorders = len(workorders.filtered(lambda w: w.state in ['draft', 'open', 'in_progress']))
            
            # Calculate overdue work orders
            today = fields.Date.context_today(self)
            overdue_workorders = len(workorders.filtered(
                lambda w: w.date_scheduled and w.date_scheduled < today and w.state not in ['done', 'cancelled']
            ))
            
            completion_rate = (completed_workorders / total_workorders * 100) if total_workorders > 0 else 0
            
            # Calculate labor metrics
            assignments = self.env['facilities.workorder.assignment'].search([
                ('workorder_id', 'in', workorders.ids)
            ])
            
            total_labor_hours = sum(assignments.mapped('work_hours'))
            total_labor_cost = sum(assignments.mapped('labor_cost'))
            
            # Calculate average duration
            completed_with_duration = workorders.filtered(lambda w: w.state == 'done' and w.date_start and w.date_done)
            if completed_with_duration:
                total_duration = sum([(wo.date_done - wo.date_start).total_seconds() / 3600 for wo in completed_with_duration])
                avg_duration = total_duration / len(completed_with_duration)
            else:
                avg_duration = 0
            
            _logger.info(f"WORK ORDER METRICS: Total={total_workorders}, Completed={completed_workorders}, Rate={completion_rate:.1f}%")
            
            return {
                'total_workorders': total_workorders,
                'completed_workorders': completed_workorders,
                'pending_workorders': pending_workorders,
                'overdue_workorders': overdue_workorders,
                'workorder_completion_rate': completion_rate,
                'avg_workorder_duration': avg_duration,
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
                'workorder_completion_rate': 0,
                'avg_workorder_duration': 0,
                'total_labor_hours': 0,
                'total_labor_cost': 0,
            }

    def _calculate_workorder_metrics_for_dashboard(self, date_from, date_to, facility_id=None, assets=None):
        """Calculate work order metrics for the JavaScript dashboard"""
        try:
            # Build domain for work orders
            workorder_domain = [
                '|',
                ('date_scheduled', '>=', date_from),
                ('date_scheduled', '<=', date_to),
                '|',
                ('date_scheduled', '=', False),
                ('create_date', '>=', date_from),
            ]
            
            # Add asset/facility filter if provided
            if assets:
                # Use the provided assets list
                workorder_domain.extend([
                    '|',
                    ('asset_id', 'in', assets.ids),
                    ('work_location_facility_id', '=', facility_id) if facility_id else ('id', '!=', False),
                ])
            elif facility_id:
                # Fallback to facility-only filter
                workorder_domain.append(('work_location_facility_id', '=', facility_id))
            
            # Search for work orders
            workorders = self.env['facilities.workorder'].search(workorder_domain)
            
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
                'workorder_completion_rate': completion_rate,
                'avg_workorder_duration': avg_duration,
                'total_labor_hours': total_labor_hours,
                'total_labor_cost': total_labor_cost,
            }
            
        except Exception as e:
            _logger.error(f"Error calculating work order metrics for dashboard: {str(e)}")
            return {
                'total_workorders': 0,
                'completed_workorders': 0,
                'pending_workorders': 0,
                'overdue_workorders': 0,
                'workorder_completion_rate': 0,
                'avg_workorder_duration': 0,
                'total_labor_hours': 0,
                'total_labor_cost': 0,
            }


    def action_drilldown_assets(self, date_from=None, date_to=None, facility_id=None, asset_ids=None):
        """Drilldown action to show assets list"""
        _logger.info(f"Assets Drilldown - facility_id: {facility_id}, asset_ids: {asset_ids}")
        
        domain = []
        if facility_id:
            domain.append(('facility_id', '=', facility_id))
        if asset_ids:
            domain.append(('id', 'in', asset_ids))
        
        # Count assets
        asset_count = self.env['facilities.asset'].search_count(domain)
        _logger.info(f"Drilldown will show {asset_count} assets")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Assets ({asset_count} records)',
            'res_model': 'facilities.asset',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'target': 'current',
            'context': {}
        }
    
    def action_drilldown_work_orders(self, date_from=None, date_to=None, facility_id=None, asset_ids=None):
        """Drilldown action to show work orders"""
        _logger.info(f"Work Orders Drilldown - date_from: {date_from}, date_to: {date_to}, facility_id: {facility_id}")
        
        domain = []
        
        # Add date filters if provided
        if date_from and date_to:
            try:
                if isinstance(date_from, str):
                    date_from = fields.Date.from_string(date_from)
                if isinstance(date_to, str):
                    date_to = fields.Date.from_string(date_to)
                
                domain = [
                    '|', '|',
                    '&', ('start_date', '>=', date_from), ('start_date', '<=', date_to),
                    '&', ('actual_start_date', '>=', date_from), ('actual_start_date', '<=', date_to),
                    '&', ('create_date', '>=', fields.Datetime.to_datetime(date_from)),
                         ('create_date', '<=', fields.Datetime.to_datetime(date_to))
                ]
            except Exception as e:
                _logger.warning(f"Error with dates: {e}")
                domain = []
        
        if facility_id:
            if domain:
                domain = ['&'] + domain + [('facility_id', '=', facility_id)]
            else:
                domain.append(('facility_id', '=', facility_id))
        
        if asset_ids:
            if domain:
                domain = ['&'] + domain + [('asset_id', 'in', asset_ids)]
            else:
                domain.append(('asset_id', 'in', asset_ids))
        
        wo_count = self.env['facilities.workorder'].search_count(domain)
        _logger.info(f"Drilldown will show {wo_count} work orders")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Work Orders ({wo_count} records)',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'target': 'current',
            'context': {}
        }
    
    def action_drilldown_maintenance_costs(self, date_from=None, date_to=None, facility_id=None, asset_ids=None):
        """Drilldown action to show maintenance costs breakdown"""
        _logger.info(f"Maintenance Costs Drilldown - date_from: {date_from}, date_to: {date_to}")
        
        domain = []
        
        if date_from and date_to:
            try:
                if isinstance(date_from, str):
                    date_from = fields.Date.from_string(date_from)
                if isinstance(date_to, str):
                    date_to = fields.Date.from_string(date_to)
                
                domain = [
                    '|', '|',
                    '&', ('start_date', '>=', date_from), ('start_date', '<=', date_to),
                    '&', ('actual_start_date', '>=', date_from), ('actual_start_date', '<=', date_to),
                    '&', ('create_date', '>=', fields.Datetime.to_datetime(date_from)),
                         ('create_date', '<=', fields.Datetime.to_datetime(date_to))
                ]
            except Exception as e:
                _logger.warning(f"Error with dates: {e}")
                domain = []
        
        if facility_id:
            if domain:
                domain = ['&'] + domain + [('facility_id', '=', facility_id)]
            else:
                domain.append(('facility_id', '=', facility_id))
        
        if asset_ids:
            if domain:
                domain = ['&'] + domain + [('asset_id', 'in', asset_ids)]
            else:
                domain.append(('asset_id', 'in', asset_ids))
        
        wo_count = self.env['facilities.workorder'].search_count(domain)
        _logger.info(f"Drilldown will show {wo_count} work orders for cost analysis")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Maintenance Costs ({wo_count} records)',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,pivot,graph,form',
            'views': [(False, 'list'), (False, 'pivot'), (False, 'graph'), (False, 'form')],
            'domain': domain,
            'target': 'current',
            'context': {
                'pivot_measures': ['total_cost', 'labor_cost', 'parts_cost'],
            }
        }
    
    def action_drilldown_asset_performance(self, date_from=None, date_to=None, facility_id=None, asset_ids=None):
        """Drilldown action to show asset performance records"""
        _logger.info(f"Asset Performance Drilldown - date_from: {date_from}, date_to: {date_to}")
        
        domain = []
        
        if date_from and date_to:
            try:
                if isinstance(date_from, str):
                    date_from = fields.Date.from_string(date_from)
                if isinstance(date_to, str):
                    date_to = fields.Date.from_string(date_to)
                domain = [('date', '>=', date_from), ('date', '<=', date_to)]
            except Exception as e:
                _logger.warning(f"Error with dates: {e}")
                domain = []
        
        if asset_ids:
            if domain:
                domain.append(('asset_id', 'in', asset_ids))
            else:
                domain = [('asset_id', 'in', asset_ids)]
        elif facility_id:
            assets = self.env['facilities.asset'].search([('facility_id', '=', facility_id)])
            if assets:
                if domain:
                    domain.append(('asset_id', 'in', assets.ids))
                else:
                    domain = [('asset_id', 'in', assets.ids)]
        
        perf_count = self.env['facilities.asset.performance'].search_count(domain)
        _logger.info(f"Drilldown will show {perf_count} performance records")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Asset Performance ({perf_count} records)',
            'res_model': 'facilities.asset.performance',
            'view_mode': 'list,graph,pivot,form',
            'views': [(False, 'list'), (False, 'graph'), (False, 'pivot'), (False, 'form')],
            'domain': domain,
            'target': 'current',
            'context': {}
        }
    
    def action_drilldown_downtime_analysis(self, date_from=None, date_to=None, facility_id=None, asset_ids=None):
        """Drilldown action to show downtime analysis"""
        _logger.info(f"Downtime Analysis Drilldown - date_from: {date_from}, date_to: {date_to}")
        
        domain = []
        
        if date_from and date_to:
            try:
                if isinstance(date_from, str):
                    date_from = fields.Date.from_string(date_from)
                if isinstance(date_to, str):
                    date_to = fields.Date.from_string(date_to)
                domain = [('date', '>=', date_from), ('date', '<=', date_to)]
            except Exception as e:
                _logger.warning(f"Error with dates: {e}")
                domain = []
        
        if asset_ids:
            if domain:
                domain.append(('asset_id', 'in', asset_ids))
            else:
                domain = [('asset_id', 'in', asset_ids)]
        elif facility_id:
            assets = self.env['facilities.asset'].search([('facility_id', '=', facility_id)])
            if assets:
                if domain:
                    domain.append(('asset_id', 'in', assets.ids))
                else:
                    domain = [('asset_id', 'in', assets.ids)]
        
        # Filter only records with downtime
        if domain:
            domain.append(('downtime_hours', '>', 0))
        else:
            domain = [('downtime_hours', '>', 0)]
        
        dt_count = self.env['facilities.asset.performance'].search_count(domain)
        _logger.info(f"Drilldown will show {dt_count} downtime records")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Downtime Analysis ({dt_count} records)',
            'res_model': 'facilities.asset.performance',
            'view_mode': 'list,pivot,graph,form',
            'views': [(False, 'list'), (False, 'pivot'), (False, 'graph'), (False, 'form')],
            'domain': domain,
            'target': 'current',
            'context': {}
        }
    
    def action_drilldown_by_facility(self, date_from=None, date_to=None, facility_id=None):
        """Drilldown to show all metrics for a specific facility"""
        _logger.info(f"Facility Drilldown - facility_id: {facility_id}, date_from: {date_from}")
        
        domain = []
        
        if facility_id:
            assets = self.env['facilities.asset'].search([('facility_id', '=', facility_id)])
            if assets:
                domain = [('asset_id', 'in', assets.ids)]
        
        if date_from and date_to and domain:
            try:
                if isinstance(date_from, str):
                    date_from = fields.Date.from_string(date_from)
                if isinstance(date_to, str):
                    date_to = fields.Date.from_string(date_to)
                domain += [('date', '>=', date_from), ('date', '<=', date_to)]
            except Exception as e:
                _logger.warning(f"Error with dates: {e}")
        
        perf_count = self.env['facilities.asset.performance'].search_count(domain)
        _logger.info(f"Drilldown will show {perf_count} performance records")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Performance Details ({perf_count} records)',
            'res_model': 'facilities.asset.performance',
            'view_mode': 'list,graph,pivot',
            'views': [(False, 'list'), (False, 'graph'), (False, 'pivot')],
            'domain': domain,
            'target': 'current',
            'context': {}
        }
    
    def action_drilldown_by_asset_category(self, date_from=None, date_to=None, category=None, facility_id=None):
        """Drilldown to show performance by asset category"""
        _logger.info(f"Category Drilldown - category: {category}, facility_id: {facility_id}")
        
        asset_domain = []
        if category:
            asset_domain.append(('category', '=', category))
        if facility_id:
            asset_domain.append(('facility_id', '=', facility_id))
        
        assets = self.env['facilities.asset'].search(asset_domain)
        
        domain = []
        if assets:
            domain = [('asset_id', 'in', assets.ids)]
        
        if date_from and date_to and domain:
            try:
                if isinstance(date_from, str):
                    date_from = fields.Date.from_string(date_from)
                if isinstance(date_to, str):
                    date_to = fields.Date.from_string(date_to)
                domain += [('date', '>=', date_from), ('date', '<=', date_to)]
            except Exception as e:
                _logger.warning(f"Error with dates: {e}")
        
        perf_count = self.env['facilities.asset.performance'].search_count(domain)
        _logger.info(f"Drilldown will show {perf_count} performance records")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'{category.title() if category else "Asset"} Performance ({perf_count} records)',
            'res_model': 'facilities.asset.performance',
            'view_mode': 'list,graph,pivot',
            'views': [(False, 'list'), (False, 'graph'), (False, 'pivot')],
            'domain': domain,
            'target': 'current',
            'context': {}
        }
    
    def action_drilldown_maintenance_efficiency(self, date_from=None, date_to=None, facility_id=None, asset_ids=None):
        """Drilldown to show work orders for maintenance efficiency analysis"""
        _logger.info(f"Maintenance Efficiency Drilldown - date_from: {date_from}, date_to: {date_to}, facility_id: {facility_id}")
        
        # Start with empty domain to show all work orders
        domain = []
        
        # Only add date filters if dates are provided and valid
        if date_from and date_to:
            try:
                # Convert string dates to date objects if needed
                if isinstance(date_from, str):
                    date_from = fields.Date.from_string(date_from)
                if isinstance(date_to, str):
                    date_to = fields.Date.from_string(date_to)
                
                # Add flexible date filtering
                domain = [
                    '|', '|',
                    '&', ('start_date', '>=', date_from), ('start_date', '<=', date_to),
                    '&', ('actual_start_date', '>=', date_from), ('actual_start_date', '<=', date_to),
                    '&', ('create_date', '>=', fields.Datetime.to_datetime(date_from)),
                         ('create_date', '<=', fields.Datetime.to_datetime(date_to))
                ]
                _logger.info(f"Added date filter: {date_from} to {date_to}")
            except Exception as e:
                _logger.warning(f"Error processing dates, showing all work orders: {e}")
                domain = []
        
        # Add facility filter if specified
        if facility_id:
            if domain:
                domain = ['&'] + domain + [('facility_id', '=', facility_id)]
            else:
                domain.append(('facility_id', '=', facility_id))
            _logger.info(f"Added facility filter: {facility_id}")
        
        # Add asset filter if specified  
        if asset_ids:
            if domain:
                domain = ['&'] + domain + [('asset_id', 'in', asset_ids)]
            else:
                domain.append(('asset_id', 'in', asset_ids))
            _logger.info(f"Added asset filter: {asset_ids}")
        
        # Count work orders for debugging
        workorder_count = self.env['facilities.workorder'].search_count(domain)
        _logger.info(f"Drilldown will show {workorder_count} work orders with domain: {domain}")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Work Orders - Maintenance Efficiency ({workorder_count} records)',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'target': 'current',
            'context': {
                'search_default_group_by_state': 1,
            }
        }


class AssetDowntimeReason(models.Model):
    _name = 'asset.downtime.reason'
    _description = 'Asset Downtime Reason'
    _order = 'sequence, name'

    name = fields.Char(string='Reason', required=True, translate=True)
    code = fields.Char(string='Code', size=10)
    description = fields.Html(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    category = fields.Selection([
        ('mechanical', 'Mechanical Failure'),
        ('electrical', 'Electrical Issue'),
        ('maintenance', 'Scheduled Maintenance'),
        ('material', 'Material/Supply Issue'),
        ('operator', 'Operator Issue'),
        ('environmental', 'Environmental'),
        ('other', 'Other')
    ], string='Category', required=True, default='other')
    active = fields.Boolean(string='Active', default=True)
    color = fields.Integer(string='Color', default=0)

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Downtime reason code must be unique!')
    ]