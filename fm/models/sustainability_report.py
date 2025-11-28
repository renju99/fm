# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)


class SustainabilityReport(models.Model):
    _name = 'facilities.sustainability.report'
    _description = 'Sustainability Report'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'report_date desc'

    # Standard Odoo fields
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company, 
                                tracking=True, index=True)

    # Basic Information
    name = fields.Char(string='Report Name', required=True, tracking=True)
    report_code = fields.Char(string='Report Code', required=True, copy=False, 
                            readonly=True, default='New', tracking=True)
    report_type = fields.Selection([
        ('monthly', 'Monthly Report'),
        ('quarterly', 'Quarterly Report'),
        ('annual', 'Annual Report'),
        ('custom', 'Custom Period Report')
    ], string='Report Type', required=True, tracking=True)
    
    # Reporting Period
    report_date = fields.Date(string='Report Date', required=True, 
                            default=fields.Date.today, tracking=True)
    period_start_date = fields.Date(string='Period Start Date', required=True, tracking=True)
    period_end_date = fields.Date(string='Period End Date', required=True, tracking=True)
    
    # Scope
    facility_id = fields.Many2one('facilities.facility', string='Facility', 
                                tracking=True, ondelete='restrict')
    include_all_facilities = fields.Boolean(string='Include All Facilities', 
                                          default=False, tracking=True)
    
    # Report Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True, required=True)
    
    # Energy Consumption Summary
    total_electricity_consumption = fields.Float(string='Total Electricity Consumption (kWh)', 
                                               digits=(16, 2), compute='_compute_energy_summary', store=True)
    total_water_consumption = fields.Float(string='Total Water Consumption (m³)', 
                                         digits=(16, 2), compute='_compute_energy_summary', store=True)
    total_gas_consumption = fields.Float(string='Total Gas Consumption (m³)', 
                                       digits=(16, 2), compute='_compute_energy_summary', store=True)
    total_steam_consumption = fields.Float(string='Total Steam Consumption (Ton-hour)', 
                                         digits=(16, 2), compute='_compute_energy_summary', store=True)
    
    # Cost Summary
    total_energy_cost = fields.Float(string='Total Energy Cost', digits=(16, 2), 
                                   compute='_compute_energy_summary', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    
    # Carbon Footprint
    total_co2_emissions = fields.Float(string='Total CO₂ Emissions (kg)', 
                                     digits=(16, 2), compute='_compute_carbon_footprint', store=True)
    co2_emissions_per_sqm = fields.Float(string='CO₂ Emissions per m² (kg/m²)', 
                                       digits=(16, 2), compute='_compute_carbon_footprint', store=True)
    co2_emissions_per_occupant = fields.Float(string='CO₂ Emissions per Occupant (kg/person)', 
                                            digits=(16, 2), compute='_compute_carbon_footprint', store=True)
    
    # Efficiency Metrics
    energy_efficiency_index = fields.Float(string='Energy Efficiency Index', 
                                         digits=(16, 2), compute='_compute_efficiency_metrics', store=True)
    water_efficiency_index = fields.Float(string='Water Efficiency Index', 
                                        digits=(16, 2), compute='_compute_efficiency_metrics', store=True)
    overall_sustainability_score = fields.Float(string='Overall Sustainability Score', 
                                              digits=(16, 2), compute='_compute_sustainability_score', store=True)
    cost_per_sqm = fields.Float(string='Cost per m²', digits=(16, 2), 
                               compute='_compute_cost_metrics', store=True)
    cost_per_occupant = fields.Float(string='Cost per Occupant', digits=(16, 2), 
                                   compute='_compute_cost_metrics', store=True)
    
    # Comparison Data
    previous_period_consumption = fields.Float(string='Previous Period Consumption', 
                                             digits=(16, 2), compute='_compute_comparison', store=True)
    consumption_change_percentage = fields.Float(string='Consumption Change (%)', 
                                               digits=(16, 2), compute='_compute_comparison', store=True)
    cost_change_percentage = fields.Float(string='Cost Change (%)', 
                                        digits=(16, 2), compute='_compute_comparison', store=True)
    
    # Goals and Targets
    energy_reduction_target = fields.Float(string='Energy Reduction Target (%)', 
                                         digits=(16, 2), default=5.0, tracking=True)
    water_reduction_target = fields.Float(string='Water Reduction Target (%)', 
                                        digits=(16, 2), default=10.0, tracking=True)
    target_achievement = fields.Selection([
        ('exceeded', 'Target Exceeded'),
        ('met', 'Target Met'),
        ('partial', 'Partially Met'),
        ('not_met', 'Target Not Met')
    ], string='Target Achievement', compute='_compute_target_achievement', store=True)
    
    # Detailed Breakdown
    meter_consumption_ids = fields.One2many('facilities.sustainability.meter.summary', 
                                          'report_id', string='Meter Consumption Summary')
    facility_breakdown_ids = fields.One2many('facilities.sustainability.facility.summary', 
                                           'report_id', string='Facility Breakdown')
    
    # Environmental Impact
    renewable_energy_percentage = fields.Float(string='Renewable Energy Percentage (%)', 
                                             digits=(16, 2), default=0.0, tracking=True)
    waste_reduction_percentage = fields.Float(string='Waste Reduction Percentage (%)', 
                                            digits=(16, 2), default=0.0, tracking=True)
    recycling_rate = fields.Float(string='Recycling Rate (%)', 
                                 digits=(16, 2), default=0.0, tracking=True)
    
    # Certifications and Standards
    leed_certification = fields.Selection([
        ('none', 'No LEED Certification'),
        ('certified', 'LEED Certified'),
        ('silver', 'LEED Silver'),
        ('gold', 'LEED Gold'),
        ('platinum', 'LEED Platinum')
    ], string='LEED Certification', tracking=True)
    
    iso_14001_compliance = fields.Boolean(string='ISO 14001 Compliance', default=False, tracking=True)
    energy_star_rating = fields.Integer(string='Energy Star Rating', tracking=True)
    
    # Notes and Recommendations
    executive_summary = fields.Text(string='Executive Summary', tracking=True)
    key_findings = fields.Text(string='Key Findings', tracking=True)
    recommendations = fields.Text(string='Recommendations', tracking=True)
    action_items = fields.Text(string='Action Items', tracking=True)
    
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
            if vals.get('report_code', 'New') == 'New':
                vals['report_code'] = self.env['ir.sequence'].next_by_code('facilities.sustainability.report') or 'New'
        return super(SustainabilityReport, self).create(vals_list)

    @api.depends('period_start_date', 'period_end_date', 'facility_id', 'include_all_facilities')
    def _compute_energy_summary(self):
        for report in self:
            if not report.period_start_date or not report.period_end_date:
                continue
                
            # Get consumption readings for the period
            domain = [
                ('reading_date', '>=', report.period_start_date),
                ('reading_date', '<=', report.period_end_date)
            ]
            
            if not report.include_all_facilities and report.facility_id:
                domain.append(('meter_id.facility_id', '=', report.facility_id.id))
            
            readings = self.env['facilities.energy.consumption'].search(domain)
            
            # Calculate totals by meter type
            electricity_meters = readings.filtered(lambda r: r.meter_id.meter_type == 'electricity')
            water_meters = readings.filtered(lambda r: r.meter_id.meter_type == 'water')
            gas_meters = readings.filtered(lambda r: r.meter_id.meter_type == 'gas')
            steam_meters = readings.filtered(lambda r: r.meter_id.meter_type == 'steam')
            
            report.total_electricity_consumption = sum(electricity_meters.mapped('consumption'))
            report.total_water_consumption = sum(water_meters.mapped('consumption'))
            report.total_gas_consumption = sum(gas_meters.mapped('consumption'))
            report.total_steam_consumption = sum(steam_meters.mapped('consumption'))
            report.total_energy_cost = sum(readings.mapped('total_cost'))

    @api.depends('total_electricity_consumption', 'total_gas_consumption', 'total_steam_consumption')
    def _compute_carbon_footprint(self):
        for report in self:
            # CO2 emission factors (kg CO2 per unit)
            electricity_factor = 0.5  # kg CO2 per kWh
            gas_factor = 2.0  # kg CO2 per m³
            steam_factor = 50.0  # kg CO2 per ton-hour
            
            co2_electricity = report.total_electricity_consumption * electricity_factor
            co2_gas = report.total_gas_consumption * gas_factor
            co2_steam = report.total_steam_consumption * steam_factor
            
            report.total_co2_emissions = co2_electricity + co2_gas + co2_steam
            
            # Calculate per square meter and per occupant
            total_area = self._get_total_area(report)
            total_occupants = self._get_total_occupants(report)
            
            report.co2_emissions_per_sqm = report.total_co2_emissions / total_area if total_area > 0 else 0
            report.co2_emissions_per_occupant = report.total_co2_emissions / total_occupants if total_occupants > 0 else 0

    @api.depends('total_electricity_consumption', 'total_water_consumption')
    def _compute_efficiency_metrics(self):
        for report in self:
            # Calculate efficiency indices (simplified calculation)
            total_area = self._get_total_area(report)
            total_occupants = self._get_total_occupants(report)
            
            if total_area > 0:
                report.energy_efficiency_index = report.total_electricity_consumption / total_area
                report.water_efficiency_index = report.total_water_consumption / total_area
            else:
                report.energy_efficiency_index = 0
                report.water_efficiency_index = 0

    @api.depends('energy_efficiency_index', 'water_efficiency_index', 'renewable_energy_percentage', 
                'recycling_rate', 'waste_reduction_percentage')
    def _compute_sustainability_score(self):
        for report in self:
            # Calculate overall sustainability score (0-100)
            # This is a simplified scoring algorithm
            score = 0
            
            # Energy efficiency (30 points max)
            if report.energy_efficiency_index > 0:
                # Lower consumption per area is better
                efficiency_score = max(0, 30 - (report.energy_efficiency_index / 10))
                score += efficiency_score
            
            # Water efficiency (20 points max)
            if report.water_efficiency_index > 0:
                water_score = max(0, 20 - (report.water_efficiency_index / 5))
                score += water_score
            
            # Renewable energy (25 points max)
            score += report.renewable_energy_percentage * 0.25
            
            # Waste management (25 points max)
            score += report.recycling_rate * 0.15
            score += report.waste_reduction_percentage * 0.10
            
            report.overall_sustainability_score = min(score, 100)

    @api.depends('period_start_date', 'period_end_date', 'facility_id', 'include_all_facilities')
    def _compute_comparison(self):
        for report in self:
            if not report.period_start_date or not report.period_end_date:
                continue
                
            # Calculate previous period
            period_duration = (report.period_end_date - report.period_start_date).days
            prev_end_date = report.period_start_date - timedelta(days=1)
            prev_start_date = prev_end_date - timedelta(days=period_duration)
            
            # Get previous period consumption
            domain = [
                ('reading_date', '>=', prev_start_date),
                ('reading_date', '<=', prev_end_date)
            ]
            
            if not report.include_all_facilities and report.facility_id:
                domain.append(('meter_id.facility_id', '=', report.facility_id.id))
            
            prev_readings = self.env['facilities.energy.consumption'].search(domain)
            prev_consumption = sum(prev_readings.mapped('consumption'))
            prev_cost = sum(prev_readings.mapped('total_cost'))
            
            report.previous_period_consumption = prev_consumption
            
            if prev_consumption > 0:
                report.consumption_change_percentage = ((report.total_energy_cost - prev_cost) / prev_cost) * 100
            else:
                report.consumption_change_percentage = 0
                
            if prev_cost > 0:
                report.cost_change_percentage = ((report.total_energy_cost - prev_cost) / prev_cost) * 100
            else:
                report.cost_change_percentage = 0

    @api.depends('consumption_change_percentage', 'energy_reduction_target', 'water_reduction_target')
    def _compute_target_achievement(self):
        for report in self:
            if report.consumption_change_percentage <= -report.energy_reduction_target:
                report.target_achievement = 'exceeded'
            elif report.consumption_change_percentage <= 0:
                report.target_achievement = 'met'
            elif report.consumption_change_percentage <= report.energy_reduction_target:
                report.target_achievement = 'partial'
            else:
                report.target_achievement = 'not_met'

    @api.depends('total_energy_cost', 'facility_id', 'include_all_facilities')
    def _compute_cost_metrics(self):
        for report in self:
            # Calculate cost per square meter
            if report.facility_id and report.facility_id.total_area > 0:
                report.cost_per_sqm = report.total_energy_cost / report.facility_id.total_area
            else:
                report.cost_per_sqm = 0
                
            # Calculate cost per occupant
            if report.facility_id and report.facility_id.capacity > 0:
                report.cost_per_occupant = report.total_energy_cost / report.facility_id.capacity
            else:
                report.cost_per_occupant = 0

    def _get_total_area(self, report):
        """Get total area for the report scope"""
        if report.include_all_facilities:
            facilities = self.env['facilities.facility'].search([])
        elif report.facility_id:
            facilities = report.facility_id
        else:
            return 0
            
        total_area = 0
        for facility in facilities:
            # Sum up building areas (simplified - would need actual area fields)
            total_area += len(facility.building_ids) * 1000  # Assuming 1000 sqm per building
        return total_area

    def _get_total_occupants(self, report):
        """Get total occupants for the report scope"""
        if report.include_all_facilities:
            facilities = self.env['facilities.facility'].search([])
        elif report.facility_id:
            facilities = report.facility_id
        else:
            return 0
            
        total_occupants = 0
        for facility in facilities:
            # Sum up lease occupants (simplified calculation)
            leases = self.env['facilities.lease'].search([('facility_id', '=', facility.id)])
            total_occupants += len(leases) * 2  # Assuming 2 people per lease
        return total_occupants

    @api.constrains('period_start_date', 'period_end_date')
    def _check_period_dates(self):
        for report in self:
            if report.period_start_date and report.period_end_date:
                if report.period_start_date >= report.period_end_date:
                    raise ValidationError(_("Period start date must be before period end date."))

    def action_start_report(self):
        for report in self:
            report.state = 'in_progress'

    def action_send_for_review(self):
        for report in self:
            report.state = 'review'

    def action_approve(self):
        for report in self:
            report.state = 'approved'
            report.approved_by_id = self.env.user.id
            report.approval_date = fields.Date.today()

    def action_publish(self):
        for report in self:
            report.state = 'published'

    def action_archive(self):
        for report in self:
            report.state = 'archived'

    def generate_detailed_breakdown(self):
        """Generate detailed breakdown of consumption by meter and facility"""
        for report in self:
            # Clear existing breakdowns
            report.meter_consumption_ids.unlink()
            report.facility_breakdown_ids.unlink()
            
            # Generate meter consumption summary
            domain = [
                ('reading_date', '>=', report.period_start_date),
                ('reading_date', '<=', report.period_end_date)
            ]
            
            if not report.include_all_facilities and report.facility_id:
                domain.append(('meter_id.facility_id', '=', report.facility_id.id))
            
            readings = self.env['facilities.energy.consumption'].search(domain)
            
            # Group by meter
            meter_groups = {}
            for reading in readings:
                meter_id = reading.meter_id.id
                if meter_id not in meter_groups:
                    meter_groups[meter_id] = {
                        'meter_id': reading.meter_id.id,
                        'total_consumption': 0,
                        'total_cost': 0,
                        'readings_count': 0
                    }
                meter_groups[meter_id]['total_consumption'] += reading.consumption
                meter_groups[meter_id]['total_cost'] += reading.total_cost
                meter_groups[meter_id]['readings_count'] += 1
            
            # Create meter summary records
            for meter_data in meter_groups.values():
                self.env['facilities.sustainability.meter.summary'].create({
                    'report_id': report.id,
                    'meter_id': meter_data['meter_id'],
                    'total_consumption': meter_data['total_consumption'],
                    'total_cost': meter_data['total_cost'],
                    'readings_count': meter_data['readings_count']
                })
            
            # Group by facility
            facility_groups = {}
            for reading in readings:
                facility_id = reading.meter_id.facility_id.id
                if facility_id not in facility_groups:
                    facility_groups[facility_id] = {
                        'facility_id': facility_id,
                        'total_consumption': 0,
                        'total_cost': 0,
                        'meter_count': 0
                    }
                facility_groups[facility_id]['total_consumption'] += reading.consumption
                facility_groups[facility_id]['total_cost'] += reading.total_cost
            
            # Count unique meters per facility
            for facility_id in facility_groups:
                meters = readings.filtered(lambda r: r.meter_id.facility_id.id == facility_id)
                facility_groups[facility_id]['meter_count'] = len(meters.mapped('meter_id'))
            
            # Create facility summary records
            for facility_data in facility_groups.values():
                self.env['facilities.sustainability.facility.summary'].create({
                    'report_id': report.id,
                    'facility_id': facility_data['facility_id'],
                    'total_consumption': facility_data['total_consumption'],
                    'total_cost': facility_data['total_cost'],
                    'meter_count': facility_data['meter_count']
                })

    def action_view_meter_consumption(self):
        """Action to view meter consumption summary for this report"""
        self.ensure_one()
        return {
            'name': _('Meter Consumption Summary'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.sustainability.meter.summary',
            'view_mode': 'list,form',
            'domain': [('report_id', '=', self.id)],
            'context': {
                'default_report_id': self.id,
            },
        }

    def action_view_facility_breakdown(self):
        """Action to view facility breakdown for this report"""
        self.ensure_one()
        return {
            'name': _('Facility Breakdown'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.sustainability.facility.summary',
            'view_mode': 'list,form',
            'domain': [('report_id', '=', self.id)],
            'context': {
                'default_report_id': self.id,
            },
        }


class SustainabilityMeterSummary(models.Model):
    _name = 'facilities.sustainability.meter.summary'
    _description = 'Sustainability Report Meter Summary'
    _rec_name = 'meter_name'

    report_id = fields.Many2one('facilities.sustainability.report', string='Report', 
                              required=True, ondelete='cascade')
    meter_id = fields.Many2one('facilities.utility.meter', string='Meter', required=True)
    meter_name = fields.Char(string='Meter Name', related='meter_id.name', store=True)
    meter_type = fields.Selection(string='Meter Type', related='meter_id.meter_type', store=True)
    facility_name = fields.Char(string='Facility', related='meter_id.facility_id.name', store=True)
    
    total_consumption = fields.Float(string='Total Consumption', digits=(16, 2))
    total_cost = fields.Float(string='Total Cost', digits=(16, 2))
    readings_count = fields.Integer(string='Number of Readings')
    average_consumption = fields.Float(string='Average Consumption', digits=(16, 2), 
                                     compute='_compute_average_consumption')

    @api.depends('total_consumption', 'readings_count')
    def _compute_average_consumption(self):
        for record in self:
            record.average_consumption = record.total_consumption / record.readings_count if record.readings_count > 0 else 0


class SustainabilityFacilitySummary(models.Model):
    _name = 'facilities.sustainability.facility.summary'
    _description = 'Sustainability Report Facility Summary'
    _rec_name = 'facility_name'

    report_id = fields.Many2one('facilities.sustainability.report', string='Report', 
                              required=True, ondelete='cascade')
    facility_id = fields.Many2one('facilities.facility', string='Facility', required=True)
    facility_name = fields.Char(string='Facility Name', related='facility_id.name', store=True)
    
    total_consumption = fields.Float(string='Total Consumption', digits=(16, 2))
    total_cost = fields.Float(string='Total Cost', digits=(16, 2))
    meter_count = fields.Integer(string='Number of Meters')
    consumption_per_meter = fields.Float(string='Consumption per Meter', digits=(16, 2), 
                                       compute='_compute_consumption_per_meter')

    @api.depends('total_consumption', 'meter_count')
    def _compute_consumption_per_meter(self):
        for record in self:
            record.consumption_per_meter = record.total_consumption / record.meter_count if record.meter_count > 0 else 0
