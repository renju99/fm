# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)


class EnergyBenchmark(models.Model):
    _name = 'facilities.energy.benchmark'
    _description = 'Energy Benchmark'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Standard Odoo fields
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company, 
                                tracking=True, index=True)

    # Basic Information
    name = fields.Char(string='Benchmark Name', required=True, tracking=True)
    benchmark_code = fields.Char(string='Benchmark Code', required=True, copy=False, 
                               readonly=True, default='New', tracking=True)
    benchmark_type = fields.Selection([
        ('energy_intensity', 'Energy Intensity (kWh/m²)'),
        ('water_intensity', 'Water Intensity (m³/m²)'),
        ('cost_per_sqm', 'Cost per Square Meter'),
        ('cost_per_occupant', 'Cost per Occupant'),
        ('carbon_intensity', 'Carbon Intensity (kg CO₂/m²)'),
        ('efficiency_rating', 'Efficiency Rating'),
        ('custom', 'Custom Benchmark')
    ], string='Benchmark Type', required=True, tracking=True)
    
    # Benchmark Scope
    facility_type = fields.Selection([
        ('office', 'Office Building'),
        ('retail', 'Retail'),
        ('industrial', 'Industrial'),
        ('healthcare', 'Healthcare'),
        ('education', 'Education'),
        ('hospitality', 'Hospitality'),
        ('residential', 'Residential'),
        ('warehouse', 'Warehouse'),
        ('data_center', 'Data Center'),
        ('mixed_use', 'Mixed-Use'),
        ('all', 'All Types')
    ], string='Facility Type', default='all', tracking=True)
    
    climate_zone = fields.Selection([
        ('tropical', 'Tropical'),
        ('subtropical', 'Subtropical'),
        ('temperate', 'Temperate'),
        ('continental', 'Continental'),
        ('arctic', 'Arctic'),
        ('all', 'All Zones')
    ], string='Climate Zone', default='all', tracking=True)
    
    building_size_category = fields.Selection([
        ('small', 'Small (< 5,000 m²)'),
        ('medium', 'Medium (5,000 - 25,000 m²)'),
        ('large', 'Large (25,000 - 100,000 m²)'),
        ('very_large', 'Very Large (> 100,000 m²)'),
        ('all', 'All Sizes')
    ], string='Building Size Category', default='all', tracking=True)
    
    # Benchmark Values
    benchmark_value = fields.Float(string='Benchmark Value', digits=(16, 4), 
                                 required=True, tracking=True)
    unit_of_measure = fields.Char(string='Unit of Measure', required=True, tracking=True)
    
    # Performance Levels
    excellent_threshold = fields.Float(string='Excellent Threshold', digits=(16, 4), 
                                     tracking=True, help="Top 10% performance")
    good_threshold = fields.Float(string='Good Threshold', digits=(16, 4), 
                                tracking=True, help="Top 25% performance")
    average_threshold = fields.Float(string='Average Threshold', digits=(16, 4), 
                                   tracking=True, help="Middle 50% performance")
    below_average_threshold = fields.Float(string='Below Average Threshold', digits=(16, 4), 
                                         tracking=True, help="Bottom 25% performance")
    
    # Data Source
    data_source = fields.Selection([
        ('industry_standard', 'Industry Standard'),
        ('government_data', 'Government Data'),
        ('peer_group', 'Peer Group'),
        ('historical', 'Historical Data'),
        ('custom', 'Custom Data')
    ], string='Data Source', required=True, tracking=True)
    
    data_source_reference = fields.Char(string='Data Source Reference', tracking=True)
    data_collection_date = fields.Date(string='Data Collection Date', tracking=True)
    sample_size = fields.Integer(string='Sample Size', tracking=True)
    
    # Validity
    effective_date = fields.Date(string='Effective Date', required=True, 
                               default=fields.Date.today, tracking=True)
    expiry_date = fields.Date(string='Expiry Date', tracking=True)
    is_active = fields.Boolean(string='Active', default=True, tracking=True)
    
    # Currency and Regional Context
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    country_id = fields.Many2one('res.country', string='Country')
    state_id = fields.Many2one('res.country.state', string='State/Province')
    
    # Notes and Documentation
    notes = fields.Text(string='Notes', tracking=True)
    methodology = fields.Text(string='Methodology', tracking=True)
    assumptions = fields.Text(string='Assumptions', tracking=True)
    limitations = fields.Text(string='Limitations', tracking=True)
    
    # Mail fields for chatter
    message_ids = fields.One2many('mail.message', 'res_id', string='Messages')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('benchmark_code', 'New') == 'New':
                vals['benchmark_code'] = self.env['ir.sequence'].next_by_code('facilities.energy.benchmark') or 'New'
        return super(EnergyBenchmark, self).create(vals_list)

    @api.constrains('effective_date', 'expiry_date')
    def _check_dates(self):
        for benchmark in self:
            if benchmark.effective_date and benchmark.expiry_date:
                if benchmark.effective_date >= benchmark.expiry_date:
                    raise ValidationError(_("Effective date must be before expiry date."))

    @api.constrains('benchmark_value', 'excellent_threshold', 'good_threshold', 
                   'average_threshold', 'below_average_threshold')
    def _check_thresholds(self):
        for benchmark in self:
            thresholds = [
                benchmark.excellent_threshold,
                benchmark.good_threshold,
                benchmark.average_threshold,
                benchmark.below_average_threshold
            ]
            
            # Remove zero values
            thresholds = [t for t in thresholds if t > 0]
            
            if len(thresholds) > 1:
                if benchmark.benchmark_type in ['energy_intensity', 'water_intensity', 
                                               'cost_per_sqm', 'cost_per_occupant', 
                                               'carbon_intensity']:
                    # For intensity metrics, lower is better
                    if not all(thresholds[i] <= thresholds[i+1] for i in range(len(thresholds)-1)):
                        raise ValidationError(_("For intensity metrics, thresholds should be in ascending order (lower is better)."))
                else:
                    # For efficiency metrics, higher is better
                    if not all(thresholds[i] >= thresholds[i+1] for i in range(len(thresholds)-1)):
                        raise ValidationError(_("For efficiency metrics, thresholds should be in descending order (higher is better)."))

    def get_performance_level(self, actual_value):
        """Determine performance level based on actual value"""
        self.ensure_one()
        
        if not actual_value or actual_value <= 0:
            return 'no_data'
        
        if self.benchmark_type in ['energy_intensity', 'water_intensity', 
                                 'cost_per_sqm', 'cost_per_occupant', 
                                 'carbon_intensity']:
            # For intensity metrics, lower is better
            if self.excellent_threshold and actual_value <= self.excellent_threshold:
                return 'excellent'
            elif self.good_threshold and actual_value <= self.good_threshold:
                return 'good'
            elif self.average_threshold and actual_value <= self.average_threshold:
                return 'average'
            elif self.below_average_threshold and actual_value <= self.below_average_threshold:
                return 'below_average'
            else:
                return 'poor'
        else:
            # For efficiency metrics, higher is better
            if self.excellent_threshold and actual_value >= self.excellent_threshold:
                return 'excellent'
            elif self.good_threshold and actual_value >= self.good_threshold:
                return 'good'
            elif self.average_threshold and actual_value >= self.average_threshold:
                return 'average'
            elif self.below_average_threshold and actual_value >= self.below_average_threshold:
                return 'below_average'
            else:
                return 'poor'

    def get_benchmark_comparison(self, facility_id, period_start, period_end):
        """Get benchmark comparison for a facility"""
        self.ensure_one()
        
        facility = self.env['facilities.facility'].browse(facility_id)
        
        # Get actual consumption data
        domain = [
            ('meter_id.facility_id', '=', facility_id),
            ('reading_date', '>=', period_start),
            ('reading_date', '<=', period_end)
        ]
        
        readings = self.env['facilities.energy.consumption'].search(domain)
        
        if not readings:
            return {
                'actual_value': 0,
                'benchmark_value': self.benchmark_value,
                'performance_level': 'no_data',
                'variance_percentage': 0,
                'comparison_status': 'no_data'
            }
        
        # Calculate actual value based on benchmark type
        if self.benchmark_type == 'energy_intensity':
            total_consumption = sum(readings.filtered(
                lambda r: r.meter_id.meter_type == 'electricity'
            ).mapped('consumption'))
            total_area = facility.area_sqm or 1
            actual_value = total_consumption / total_area
            
        elif self.benchmark_type == 'water_intensity':
            total_consumption = sum(readings.filtered(
                lambda r: r.meter_id.meter_type == 'water'
            ).mapped('consumption'))
            total_area = facility.area_sqm or 1
            actual_value = total_consumption / total_area
            
        elif self.benchmark_type == 'cost_per_sqm':
            total_cost = sum(readings.mapped('total_cost'))
            total_area = facility.area_sqm or 1
            actual_value = total_cost / total_area
            
        elif self.benchmark_type == 'cost_per_occupant':
            total_cost = sum(readings.mapped('total_cost'))
            total_occupants = facility.capacity or 1
            actual_value = total_cost / total_occupants
            
        elif self.benchmark_type == 'carbon_intensity':
            # Calculate CO2 emissions
            electricity_factor = 0.5  # kg CO2 per kWh
            gas_factor = 2.0  # kg CO2 per m³
            steam_factor = 50.0  # kg CO2 per ton-hour
            
            electricity_consumption = sum(readings.filtered(
                lambda r: r.meter_id.meter_type == 'electricity'
            ).mapped('consumption'))
            gas_consumption = sum(readings.filtered(
                lambda r: r.meter_id.meter_type == 'gas'
            ).mapped('consumption'))
            steam_consumption = sum(readings.filtered(
                lambda r: r.meter_id.meter_type == 'steam'
            ).mapped('consumption'))
            
            total_co2 = (electricity_consumption * electricity_factor + 
                        gas_consumption * gas_factor + 
                        steam_consumption * steam_factor)
            
            total_area = facility.area_sqm or 1
            actual_value = total_co2 / total_area
            
        else:
            actual_value = 0
        
        # Get performance level
        performance_level = self.get_performance_level(actual_value)
        
        # Calculate variance
        if self.benchmark_value > 0:
            if self.benchmark_type in ['energy_intensity', 'water_intensity', 
                                     'cost_per_sqm', 'cost_per_occupant', 
                                     'carbon_intensity']:
                # For intensity metrics, negative variance is good
                variance_percentage = ((actual_value - self.benchmark_value) / self.benchmark_value) * 100
            else:
                # For efficiency metrics, positive variance is good
                variance_percentage = ((actual_value - self.benchmark_value) / self.benchmark_value) * 100
        else:
            variance_percentage = 0
        
        # Determine comparison status
        if performance_level == 'excellent':
            comparison_status = 'above_benchmark'
        elif performance_level in ['good', 'average']:
            comparison_status = 'at_benchmark'
        else:
            comparison_status = 'below_benchmark'
        
        return {
            'actual_value': actual_value,
            'benchmark_value': self.benchmark_value,
            'performance_level': performance_level,
            'variance_percentage': variance_percentage,
            'comparison_status': comparison_status,
            'unit_of_measure': self.unit_of_measure
        }

    def action_create_benchmark_report(self):
        """Create a benchmark report for all facilities"""
        self.ensure_one()
        
        report_data = []
        facilities = self.env['facilities.facility'].search([])
        
        for facility in facilities:
            # Check if facility matches benchmark criteria
            if not self._facility_matches_criteria(facility):
                continue
            
            # Get comparison data
            period_start = fields.Date.today().replace(day=1)  # Current month
            period_end = fields.Date.today()
            
            comparison = self.get_benchmark_comparison(facility.id, period_start, period_end)
            
            if comparison['actual_value'] > 0:
                report_data.append({
                    'facility_id': facility.id,
                    'facility_name': facility.name,
                    'actual_value': comparison['actual_value'],
                    'benchmark_value': comparison['benchmark_value'],
                    'performance_level': comparison['performance_level'],
                    'variance_percentage': comparison['variance_percentage'],
                    'comparison_status': comparison['comparison_status']
                })
        
        return report_data

    def _facility_matches_criteria(self, facility):
        """Check if facility matches benchmark criteria"""
        # Check facility type
        if self.facility_type != 'all' and facility.property_type != self.facility_type:
            return False
        
        # Check building size category
        if self.building_size_category != 'all':
            area = facility.area_sqm or 0
            if self.building_size_category == 'small' and area >= 5000:
                return False
            elif self.building_size_category == 'medium' and (area < 5000 or area > 25000):
                return False
            elif self.building_size_category == 'large' and (area < 25000 or area > 100000):
                return False
            elif self.building_size_category == 'very_large' and area < 100000:
                return False
        
        # Check location
        if self.country_id and facility.country_id != self.country_id:
            return False
        if self.state_id and facility.state_id != self.state_id:
            return False
        
        return True

    @api.model
    def get_default_benchmarks(self):
        """Get default industry benchmarks"""
        default_benchmarks = [
            {
                'name': 'Office Building Energy Intensity',
                'benchmark_type': 'energy_intensity',
                'facility_type': 'office',
                'benchmark_value': 150.0,  # kWh/m²/year
                'unit_of_measure': 'kWh/m²/year',
                'excellent_threshold': 100.0,
                'good_threshold': 125.0,
                'average_threshold': 150.0,
                'below_average_threshold': 200.0,
                'data_source': 'industry_standard',
                'data_source_reference': 'ASHRAE 90.1',
                'methodology': 'Based on ASHRAE 90.1 Energy Standard for Buildings'
            },
            {
                'name': 'Office Building Water Intensity',
                'benchmark_type': 'water_intensity',
                'facility_type': 'office',
                'benchmark_value': 0.8,  # m³/m²/year
                'unit_of_measure': 'm³/m²/year',
                'excellent_threshold': 0.5,
                'good_threshold': 0.65,
                'average_threshold': 0.8,
                'below_average_threshold': 1.2,
                'data_source': 'industry_standard',
                'data_source_reference': 'EPA WaterSense',
                'methodology': 'Based on EPA WaterSense commercial building benchmarks'
            }
        ]
        
        return default_benchmarks

    def action_create_default_benchmarks(self):
        """Create default industry benchmarks"""
        default_benchmarks = self.get_default_benchmarks()
        
        for benchmark_data in default_benchmarks:
            existing = self.search([
                ('name', '=', benchmark_data['name']),
                ('company_id', '=', self.env.company.id)
            ])
            
            if not existing:
                self.create(benchmark_data)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Default benchmarks created successfully.'),
                'type': 'success',
            }
        }


