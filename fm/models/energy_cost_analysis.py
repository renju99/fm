# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)


class EnergyCostAnalysis(models.Model):
    _name = 'facilities.energy.cost.analysis'
    _description = 'Energy Cost Analysis'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'analysis_date desc'

    # Standard Odoo fields
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company, 
                                tracking=True, index=True)

    # Basic Information
    name = fields.Char(string='Analysis Name', required=True, tracking=True)
    analysis_code = fields.Char(string='Analysis Code', required=True, copy=False, 
                              readonly=True, default='New', tracking=True)
    analysis_type = fields.Selection([
        ('monthly', 'Monthly Analysis'),
        ('quarterly', 'Quarterly Analysis'),
        ('annual', 'Annual Analysis'),
        ('budget_vs_actual', 'Budget vs Actual'),
        ('trend', 'Trend Analysis'),
        ('benchmark', 'Benchmark Analysis'),
        ('custom', 'Custom Analysis')
    ], string='Analysis Type', required=True, tracking=True)
    
    # Analysis Period
    analysis_date = fields.Date(string='Analysis Date', required=True, 
                              default=fields.Date.today, tracking=True)
    period_start_date = fields.Date(string='Period Start Date', required=True, tracking=True)
    period_end_date = fields.Date(string='Period End Date', required=True, tracking=True)
    
    # Scope
    facility_id = fields.Many2one('facilities.facility', string='Facility', 
                                tracking=True, ondelete='restrict')
    building_id = fields.Many2one('facilities.building', string='Building', 
                                tracking=True, ondelete='restrict')
    include_all_facilities = fields.Boolean(string='Include All Facilities', 
                                          default=False, tracking=True)
    
    # Analysis Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculating', 'Calculating'),
        ('completed', 'Completed'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True, required=True)
    
    # Cost Summary
    total_energy_cost = fields.Float(string='Total Energy Cost', digits=(16, 2), 
                                   compute='_compute_cost_summary', store=True)
    total_electricity_cost = fields.Float(string='Total Electricity Cost', digits=(16, 2), 
                                        compute='_compute_cost_summary', store=True)
    total_water_cost = fields.Float(string='Total Water Cost', digits=(16, 2), 
                                  compute='_compute_cost_summary', store=True)
    total_gas_cost = fields.Float(string='Total Gas Cost', digits=(16, 2), 
                                compute='_compute_cost_summary', store=True)
    total_steam_cost = fields.Float(string='Total Steam Cost', digits=(16, 2), 
                                  compute='_compute_cost_summary', store=True)
    
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    
    # Cost per Unit Analysis
    cost_per_sqm = fields.Float(string='Cost per m²', digits=(16, 2), 
                               compute='_compute_cost_metrics', store=True)
    cost_per_occupant = fields.Float(string='Cost per Occupant', digits=(16, 2), 
                                   compute='_compute_cost_metrics', store=True)
    cost_per_hour = fields.Float(string='Cost per Hour', digits=(16, 2), 
                               compute='_compute_cost_metrics', store=True)
    cost_per_day = fields.Float(string='Cost per Day', digits=(16, 2), 
                              compute='_compute_cost_metrics', store=True)
    
    # Budget Analysis
    budgeted_cost = fields.Float(string='Budgeted Cost', digits=(16, 2), tracking=True)
    variance_amount = fields.Float(string='Variance Amount', digits=(16, 2), 
                                 compute='_compute_budget_analysis', store=True)
    variance_percentage = fields.Float(string='Variance Percentage (%)', digits=(16, 2), 
                                     compute='_compute_budget_analysis', store=True)
    budget_performance = fields.Selection([
        ('under_budget', 'Under Budget'),
        ('on_budget', 'On Budget'),
        ('over_budget', 'Over Budget')
    ], string='Budget Performance', compute='_compute_budget_analysis', store=True)
    
    # Trend Analysis
    previous_period_cost = fields.Float(string='Previous Period Cost', digits=(16, 2), 
                                      compute='_compute_trend_analysis', store=True)
    cost_change_amount = fields.Float(string='Cost Change Amount', digits=(16, 2), 
                                    compute='_compute_trend_analysis', store=True)
    cost_change_percentage = fields.Float(string='Cost Change Percentage (%)', digits=(16, 2), 
                                        compute='_compute_trend_analysis', store=True)
    cost_trend = fields.Selection([
        ('increasing', 'Increasing'),
        ('decreasing', 'Decreasing'),
        ('stable', 'Stable'),
        ('fluctuating', 'Fluctuating')
    ], string='Cost Trend', compute='_compute_trend_analysis', store=True)
    
    # Benchmark Analysis
    industry_average_cost_per_sqm = fields.Float(string='Industry Average Cost per m²', 
                                               digits=(16, 2), tracking=True)
    benchmark_performance = fields.Selection([
        ('excellent', 'Excellent (Top 10%)'),
        ('good', 'Good (Top 25%)'),
        ('average', 'Average (Middle 50%)'),
        ('below_average', 'Below Average (Bottom 25%)'),
        ('poor', 'Poor (Bottom 10%)')
    ], string='Benchmark Performance', compute='_compute_benchmark_analysis', store=True)
    
    # Peak and Off-Peak Analysis
    peak_hours_cost = fields.Float(string='Peak Hours Cost', digits=(16, 2), 
                                 compute='_compute_peak_analysis', store=True)
    off_peak_hours_cost = fields.Float(string='Off-Peak Hours Cost', digits=(16, 2), 
                                     compute='_compute_peak_analysis', store=True)
    peak_off_peak_ratio = fields.Float(string='Peak/Off-Peak Ratio', digits=(16, 2), 
                                     compute='_compute_peak_analysis', store=True)
    
    # Seasonal Analysis
    seasonal_variance = fields.Float(string='Seasonal Variance (%)', digits=(16, 2), 
                                   compute='_compute_seasonal_analysis', store=True)
    highest_cost_month = fields.Char(string='Highest Cost Month', 
                                   compute='_compute_seasonal_analysis', store=True)
    lowest_cost_month = fields.Char(string='Lowest Cost Month', 
                                  compute='_compute_seasonal_analysis', store=True)
    
    # Detailed Breakdown
    meter_cost_breakdown_ids = fields.One2many('facilities.energy.cost.breakdown', 
                                             'analysis_id', string='Meter Cost Breakdown')
    facility_cost_breakdown_ids = fields.One2many('facilities.energy.facility.cost.breakdown', 
                                                'analysis_id', string='Facility Cost Breakdown')
    
    # Recommendations
    cost_optimization_opportunities = fields.Text(string='Cost Optimization Opportunities', tracking=True)
    energy_efficiency_recommendations = fields.Text(string='Energy Efficiency Recommendations', tracking=True)
    budget_recommendations = fields.Text(string='Budget Recommendations', tracking=True)
    
    # Approval
    prepared_by_id = fields.Many2one('res.users', string='Prepared By', 
                                   default=lambda self: self.env.user, tracking=True)
    reviewed_by_id = fields.Many2one('res.users', string='Reviewed By', tracking=True)
    approved_by_id = fields.Many2one('res.users', string='Approved By', tracking=True)
    review_date = fields.Date(string='Review Date', tracking=True)
    approval_date = fields.Date(string='Approval Date', tracking=True)
    
    # Attachments
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    
    # Mail fields for chatter
    message_ids = fields.One2many('mail.message', 'res_id', string='Messages')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('analysis_code', 'New') == 'New':
                vals['analysis_code'] = self.env['ir.sequence'].next_by_code('facilities.energy.cost.analysis') or 'New'
        return super(EnergyCostAnalysis, self).create(vals_list)

    @api.depends('period_start_date', 'period_end_date', 'facility_id', 'building_id', 'include_all_facilities')
    def _compute_cost_summary(self):
        for analysis in self:
            if not analysis.period_start_date or not analysis.period_end_date:
                continue
                
            # Get consumption readings for the period
            domain = [
                ('reading_date', '>=', analysis.period_start_date),
                ('reading_date', '<=', analysis.period_end_date)
            ]
            
            if not analysis.include_all_facilities:
                if analysis.facility_id:
                    domain.append(('meter_id.facility_id', '=', analysis.facility_id.id))
                if analysis.building_id:
                    domain.append(('meter_id.building_id', '=', analysis.building_id.id))
            
            readings = self.env['facilities.energy.consumption'].search(domain)
            
            # Calculate totals by meter type
            electricity_readings = readings.filtered(lambda r: r.meter_id.meter_type == 'electricity')
            water_readings = readings.filtered(lambda r: r.meter_id.meter_type == 'water')
            gas_readings = readings.filtered(lambda r: r.meter_id.meter_type == 'gas')
            steam_readings = readings.filtered(lambda r: r.meter_id.meter_type == 'steam')
            
            analysis.total_electricity_cost = sum(electricity_readings.mapped('total_cost'))
            analysis.total_water_cost = sum(water_readings.mapped('total_cost'))
            analysis.total_gas_cost = sum(gas_readings.mapped('total_cost'))
            analysis.total_steam_cost = sum(steam_readings.mapped('total_cost'))
            analysis.total_energy_cost = sum(readings.mapped('total_cost'))

    @api.depends('total_energy_cost', 'facility_id', 'building_id', 'include_all_facilities')
    def _compute_cost_metrics(self):
        for analysis in self:
            # Calculate cost per square meter
            total_area = self._get_total_area(analysis)
            if total_area > 0:
                analysis.cost_per_sqm = analysis.total_energy_cost / total_area
            else:
                analysis.cost_per_sqm = 0
            
            # Calculate cost per occupant
            total_occupants = self._get_total_occupants(analysis)
            if total_occupants > 0:
                analysis.cost_per_occupant = analysis.total_energy_cost / total_occupants
            else:
                analysis.cost_per_occupant = 0
            
            # Calculate cost per hour and per day
            if analysis.period_start_date and analysis.period_end_date:
                period_days = (analysis.period_end_date - analysis.period_start_date).days + 1
                analysis.cost_per_day = analysis.total_energy_cost / period_days if period_days > 0 else 0
                analysis.cost_per_hour = analysis.cost_per_day / 24 if analysis.cost_per_day > 0 else 0

    @api.depends('total_energy_cost', 'budgeted_cost')
    def _compute_budget_analysis(self):
        for analysis in self:
            if analysis.budgeted_cost > 0:
                analysis.variance_amount = analysis.total_energy_cost - analysis.budgeted_cost
                analysis.variance_percentage = (analysis.variance_amount / analysis.budgeted_cost) * 100
                
                if analysis.variance_percentage < -5:
                    analysis.budget_performance = 'under_budget'
                elif analysis.variance_percentage <= 5:
                    analysis.budget_performance = 'on_budget'
                else:
                    analysis.budget_performance = 'over_budget'
            else:
                analysis.variance_amount = 0
                analysis.variance_percentage = 0
                analysis.budget_performance = 'on_budget'

    @api.depends('period_start_date', 'period_end_date', 'facility_id', 'building_id', 'include_all_facilities')
    def _compute_trend_analysis(self):
        for analysis in self:
            if not analysis.period_start_date or not analysis.period_end_date:
                continue
                
            # Calculate previous period
            period_duration = (analysis.period_end_date - analysis.period_start_date).days
            prev_end_date = analysis.period_start_date - timedelta(days=1)
            prev_start_date = prev_end_date - timedelta(days=period_duration)
            
            # Get previous period cost
            domain = [
                ('reading_date', '>=', prev_start_date),
                ('reading_date', '<=', prev_end_date)
            ]
            
            if not analysis.include_all_facilities:
                if analysis.facility_id:
                    domain.append(('meter_id.facility_id', '=', analysis.facility_id.id))
                if analysis.building_id:
                    domain.append(('meter_id.building_id', '=', analysis.building_id.id))
            
            prev_readings = self.env['facilities.energy.consumption'].search(domain)
            prev_cost = sum(prev_readings.mapped('total_cost'))
            
            analysis.previous_period_cost = prev_cost
            analysis.cost_change_amount = analysis.total_energy_cost - prev_cost
            
            if prev_cost > 0:
                analysis.cost_change_percentage = (analysis.cost_change_amount / prev_cost) * 100
                
                if analysis.cost_change_percentage > 10:
                    analysis.cost_trend = 'increasing'
                elif analysis.cost_change_percentage < -10:
                    analysis.cost_trend = 'decreasing'
                elif abs(analysis.cost_change_percentage) <= 5:
                    analysis.cost_trend = 'stable'
                else:
                    analysis.cost_trend = 'fluctuating'
            else:
                analysis.cost_change_percentage = 0
                analysis.cost_trend = 'stable'

    @api.depends('cost_per_sqm', 'industry_average_cost_per_sqm')
    def _compute_benchmark_analysis(self):
        for analysis in self:
            if analysis.industry_average_cost_per_sqm > 0 and analysis.cost_per_sqm > 0:
                ratio = analysis.cost_per_sqm / analysis.industry_average_cost_per_sqm
                
                if ratio <= 0.9:
                    analysis.benchmark_performance = 'excellent'
                elif ratio <= 1.1:
                    analysis.benchmark_performance = 'good'
                elif ratio <= 1.3:
                    analysis.benchmark_performance = 'average'
                elif ratio <= 1.5:
                    analysis.benchmark_performance = 'below_average'
                else:
                    analysis.benchmark_performance = 'poor'
            else:
                analysis.benchmark_performance = 'average'

    @api.depends('period_start_date', 'period_end_date', 'facility_id', 'building_id', 'include_all_facilities')
    def _compute_peak_analysis(self):
        for analysis in self:
            # This is a simplified peak analysis
            # In a real implementation, you would need to define peak hours and get detailed consumption data
            analysis.peak_hours_cost = analysis.total_energy_cost * 0.6  # Assume 60% during peak hours
            analysis.off_peak_hours_cost = analysis.total_energy_cost * 0.4  # Assume 40% during off-peak hours
            
            if analysis.off_peak_hours_cost > 0:
                analysis.peak_off_peak_ratio = analysis.peak_hours_cost / analysis.off_peak_hours_cost
            else:
                analysis.peak_off_peak_ratio = 0

    @api.depends('period_start_date', 'period_end_date', 'facility_id', 'building_id', 'include_all_facilities')
    def _compute_seasonal_analysis(self):
        for analysis in self:
            # Simplified seasonal analysis
            # In a real implementation, you would analyze monthly data
            monthly_costs = {}
            
            if analysis.period_start_date and analysis.period_end_date:
                current_date = analysis.period_start_date.replace(day=1)
                while current_date <= analysis.period_end_date:
                    month_start = current_date
                    if current_date.month == 12:
                        month_end = current_date.replace(year=current_date.year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        month_end = current_date.replace(month=current_date.month + 1, day=1) - timedelta(days=1)
                    
                    # Get monthly cost
                    domain = [
                        ('reading_date', '>=', month_start),
                        ('reading_date', '<=', month_end)
                    ]
                    
                    if not analysis.include_all_facilities:
                        if analysis.facility_id:
                            domain.append(('meter_id.facility_id', '=', analysis.facility_id.id))
                        if analysis.building_id:
                            domain.append(('meter_id.building_id', '=', analysis.building_id.id))
                    
                    monthly_readings = self.env['facilities.energy.consumption'].search(domain)
                    monthly_cost = sum(monthly_readings.mapped('total_cost'))
                    monthly_costs[current_date.strftime('%B %Y')] = monthly_cost
                    
                    if current_date.month == 12:
                        current_date = current_date.replace(year=current_date.year + 1, month=1)
                    else:
                        current_date = current_date.replace(month=current_date.month + 1)
            
            if monthly_costs:
                highest_month = max(monthly_costs, key=monthly_costs.get)
                lowest_month = min(monthly_costs, key=monthly_costs.get)
                
                analysis.highest_cost_month = highest_month
                analysis.lowest_cost_month = lowest_month
                
                # Calculate seasonal variance
                avg_cost = sum(monthly_costs.values()) / len(monthly_costs)
                max_cost = max(monthly_costs.values())
                min_cost = min(monthly_costs.values())
                
                if avg_cost > 0:
                    analysis.seasonal_variance = ((max_cost - min_cost) / avg_cost) * 100
                else:
                    analysis.seasonal_variance = 0
            else:
                analysis.highest_cost_month = ''
                analysis.lowest_cost_month = ''
                analysis.seasonal_variance = 0

    def _get_total_area(self, analysis):
        """Get total area for the analysis scope"""
        if analysis.include_all_facilities:
            facilities = self.env['facilities.facility'].search([])
        elif analysis.facility_id:
            facilities = analysis.facility_id
        else:
            return 0
            
        total_area = 0
        for facility in facilities:
            if analysis.building_id:
                # Only include the specific building
                total_area += 1000  # Simplified calculation
            else:
                # Include all buildings in the facility
                total_area += len(facility.building_ids) * 1000
        return total_area

    def _get_total_occupants(self, analysis):
        """Get total occupants for the analysis scope"""
        if analysis.include_all_facilities:
            facilities = self.env['facilities.facility'].search([])
        elif analysis.facility_id:
            facilities = analysis.facility_id
        else:
            return 0
            
        total_occupants = 0
        for facility in facilities:
            if analysis.building_id:
                # Only include occupants in the specific building
                total_occupants += 10  # Simplified calculation
            else:
                # Include all occupants in the facility
                leases = self.env['facilities.lease'].search([('facility_id', '=', facility.id)])
                total_occupants += len(leases) * 2  # Assuming 2 people per lease
        return total_occupants

    @api.constrains('period_start_date', 'period_end_date')
    def _check_period_dates(self):
        for analysis in self:
            if analysis.period_start_date and analysis.period_end_date:
                if analysis.period_start_date >= analysis.period_end_date:
                    raise ValidationError(_("Period start date must be before period end date."))

    def action_start_analysis(self):
        for analysis in self:
            analysis.state = 'calculating'

    def action_complete_analysis(self):
        for analysis in self:
            analysis.state = 'completed'
            analysis.generate_detailed_breakdown()

    def action_send_for_review(self):
        for analysis in self:
            analysis.state = 'review'

    def action_approve(self):
        for analysis in self:
            analysis.state = 'approved'
            analysis.approved_by_id = self.env.user.id
            analysis.approval_date = fields.Date.today()

    def action_archive(self):
        for analysis in self:
            analysis.state = 'archived'

    def generate_detailed_breakdown(self):
        """Generate detailed breakdown of costs by meter and facility"""
        for analysis in self:
            # Clear existing breakdowns
            analysis.meter_cost_breakdown_ids.unlink()
            analysis.facility_cost_breakdown_ids.unlink()
            
            # Generate meter cost breakdown
            domain = [
                ('reading_date', '>=', analysis.period_start_date),
                ('reading_date', '<=', analysis.period_end_date)
            ]
            
            if not analysis.include_all_facilities:
                if analysis.facility_id:
                    domain.append(('meter_id.facility_id', '=', analysis.facility_id.id))
                if analysis.building_id:
                    domain.append(('meter_id.building_id', '=', analysis.building_id.id))
            
            readings = self.env['facilities.energy.consumption'].search(domain)
            
            # Group by meter
            meter_groups = {}
            for reading in readings:
                meter_id = reading.meter_id.id
                if meter_id not in meter_groups:
                    meter_groups[meter_id] = {
                        'meter_id': reading.meter_id.id,
                        'total_cost': 0,
                        'total_consumption': 0,
                        'readings_count': 0
                    }
                meter_groups[meter_id]['total_cost'] += reading.total_cost
                meter_groups[meter_id]['total_consumption'] += reading.consumption
                meter_groups[meter_id]['readings_count'] += 1
            
            # Create meter cost breakdown records
            for meter_data in meter_groups.values():
                self.env['facilities.energy.cost.breakdown'].create({
                    'analysis_id': analysis.id,
                    'meter_id': meter_data['meter_id'],
                    'total_cost': meter_data['total_cost'],
                    'total_consumption': meter_data['total_consumption'],
                    'readings_count': meter_data['readings_count']
                })
            
            # Group by facility
            facility_groups = {}
            for reading in readings:
                facility_id = reading.meter_id.facility_id.id
                if facility_id not in facility_groups:
                    facility_groups[facility_id] = {
                        'facility_id': facility_id,
                        'total_cost': 0,
                        'total_consumption': 0,
                        'meter_count': 0
                    }
                facility_groups[facility_id]['total_cost'] += reading.total_cost
                facility_groups[facility_id]['total_consumption'] += reading.consumption
            
            # Count unique meters per facility
            for facility_id in facility_groups:
                meters = readings.filtered(lambda r: r.meter_id.facility_id.id == facility_id)
                facility_groups[facility_id]['meter_count'] = len(meters.mapped('meter_id'))
            
            # Create facility cost breakdown records
            for facility_data in facility_groups.values():
                self.env['facilities.energy.facility.cost.breakdown'].create({
                    'analysis_id': analysis.id,
                    'facility_id': facility_data['facility_id'],
                    'total_cost': facility_data['total_cost'],
                    'total_consumption': facility_data['total_consumption'],
                    'meter_count': facility_data['meter_count']
                })

    def action_view_meter_breakdown(self):
        """Open meter cost breakdown view"""
        self.ensure_one()
        return {
            'name': _('Meter Cost Breakdown'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.energy.cost.breakdown',
            'view_mode': 'list,form',
            'domain': [('analysis_id', '=', self.id)],
            'context': {'default_analysis_id': self.id},
            'target': 'current',
        }

    def action_view_facility_breakdown(self):
        """Open facility cost breakdown view"""
        self.ensure_one()
        return {
            'name': _('Facility Cost Breakdown'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.energy.facility.cost.breakdown',
            'view_mode': 'list,form',
            'domain': [('analysis_id', '=', self.id)],
            'context': {'default_analysis_id': self.id},
            'target': 'current',
        }


class EnergyCostBreakdown(models.Model):
    _name = 'facilities.energy.cost.breakdown'
    _description = 'Energy Cost Analysis Meter Breakdown'
    _rec_name = 'meter_name'

    analysis_id = fields.Many2one('facilities.energy.cost.analysis', string='Analysis', 
                                required=True, ondelete='cascade')
    meter_id = fields.Many2one('facilities.utility.meter', string='Meter', required=True)
    meter_name = fields.Char(string='Meter Name', related='meter_id.name', store=True)
    meter_type = fields.Selection(string='Meter Type', related='meter_id.meter_type', store=True)
    facility_name = fields.Char(string='Facility', related='meter_id.facility_id.name', store=True)
    
    total_cost = fields.Float(string='Total Cost', digits=(16, 2))
    total_consumption = fields.Float(string='Total Consumption', digits=(16, 2))
    readings_count = fields.Integer(string='Number of Readings')
    average_cost_per_reading = fields.Float(string='Average Cost per Reading', digits=(16, 2), 
                                          compute='_compute_average_cost')
    cost_per_unit = fields.Float(string='Cost per Unit', digits=(16, 2), 
                               compute='_compute_cost_per_unit')

    @api.depends('total_cost', 'readings_count')
    def _compute_average_cost(self):
        for record in self:
            record.average_cost_per_reading = record.total_cost / record.readings_count if record.readings_count > 0 else 0

    @api.depends('total_cost', 'total_consumption')
    def _compute_cost_per_unit(self):
        for record in self:
            record.cost_per_unit = record.total_cost / record.total_consumption if record.total_consumption > 0 else 0


class EnergyFacilityCostBreakdown(models.Model):
    _name = 'facilities.energy.facility.cost.breakdown'
    _description = 'Energy Cost Analysis Facility Breakdown'
    _rec_name = 'facility_name'

    analysis_id = fields.Many2one('facilities.energy.cost.analysis', string='Analysis', 
                                required=True, ondelete='cascade')
    facility_id = fields.Many2one('facilities.facility', string='Facility', required=True)
    facility_name = fields.Char(string='Facility Name', related='facility_id.name', store=True)
    
    total_cost = fields.Float(string='Total Cost', digits=(16, 2))
    total_consumption = fields.Float(string='Total Consumption', digits=(16, 2))
    meter_count = fields.Integer(string='Number of Meters')
    cost_per_meter = fields.Float(string='Cost per Meter', digits=(16, 2), 
                                compute='_compute_cost_per_meter')
    consumption_per_meter = fields.Float(string='Consumption per Meter', digits=(16, 2), 
                                       compute='_compute_consumption_per_meter')

    @api.depends('total_cost', 'meter_count')
    def _compute_cost_per_meter(self):
        for record in self:
            record.cost_per_meter = record.total_cost / record.meter_count if record.meter_count > 0 else 0

    @api.depends('total_consumption', 'meter_count')
    def _compute_consumption_per_meter(self):
        for record in self:
            record.consumption_per_meter = record.total_consumption / record.meter_count if record.meter_count > 0 else 0
