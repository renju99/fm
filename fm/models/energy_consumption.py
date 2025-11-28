# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)


class EnergyConsumption(models.Model):
    _name = 'facilities.energy.consumption'
    _description = 'Energy Consumption Reading'
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reading_date desc'

    # Standard Odoo fields
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company, 
                                tracking=True, index=True)

    # Basic Information
    name = fields.Char(string='Reading Reference', required=True, copy=False, 
                      readonly=True, default='New', tracking=True)
    meter_id = fields.Many2one('facilities.utility.meter', string='Meter', 
                              required=True, tracking=True, ondelete='cascade')
    
    # Reading Information
    reading_date = fields.Datetime(string='Reading Date', required=True, 
                                 default=fields.Datetime.now, tracking=True)
    reading_value = fields.Float(string='Reading Value', digits=(16, 2), 
                               required=True, tracking=True)
    consumption = fields.Float(string='Consumption', digits=(16, 2), 
                             compute='_compute_consumption', store=True)
    
    # Reading Details
    reading_type = fields.Selection([
        ('manual', 'Manual Reading'),
        ('automatic', 'Automatic Reading'),
        ('estimated', 'Estimated Reading'),
        ('corrected', 'Corrected Reading')
    ], string='Reading Type', default='manual', required=True, tracking=True)
    
    reading_user_id = fields.Many2one('res.users', string='Reading User', 
                                    default=lambda self: self.env.user, tracking=True)
    is_validated = fields.Boolean(string='Validated', default=False, tracking=True)
    validated_by_id = fields.Many2one('res.users', string='Validated By', tracking=True)
    validated_date = fields.Datetime(string='Validation Date', tracking=True)
    
    # Consumption Analysis
    daily_consumption = fields.Float(string='Daily Consumption', digits=(16, 2), 
                                   compute='_compute_daily_consumption', store=True)
    monthly_consumption = fields.Float(string='Monthly Consumption', digits=(16, 2), 
                                     compute='_compute_monthly_consumption', store=True)
    
    # Cost Information
    cost_per_unit = fields.Float(string='Cost per Unit', digits=(16, 4), 
                                related='meter_id.cost_per_unit', store=True)
    total_cost = fields.Float(string='Total Cost', digits=(16, 2), 
                             compute='_compute_total_cost', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 related='meter_id.currency_id', store=True)
    
    # Comparison and Analysis
    previous_reading_id = fields.Many2one('facilities.energy.consumption', 
                                        string='Previous Reading', 
                                        compute='_compute_previous_reading', store=True)
    consumption_variance = fields.Float(string='Consumption Variance', 
                                      digits=(16, 2), compute='_compute_consumption_variance', store=False)
    variance_percentage = fields.Float(string='Variance Percentage', 
                                     digits=(16, 2), compute='_compute_variance_percentage', store=True)
    
    # Weather and External Factors
    temperature = fields.Float(string='Temperature (°C)', digits=(8, 2), tracking=True)
    humidity = fields.Float(string='Humidity (%)', digits=(8, 2), tracking=True)
    occupancy_factor = fields.Float(string='Occupancy Factor', digits=(8, 2), 
                                   default=1.0, tracking=True,
                                   help="Factor to account for building occupancy (1.0 = full occupancy)")
    
    # Anomaly Detection
    is_anomaly = fields.Boolean(string='Anomaly Detected', default=False, tracking=True)
    anomaly_reason = fields.Text(string='Anomaly Reason', tracking=True)
    anomaly_severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Anomaly Severity', tracking=True)
    
    # Notes and Comments
    notes = fields.Text(string='Notes', tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    
    # Computed Display Name
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', 
                              store=True)
    
    # Mail fields for chatter
    message_ids = fields.One2many('mail.message', 'res_id', string='Messages')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('facilities.energy.consumption') or 'New'
        return super(EnergyConsumption, self).create(vals_list)

    @api.depends('reading_value', 'previous_reading_id.reading_value')
    def _compute_consumption(self):
        for record in self:
            if record.previous_reading_id and record.reading_value:
                consumption = record.reading_value - record.previous_reading_id.reading_value
                record.consumption = max(consumption, 0)  # Prevent negative consumption
            else:
                record.consumption = 0.0

    @api.depends('consumption')
    def _compute_daily_consumption(self):
        for record in self:
            if record.consumption:
                # Get consumption for the same day
                start_of_day = record.reading_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = start_of_day + timedelta(days=1)
                
                daily_readings = self.search([
                    ('meter_id', '=', record.meter_id.id),
                    ('reading_date', '>=', start_of_day),
                    ('reading_date', '<', end_of_day),
                    ('id', '<=', record.id)
                ])
                record.daily_consumption = sum(daily_readings.mapped('consumption'))
            else:
                record.daily_consumption = 0.0

    @api.depends('consumption')
    def _compute_monthly_consumption(self):
        for record in self:
            if record.consumption:
                # Get consumption for the same month
                start_of_month = record.reading_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if record.reading_date.month == 12:
                    end_of_month = start_of_month.replace(year=record.reading_date.year + 1, month=1)
                else:
                    end_of_month = start_of_month.replace(month=record.reading_date.month + 1)
                
                monthly_readings = self.search([
                    ('meter_id', '=', record.meter_id.id),
                    ('reading_date', '>=', start_of_month),
                    ('reading_date', '<', end_of_month),
                    ('id', '<=', record.id)
                ])
                record.monthly_consumption = sum(monthly_readings.mapped('consumption'))
            else:
                record.monthly_consumption = 0.0

    @api.depends('consumption', 'cost_per_unit')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = record.consumption * (record.cost_per_unit or 0)

    @api.depends('meter_id', 'reading_date')
    def _compute_previous_reading(self):
        for record in self:
            if record.meter_id and record.reading_date:
                previous = self.search([
                    ('meter_id', '=', record.meter_id.id),
                    ('reading_date', '<', record.reading_date),
                    ('id', '!=', record.id)
                ], order='reading_date desc', limit=1)
                record.previous_reading_id = previous.id if previous else False
            else:
                record.previous_reading_id = False

    @api.depends('consumption', 'previous_reading_id.consumption')
    def _compute_consumption_variance(self):
        for record in self:
            if record.previous_reading_id and record.previous_reading_id.consumption > 0:
                variance = record.consumption - record.previous_reading_id.consumption
                record.consumption_variance = variance
            else:
                record.consumption_variance = 0.0

    @api.depends('consumption', 'previous_reading_id.consumption')
    def _compute_variance_percentage(self):
        for record in self:
            if record.previous_reading_id and record.previous_reading_id.consumption > 0:
                variance = record.consumption - record.previous_reading_id.consumption
                record.variance_percentage = (variance / record.previous_reading_id.consumption) * 100
            else:
                record.variance_percentage = 0.0

    @api.depends('meter_id', 'reading_date', 'consumption')
    def _compute_display_name(self):
        for record in self:
            if record.meter_id and record.reading_date:
                record.display_name = f"{record.meter_id.name} - {record.reading_date.strftime('%Y-%m-%d %H:%M')} ({record.consumption} {record.meter_id.unit_of_measure or ''})"
            else:
                record.display_name = record.name

    @api.constrains('reading_value')
    def _check_reading_value(self):
        for record in self:
            if record.reading_value < 0:
                raise ValidationError(_("Reading value cannot be negative."))
            
            if record.previous_reading_id and record.reading_value < record.previous_reading_id.reading_value:
                raise ValidationError(_("New reading value cannot be less than the previous reading."))

    @api.constrains('consumption')
    def _check_consumption_anomaly(self):
        for record in self:
            if record.consumption > 0:
                # Simple anomaly detection based on variance
                if record.variance_percentage > 100:  # More than 100% increase
                    record.is_anomaly = True
                    record.anomaly_severity = 'high'
                    record.anomaly_reason = f"Consumption increased by {record.variance_percentage:.1f}% compared to previous reading"
                elif record.variance_percentage > 50:  # More than 50% increase
                    record.is_anomaly = True
                    record.anomaly_severity = 'medium'
                    record.anomaly_reason = f"Consumption increased by {record.variance_percentage:.1f}% compared to previous reading"

    def action_validate_reading(self):
        for record in self:
            record.is_validated = True
            record.validated_by_id = self.env.user.id
            record.validated_date = fields.Datetime.now()

    def action_unvalidate_reading(self):
        for record in self:
            record.is_validated = False
            record.validated_by_id = False
            record.validated_date = False

    def get_consumption_trend(self, days=30):
        """Get consumption trend data for the last N days"""
        end_date = fields.Datetime.now()
        start_date = end_date - timedelta(days=days)
        
        readings = self.search([
            ('meter_id', '=', self.meter_id.id),
            ('reading_date', '>=', start_date),
            ('reading_date', '<=', end_date)
        ], order='reading_date')
        
        trend_data = []
        for reading in readings:
            trend_data.append({
                'date': reading.reading_date.strftime('%Y-%m-%d'),
                'consumption': reading.consumption,
                'cost': reading.total_cost,
                'temperature': reading.temperature,
                'is_anomaly': reading.is_anomaly
            })
        
        return trend_data

    def get_efficiency_metrics(self):
        """Calculate energy efficiency metrics"""
        metrics = {}
        
        # Calculate average consumption per day
        recent_readings = self.search([
            ('meter_id', '=', self.meter_id.id),
            ('reading_date', '>=', fields.Datetime.now() - timedelta(days=30))
        ])
        
        if recent_readings:
            total_consumption = sum(recent_readings.mapped('consumption'))
            days = len(recent_readings)
            metrics['avg_daily_consumption'] = total_consumption / days if days > 0 else 0
            metrics['total_consumption_30d'] = total_consumption
            metrics['readings_count'] = days
            
            # Calculate cost efficiency
            total_cost = sum(recent_readings.mapped('total_cost'))
            metrics['avg_daily_cost'] = total_cost / days if days > 0 else 0
            metrics['total_cost_30d'] = total_cost
            
            # Calculate occupancy-adjusted consumption
            occupancy_adjusted = sum(
                r.consumption / r.occupancy_factor for r in recent_readings 
                if r.occupancy_factor > 0
            )
            metrics['occupancy_adjusted_consumption'] = occupancy_adjusted / days if days > 0 else 0
        
        return metrics