class EnergyBenchmarkReport(models.Model):
    _name = 'facilities.energy.benchmark.report'
    _description = 'Energy Benchmark Report'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Standard Odoo fields
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company, 
                                tracking=True, index=True)

    # Basic Information
    name = fields.Char(string='Report Name', required=True, tracking=True)
    report_code = fields.Char(string='Report Code', required=True, copy=False, 
                            readonly=True, default='New', tracking=True)
    
    # Report Configuration
    benchmark_id = fields.Many2one('facilities.energy.benchmark', 
                                 string='Benchmark', required=True, tracking=True)
    report_period_start = fields.Date(string='Report Period Start', required=True, tracking=True)
    report_period_end = fields.Date(string='Report Period End', required=True, tracking=True)
    
    # Report Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True, required=True)
    
    # Report Data
    total_facilities = fields.Integer(string='Total Facilities', 
                                    compute='_compute_report_summary', store=True)
    facilities_above_benchmark = fields.Integer(string='Facilities Above Benchmark', 
                                              compute='_compute_report_summary', store=True)
    facilities_at_benchmark = fields.Integer(string='Facilities At Benchmark', 
                                           compute='_compute_report_summary', store=True)
    facilities_below_benchmark = fields.Integer(string='Facilities Below Benchmark', 
                                              compute='_compute_report_summary', store=True)
    
    # Detailed Results
    benchmark_results_ids = fields.One2many('facilities.energy.benchmark.result', 
                                          'report_id', string='Benchmark Results')
    
    # Generated by
    generated_by_id = fields.Many2one('res.users', string='Generated By', 
                                    default=lambda self: self.env.user, tracking=True)
    generated_date = fields.Datetime(string='Generated Date', tracking=True)
    
    # Mail fields for chatter
    message_ids = fields.One2many('mail.message', 'res_id', string='Messages')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('report_code', 'New') == 'New':
                vals['report_code'] = self.env['ir.sequence'].next_by_code('facilities.energy.benchmark.report') or 'New'
        return super(EnergyBenchmarkReport, self).create(vals_list)

    @api.depends('benchmark_results_ids')
    def _compute_report_summary(self):
        for report in self:
            results = report.benchmark_results_ids
            report.total_facilities = len(results)
            report.facilities_above_benchmark = len(results.filtered(
                lambda r: r.comparison_status == 'above_benchmark'
            ))
            report.facilities_at_benchmark = len(results.filtered(
                lambda r: r.comparison_status == 'at_benchmark'
            ))
            report.facilities_below_benchmark = len(results.filtered(
                lambda r: r.comparison_status == 'below_benchmark'
            ))

    def action_generate_report(self):
        """Generate the benchmark report"""
        for report in self:
            # Clear existing results
            report.benchmark_results_ids.unlink()
            
            # Generate new results
            report_data = report.benchmark_id.action_create_benchmark_report()
            
            for data in report_data:
                self.env['facilities.energy.benchmark.result'].create({
                    'report_id': report.id,
                    'facility_id': data['facility_id'],
                    'actual_value': data['actual_value'],
                    'benchmark_value': data['benchmark_value'],
                    'performance_level': data['performance_level'],
                    'variance_percentage': data['variance_percentage'],
                    'comparison_status': data['comparison_status']
                })
            
            report.state = 'generated'
            report.generated_date = fields.Datetime.now()

    def action_publish_report(self):
        """Publish the benchmark report"""
        for report in self:
            report.state = 'published'

    def action_archive_report(self):
        """Archive the benchmark report"""
        for report in self:
            report.state = 'archived'


class EnergyBenchmarkResult(models.Model):
    _name = 'facilities.energy.benchmark.result'
    _description = 'Energy Benchmark Result'

    report_id = fields.Many2one('facilities.energy.benchmark.report', 
                              string='Report', required=True, ondelete='cascade')
    facility_id = fields.Many2one('facilities.facility', string='Facility', required=True)
    facility_name = fields.Char(string='Facility Name', related='facility_id.name', store=True)
    
    actual_value = fields.Float(string='Actual Value', digits=(16, 4))
    benchmark_value = fields.Float(string='Benchmark Value', digits=(16, 4))
    performance_level = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('average', 'Average'),
        ('below_average', 'Below Average'),
        ('poor', 'Poor'),
        ('no_data', 'No Data')
    ], string='Performance Level')
    
    variance_percentage = fields.Float(string='Variance (%)', digits=(16, 2))
    comparison_status = fields.Selection([
        ('above_benchmark', 'Above Benchmark'),
        ('at_benchmark', 'At Benchmark'),
        ('below_benchmark', 'Below Benchmark'),
        ('no_data', 'No Data')
    ], string='Comparison Status')
