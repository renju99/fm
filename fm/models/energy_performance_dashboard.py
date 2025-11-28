# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
import logging
from datetime import datetime, timedelta, date

_logger = logging.getLogger(__name__)


class EnergyPerformanceDashboard(models.Model):
    _name = 'facilities.energy.performance.dashboard'
    _description = 'Energy Performance Dashboard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # Basic Information
    name = fields.Char(string='Energy Analysis Name', required=True, tracking=True)
    date_from = fields.Date(string='Date From', required=True, default=fields.Date.context_today, tracking=True)
    date_to = fields.Date(string='Date To', required=True, default=fields.Date.context_today, tracking=True)
    
    # Facility Selection
    facility_id = fields.Many2one('facilities.facility', string='Filter by Facility', tracking=True,
                                 help='Filter energy data by specific facility. Leave empty to include all facilities.')
    meter_ids = fields.Many2many('facilities.utility.meter', 'energy_dashboard_meter_rel', 
                                 'dashboard_id', 'meter_id', string='Utility Meters', tracking=True)
    
    # State Management
    state = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error')
    ], string='State', default='draft', tracking=True, required=True)
    
    # Energy Performance Metrics
    total_meters = fields.Integer(string='Total Meters', compute='_compute_metrics', store=True)
    total_consumption = fields.Float(string='Total Consumption', compute='_compute_metrics', store=True)
    total_energy_cost = fields.Float(string='Total Energy Cost', compute='_compute_metrics', store=True)
    avg_efficiency_score = fields.Float(string='Average Efficiency Score', compute='_compute_metrics', store=True)
    
    # Consumption Breakdown by Type
    electricity_consumption = fields.Float(string='Electricity Consumption (kWh)', compute='_compute_metrics', store=True)
    water_consumption = fields.Float(string='Water Consumption (m³)', compute='_compute_metrics', store=True)
    gas_consumption = fields.Float(string='Gas Consumption (m³)', compute='_compute_metrics', store=True)
    steam_consumption = fields.Float(string='Steam Consumption (Ton-hour)', compute='_compute_metrics', store=True)
    
    # Cost Breakdown by Type
    electricity_cost = fields.Float(string='Electricity Cost', compute='_compute_metrics', store=True)
    water_cost = fields.Float(string='Water Cost', compute='_compute_metrics', store=True)
    gas_cost = fields.Float(string='Gas Cost', compute='_compute_metrics', store=True)
    steam_cost = fields.Float(string='Steam Cost', compute='_compute_metrics', store=True)
    
    # Efficiency Metrics
    energy_efficiency_score = fields.Float(string='Energy Efficiency Score', compute='_compute_metrics', store=True)
    water_efficiency_score = fields.Float(string='Water Efficiency Score', compute='_compute_metrics', store=True)
    sustainability_score = fields.Float(string='Sustainability Score', compute='_compute_metrics', store=True)
    co2_emissions = fields.Float(string='CO₂ Emissions (kg)', compute='_compute_metrics', store=True)
    
    # Performance Indicators
    peak_demand = fields.Float(string='Peak Demand (kW)', compute='_compute_metrics', store=True)
    average_demand = fields.Float(string='Average Demand (kW)', compute='_compute_metrics', store=True)
    load_factor = fields.Float(string='Load Factor (%)', compute='_compute_metrics', store=True)
    utilization_rate = fields.Float(string='Utilization Rate (%)', compute='_compute_metrics', store=True)
    
    # Cost Analysis
    cost_per_sqm = fields.Float(string='Cost per m²', compute='_compute_metrics', store=True)
    cost_per_occupant = fields.Float(string='Cost per Occupant', compute='_compute_metrics', store=True)
    cost_per_hour = fields.Float(string='Cost per Hour', compute='_compute_metrics', store=True)
    
    # Trend Analysis
    consumption_trend = fields.Selection([
        ('increasing', 'Increasing'),
        ('decreasing', 'Decreasing'),
        ('stable', 'Stable'),
        ('fluctuating', 'Fluctuating')
    ], string='Consumption Trend', compute='_compute_trend_analysis', store=True)
    
    trend_percentage = fields.Float(string='Trend Percentage (%)', compute='_compute_trend_analysis', store=True)
    cost_trend = fields.Selection([
        ('increasing', 'Increasing'),
        ('decreasing', 'Decreasing'),
        ('stable', 'Stable'),
        ('fluctuating', 'Fluctuating')
    ], string='Cost Trend', compute='_compute_trend_analysis', store=True)
    
    # Alerts and Anomalies
    total_alerts = fields.Integer(string='Total Alerts', compute='_compute_alerts', store=True)
    high_consumption_alerts = fields.Integer(string='High Consumption Alerts', compute='_compute_alerts', store=True)
    cost_anomaly_alerts = fields.Integer(string='Cost Anomaly Alerts', compute='_compute_alerts', store=True)
    maintenance_alerts = fields.Integer(string='Maintenance Alerts', compute='_compute_alerts', store=True)
    
    # Benchmark Analysis
    industry_benchmark_cost = fields.Float(string='Industry Benchmark Cost per m²', tracking=True,
                                         help='Industry benchmark for cost per square meter')
    benchmark_performance = fields.Selection([
        ('excellent', 'Excellent (Top 10%)'),
        ('good', 'Good (Top 25%)'),
        ('average', 'Average (Middle 50%)'),
        ('below_average', 'Below Average (Bottom 25%)'),
        ('poor', 'Poor (Bottom 10%)')
    ], string='Benchmark Performance', compute='_compute_benchmark_analysis', store=True)
    
    # Results Storage
    performance_data = fields.Text(string='Performance Data (JSON)', readonly=True)
    
    # Mail fields for chatter
    message_ids = fields.One2many('mail.message', 'res_id', string='Messages')

    @api.depends('date_from', 'date_to', 'facility_id', 'meter_ids')
    def _compute_metrics(self):
        """Compute all energy performance metrics"""
        for dashboard in self:
            if not dashboard.date_from or not dashboard.date_to:
                continue
                
            # Get consumption readings for the period
            domain = [
                ('reading_date', '>=', dashboard.date_from),
                ('reading_date', '<=', dashboard.date_to),
                ('is_validated', '=', True)
            ]
            
            if dashboard.facility_id:
                domain.append(('meter_id.facility_id', '=', dashboard.facility_id.id))
            elif dashboard.meter_ids:
                domain.append(('meter_id', 'in', dashboard.meter_ids.ids))
            
            readings = self.env['facilities.energy.consumption'].search(domain)
            
            if not readings:
                # Set default values if no readings found
                dashboard.total_meters = 0
                dashboard.total_consumption = 0.0
                dashboard.total_energy_cost = 0.0
                dashboard.avg_efficiency_score = 0.0
                dashboard.electricity_consumption = 0.0
                dashboard.water_consumption = 0.0
                dashboard.gas_consumption = 0.0
                dashboard.steam_consumption = 0.0
                dashboard.electricity_cost = 0.0
                dashboard.water_cost = 0.0
                dashboard.gas_cost = 0.0
                dashboard.steam_cost = 0.0
                dashboard.energy_efficiency_score = 0.0
                dashboard.water_efficiency_score = 0.0
                dashboard.sustainability_score = 0.0
                dashboard.co2_emissions = 0.0
                dashboard.peak_demand = 0.0
                dashboard.average_demand = 0.0
                dashboard.load_factor = 0.0
                dashboard.utilization_rate = 0.0
                dashboard.cost_per_sqm = 0.0
                dashboard.cost_per_occupant = 0.0
                dashboard.cost_per_hour = 0.0
                continue
            
            # Calculate totals
            dashboard.total_consumption = sum(readings.mapped('consumption'))
            dashboard.total_energy_cost = sum(readings.mapped('total_cost'))
            dashboard.total_meters = len(readings.mapped('meter_id'))
            
            # Calculate by meter type
            electricity_readings = readings.filtered(lambda r: r.meter_id.meter_type == 'electricity')
            water_readings = readings.filtered(lambda r: r.meter_id.meter_type == 'water')
            gas_readings = readings.filtered(lambda r: r.meter_id.meter_type == 'gas')
            steam_readings = readings.filtered(lambda r: r.meter_id.meter_type == 'steam')
            
            dashboard.electricity_consumption = sum(electricity_readings.mapped('consumption'))
            dashboard.water_consumption = sum(water_readings.mapped('consumption'))
            dashboard.gas_consumption = sum(gas_readings.mapped('consumption'))
            dashboard.steam_consumption = sum(steam_readings.mapped('consumption'))
            
            dashboard.electricity_cost = sum(electricity_readings.mapped('total_cost'))
            dashboard.water_cost = sum(water_readings.mapped('total_cost'))
            dashboard.gas_cost = sum(gas_readings.mapped('total_cost'))
            dashboard.steam_cost = sum(steam_readings.mapped('total_cost'))
            
            # Calculate efficiency scores
            dashboard.energy_efficiency_score = self._calculate_energy_efficiency_score(readings, dashboard)
            dashboard.water_efficiency_score = self._calculate_water_efficiency_score(readings, dashboard)
            dashboard.sustainability_score = (dashboard.energy_efficiency_score + dashboard.water_efficiency_score) / 2
            
            # Calculate CO2 emissions
            dashboard.co2_emissions = self._calculate_co2_emissions(readings)
            
            # Calculate performance indicators
            dashboard.peak_demand = self._calculate_peak_demand(electricity_readings)
            dashboard.average_demand = self._calculate_average_demand(electricity_readings)
            dashboard.load_factor = self._calculate_load_factor(dashboard.peak_demand, dashboard.average_demand)
            dashboard.utilization_rate = self._calculate_utilization_rate(readings)
            
            # Calculate cost analysis
            dashboard.cost_per_sqm = self._calculate_cost_per_sqm(dashboard.total_energy_cost, dashboard)
            dashboard.cost_per_occupant = self._calculate_cost_per_occupant(dashboard.total_energy_cost, dashboard)
            dashboard.cost_per_hour = self._calculate_cost_per_hour(dashboard.total_energy_cost, dashboard)
            
            # Calculate average efficiency score
            dashboard.avg_efficiency_score = dashboard.sustainability_score

    @api.depends('date_from', 'date_to', 'facility_id', 'meter_ids')
    def _compute_trend_analysis(self):
        """Compute consumption and cost trends"""
        for dashboard in self:
            if not dashboard.date_from or not dashboard.date_to:
                continue
                
            # Calculate previous period
            period_days = (dashboard.date_to - dashboard.date_from).days
            prev_end_date = dashboard.date_from - timedelta(days=1)
            prev_start_date = prev_end_date - timedelta(days=period_days)
            
            # Get current and previous period readings
            current_domain = [
                ('reading_date', '>=', dashboard.date_from),
                ('reading_date', '<=', dashboard.date_to),
                ('is_validated', '=', True)
            ]
            
            prev_domain = [
                ('reading_date', '>=', prev_start_date),
                ('reading_date', '<=', prev_end_date),
                ('is_validated', '=', True)
            ]
            
            if dashboard.facility_id:
                current_domain.append(('meter_id.facility_id', '=', dashboard.facility_id.id))
                prev_domain.append(('meter_id.facility_id', '=', dashboard.facility_id.id))
            elif dashboard.meter_ids:
                current_domain.append(('meter_id', 'in', dashboard.meter_ids.ids))
                prev_domain.append(('meter_id', 'in', dashboard.meter_ids.ids))
            
            current_readings = self.env['facilities.energy.consumption'].search(current_domain)
            prev_readings = self.env['facilities.energy.consumption'].search(prev_domain)
            
            current_consumption = sum(current_readings.mapped('consumption'))
            prev_consumption = sum(prev_readings.mapped('consumption'))
            current_cost = sum(current_readings.mapped('total_cost'))
            prev_cost = sum(prev_readings.mapped('total_cost'))
            
            # Calculate consumption trend
            if prev_consumption > 0:
                consumption_change = ((current_consumption - prev_consumption) / prev_consumption) * 100
                dashboard.trend_percentage = consumption_change
                
                if consumption_change > 10:
                    dashboard.consumption_trend = 'increasing'
                elif consumption_change < -10:
                    dashboard.consumption_trend = 'decreasing'
                elif abs(consumption_change) <= 5:
                    dashboard.consumption_trend = 'stable'
                else:
                    dashboard.consumption_trend = 'fluctuating'
            else:
                dashboard.trend_percentage = 0
                dashboard.consumption_trend = 'stable'
            
            # Calculate cost trend
            if prev_cost > 0:
                cost_change = ((current_cost - prev_cost) / prev_cost) * 100
                if cost_change > 10:
                    dashboard.cost_trend = 'increasing'
                elif cost_change < -10:
                    dashboard.cost_trend = 'decreasing'
                elif abs(cost_change) <= 5:
                    dashboard.cost_trend = 'stable'
                else:
                    dashboard.cost_trend = 'fluctuating'
            else:
                dashboard.cost_trend = 'stable'

    @api.depends('facility_id', 'meter_ids')
    def _compute_alerts(self):
        """Compute alert counts"""
        for dashboard in self:
            # Count anomaly alerts
            alert_domain = [('is_anomaly', '=', True)]
            
            if dashboard.facility_id:
                alert_domain.append(('meter_id.facility_id', '=', dashboard.facility_id.id))
            elif dashboard.meter_ids:
                alert_domain.append(('meter_id', 'in', dashboard.meter_ids.ids))
            
            readings = self.env['facilities.energy.consumption'].search(alert_domain)
            
            dashboard.total_alerts = len(readings)
            dashboard.high_consumption_alerts = len(readings.filtered(
                lambda r: r.anomaly_severity in ['high', 'critical']
            ))
            dashboard.cost_anomaly_alerts = len(readings.filtered(
                lambda r: r.variance_percentage > 50
            ))
            
            # Count maintenance alerts
            maintenance_domain = [('state', 'in', ['maintenance', 'calibration', 'faulty'])]
            if dashboard.facility_id:
                maintenance_domain.append(('facility_id', '=', dashboard.facility_id.id))
            elif dashboard.meter_ids:
                maintenance_domain.append(('id', 'in', dashboard.meter_ids.ids))
            
            maintenance_meters = self.env['facilities.utility.meter'].search(maintenance_domain)
            dashboard.maintenance_alerts = len(maintenance_meters)

    @api.depends('cost_per_sqm', 'industry_benchmark_cost')
    def _compute_benchmark_analysis(self):
        """Compute benchmark performance"""
        for dashboard in self:
            if dashboard.industry_benchmark_cost > 0 and dashboard.cost_per_sqm > 0:
                ratio = dashboard.cost_per_sqm / dashboard.industry_benchmark_cost
                
                if ratio <= 0.9:
                    dashboard.benchmark_performance = 'excellent'
                elif ratio <= 1.1:
                    dashboard.benchmark_performance = 'good'
                elif ratio <= 1.3:
                    dashboard.benchmark_performance = 'average'
                elif ratio <= 1.5:
                    dashboard.benchmark_performance = 'below_average'
                else:
                    dashboard.benchmark_performance = 'poor'
            else:
                dashboard.benchmark_performance = 'average'

    def _calculate_energy_efficiency_score(self, readings, dashboard):
        """Calculate energy efficiency score (0-100)"""
        if not readings:
            return 0.0
            
        # Simplified calculation based on consumption per area
        total_area = self._get_total_area(dashboard)
        if total_area > 0:
            energy_per_sqm = dashboard.electricity_consumption / total_area
            # Efficiency score: lower consumption per sqm = higher score
            return max(0, 100 - (energy_per_sqm / 10))
        return 0.0

    def _calculate_water_efficiency_score(self, readings, dashboard):
        """Calculate water efficiency score (0-100)"""
        if not readings:
            return 0.0
            
        # Simplified calculation based on consumption per area
        total_area = self._get_total_area(dashboard)
        if total_area > 0:
            water_per_sqm = dashboard.water_consumption / total_area
            # Efficiency score: lower consumption per sqm = higher score
            return max(0, 100 - (water_per_sqm / 5))
        return 0.0

    def _calculate_co2_emissions(self, readings):
        """Calculate CO2 emissions in kg"""
        if not readings:
            return 0.0
            
        # CO2 emission factors
        electricity_factor = 0.5  # kg CO2 per kWh
        gas_factor = 2.0  # kg CO2 per m³
        steam_factor = 50.0  # kg CO2 per ton-hour
        
        total_emissions = 0
        for reading in readings:
            if reading.meter_id.meter_type == 'electricity':
                total_emissions += reading.consumption * electricity_factor
            elif reading.meter_id.meter_type == 'gas':
                total_emissions += reading.consumption * gas_factor
            elif reading.meter_id.meter_type == 'steam':
                total_emissions += reading.consumption * steam_factor
        
        return total_emissions

    def _calculate_peak_demand(self, electricity_readings):
        """Calculate peak demand from electricity readings"""
        if not electricity_readings:
            return 0.0
        return max(electricity_readings.mapped('consumption'))

    def _calculate_average_demand(self, electricity_readings):
        """Calculate average demand from electricity readings"""
        if not electricity_readings:
            return 0.0
        return sum(electricity_readings.mapped('consumption')) / len(electricity_readings)

    def _calculate_load_factor(self, peak_demand, average_demand):
        """Calculate load factor percentage"""
        if peak_demand > 0:
            return (average_demand / peak_demand) * 100
        return 0.0

    def _calculate_utilization_rate(self, readings):
        """Calculate utilization rate percentage"""
        if not readings:
            return 0.0
            
        # Simplified calculation based on expected vs actual consumption
        # In a real implementation, this would consider meter capacity and expected usage
        return min(100, (sum(readings.mapped('consumption')) / len(readings)) * 10)

    def _calculate_cost_per_sqm(self, total_cost, dashboard):
        """Calculate cost per square meter"""
        total_area = self._get_total_area(dashboard)
        return total_cost / total_area if total_area > 0 else 0.0

    def _calculate_cost_per_occupant(self, total_cost, dashboard):
        """Calculate cost per occupant"""
        total_occupants = self._get_total_occupants(dashboard)
        return total_cost / total_occupants if total_occupants > 0 else 0.0

    def _calculate_cost_per_hour(self, total_cost, dashboard):
        """Calculate cost per hour"""
        if dashboard.date_from and dashboard.date_to:
            period_hours = ((dashboard.date_to - dashboard.date_from).days + 1) * 24
            return total_cost / period_hours if period_hours > 0 else 0.0
        return 0.0

    def _get_total_area(self, dashboard):
        """Get total area for calculations"""
        if dashboard.facility_id:
            return len(dashboard.facility_id.building_ids) * 1000  # Simplified calculation
        elif dashboard.meter_ids:
            # Get unique facilities from meters
            facilities = dashboard.meter_ids.mapped('facility_id')
            return len(facilities) * 1000
        else:
            # All facilities
            facilities = self.env['facilities.facility'].search([])
            return len(facilities) * 1000

    def _get_total_occupants(self, dashboard):
        """Get total occupants for calculations"""
        if dashboard.facility_id:
            leases = self.env['facilities.lease'].search([('facility_id', '=', dashboard.facility_id.id)])
            return len(leases) * 2  # Simplified calculation
        elif dashboard.meter_ids:
            # Get unique facilities from meters
            facilities = dashboard.meter_ids.mapped('facility_id')
            total_occupants = 0
            for facility in facilities:
                leases = self.env['facilities.lease'].search([('facility_id', '=', facility.id)])
                total_occupants += len(leases) * 2
            return total_occupants
        else:
            # All facilities
            leases = self.env['facilities.lease'].search([])
            return len(leases) * 2

    def action_process(self):
        """Process energy performance analysis"""
        self.ensure_one()
        try:
            self.state = 'processing'
            
            # Force recomputation of all metrics
            self._compute_metrics()
            self._compute_trend_analysis()
            self._compute_alerts()
            self._compute_benchmark_analysis()
            
            # Store performance data as JSON
            performance_data = {
                'analysis_info': {
                    'name': self.name,
                    'date_from': self.date_from.isoformat(),
                    'date_to': self.date_to.isoformat(),
                    'facility_id': self.facility_id.id if self.facility_id else None,
                    'meter_count': len(self.meter_ids),
                    'processed_at': fields.Datetime.now().isoformat()
                },
                'metrics': {
                    'total_meters': self.total_meters,
                    'total_consumption': self.total_consumption,
                    'total_energy_cost': self.total_energy_cost,
                    'avg_efficiency_score': self.avg_efficiency_score,
                    'electricity_consumption': self.electricity_consumption,
                    'water_consumption': self.water_consumption,
                    'gas_consumption': self.gas_consumption,
                    'steam_consumption': self.steam_consumption,
                    'electricity_cost': self.electricity_cost,
                    'water_cost': self.water_cost,
                    'gas_cost': self.gas_cost,
                    'steam_cost': self.steam_cost,
                    'energy_efficiency_score': self.energy_efficiency_score,
                    'water_efficiency_score': self.water_efficiency_score,
                    'sustainability_score': self.sustainability_score,
                    'co2_emissions': self.co2_emissions,
                    'peak_demand': self.peak_demand,
                    'average_demand': self.average_demand,
                    'load_factor': self.load_factor,
                    'utilization_rate': self.utilization_rate,
                    'cost_per_sqm': self.cost_per_sqm,
                    'cost_per_occupant': self.cost_per_occupant,
                    'cost_per_hour': self.cost_per_hour
                },
                'trends': {
                    'consumption_trend': self.consumption_trend,
                    'trend_percentage': self.trend_percentage,
                    'cost_trend': self.cost_trend
                },
                'alerts': {
                    'total_alerts': self.total_alerts,
                    'high_consumption_alerts': self.high_consumption_alerts,
                    'cost_anomaly_alerts': self.cost_anomaly_alerts,
                    'maintenance_alerts': self.maintenance_alerts
                },
                'benchmark': {
                    'benchmark_performance': self.benchmark_performance,
                    'industry_benchmark_cost': self.industry_benchmark_cost,
                    'cost_per_sqm': self.cost_per_sqm
                }
            }
            
            self.performance_data = json.dumps(performance_data, indent=2)
            self.state = 'completed'
            
        except Exception as e:
            self.state = 'error'
            _logger.error(f"Error processing energy performance analysis: {str(e)}")
            raise ValidationError(f"Analysis processing failed: {str(e)}")

    def action_reset(self):
        """Reset to draft state"""
        self.ensure_one()
        self.write({
            'state': 'draft',
            'performance_data': ''
        })

    def get_comprehensive_dashboard_data(self, period='current_year', facility_id=None, date_from=None, date_to=None):
        """Get comprehensive dashboard data for the frontend"""
        try:
            # Determine date range based on period
            today = fields.Date.today()
            if period == 'custom_range':
                if date_from:
                    date_from = fields.Date.from_string(date_from) if isinstance(date_from, str) else date_from
                else:
                    date_from = today.replace(month=1, day=1)
                
                if date_to:
                    date_to = fields.Date.from_string(date_to) if isinstance(date_to, str) else date_to
                else:
                    date_to = today
                    
                if date_from > date_to:
                    date_from, date_to = date_to, date_from
                    
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

            # Create a temporary dashboard for calculations
            temp_dashboard = self.create({
                'name': f'Temp Analysis - {period}',
                'date_from': date_from,
                'date_to': date_to,
                'facility_id': facility_id,
                'state': 'draft'
            })
            
            # Force computation
            temp_dashboard._compute_metrics()
            temp_dashboard._compute_trend_analysis()
            temp_dashboard._compute_alerts()
            temp_dashboard._compute_benchmark_analysis()
            
            # Prepare comprehensive data
            dashboard_data = {
                'period': period,
                'facility_id': facility_id,
                'metrics': {
                    'total_meters': temp_dashboard.total_meters,
                    'total_consumption': temp_dashboard.total_consumption,
                    'total_energy_cost': temp_dashboard.total_energy_cost,
                    'avg_efficiency_score': temp_dashboard.avg_efficiency_score,
                    'electricity_consumption': temp_dashboard.electricity_consumption,
                    'water_consumption': temp_dashboard.water_consumption,
                    'gas_consumption': temp_dashboard.gas_consumption,
                    'steam_consumption': temp_dashboard.steam_consumption,
                    'electricity_cost': temp_dashboard.electricity_cost,
                    'water_cost': temp_dashboard.water_cost,
                    'gas_cost': temp_dashboard.gas_cost,
                    'steam_cost': temp_dashboard.steam_cost,
                    'energy_efficiency_score': temp_dashboard.energy_efficiency_score,
                    'water_efficiency_score': temp_dashboard.water_efficiency_score,
                    'sustainability_score': temp_dashboard.sustainability_score,
                    'co2_emissions': temp_dashboard.co2_emissions,
                    'peak_demand': temp_dashboard.peak_demand,
                    'average_demand': temp_dashboard.average_demand,
                    'load_factor': temp_dashboard.load_factor,
                    'utilization_rate': temp_dashboard.utilization_rate,
                    'cost_per_sqm': temp_dashboard.cost_per_sqm,
                    'cost_per_occupant': temp_dashboard.cost_per_occupant,
                    'cost_per_hour': temp_dashboard.cost_per_hour
                },
                'trends': {
                    'consumption_trend': temp_dashboard.consumption_trend,
                    'trend_percentage': temp_dashboard.trend_percentage,
                    'cost_trend': temp_dashboard.cost_trend,
                    'consumption_history': self._get_consumption_history(date_from, date_to, facility_id),
                    'cost_history': self._get_cost_history(date_from, date_to, facility_id)
                },
                'alerts': {
                    'total_alerts': temp_dashboard.total_alerts,
                    'high_consumption_alerts': temp_dashboard.high_consumption_alerts,
                    'cost_anomaly_alerts': temp_dashboard.cost_anomaly_alerts,
                    'maintenance_alerts': temp_dashboard.maintenance_alerts
                },
                'benchmark': {
                    'benchmark_performance': temp_dashboard.benchmark_performance,
                    'industry_benchmark_cost': temp_dashboard.industry_benchmark_cost,
                    'cost_per_sqm': temp_dashboard.cost_per_sqm
                },
                'summary': {
                    'total_meters': temp_dashboard.total_meters,
                    'total_alerts': temp_dashboard.total_alerts,
                    'last_updated': fields.Datetime.now().isoformat()
                }
            }
            
            # Clean up temporary dashboard
            temp_dashboard.unlink()
            
            return dashboard_data
            
        except Exception as e:
            _logger.error(f"Error getting comprehensive dashboard data: {str(e)}")
            return {'error': str(e)}

    def _get_consumption_history(self, date_from, date_to, facility_id):
        """Get consumption history for trend charts"""
        domain = [
            ('reading_date', '>=', date_from),
            ('reading_date', '<=', date_to),
            ('is_validated', '=', True)
        ]
        
        if facility_id:
            domain.append(('meter_id.facility_id', '=', facility_id))
        
        readings = self.env['facilities.energy.consumption'].search(domain, order='reading_date')
        
        history = []
        for reading in readings:
            history.append({
                'date': reading.reading_date.strftime('%Y-%m-%d'),
                'consumption': reading.consumption,
                'meter_type': reading.meter_id.meter_type,
                'facility_name': reading.meter_id.facility_id.name if reading.meter_id.facility_id else 'Unknown'
            })
        
        return history

    def _get_cost_history(self, date_from, date_to, facility_id):
        """Get cost history for trend charts"""
        domain = [
            ('reading_date', '>=', date_from),
            ('reading_date', '<=', date_to),
            ('is_validated', '=', True)
        ]
        
        if facility_id:
            domain.append(('meter_id.facility_id', '=', facility_id))
        
        readings = self.env['facilities.energy.consumption'].search(domain, order='reading_date')
        
        history = []
        for reading in readings:
            history.append({
                'date': reading.reading_date.strftime('%Y-%m-%d'),
                'cost': reading.total_cost,
                'meter_type': reading.meter_id.meter_type,
                'facility_name': reading.meter_id.facility_id.name if reading.meter_id.facility_id else 'Unknown'
            })
        
        return history
