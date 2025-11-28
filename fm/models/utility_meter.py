# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)


class UtilityMeter(models.Model):
    _name = 'facilities.utility.meter'
    _description = 'Utility Meter'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # Standard Odoo fields
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company, 
                                tracking=True, index=True)

    # Basic Information
    name = fields.Char(string='Meter Name', required=True, tracking=True)
    meter_code = fields.Char(string='Meter Code', required=True, copy=False, 
                           readonly=True, default='New', tracking=True)
    meter_type = fields.Selection([
        ('electricity', 'Electricity'),
        ('water', 'Water'),
        ('gas', 'Gas'),
        ('steam', 'Steam'),
        ('cooling', 'Cooling'),
        ('heating', 'Heating'),
        ('other', 'Other')
    ], string='Meter Type', required=True, tracking=True)
    
    # Location Information
    facility_id = fields.Many2one('facilities.facility', string='Facility', 
                                 required=True, tracking=True, ondelete='restrict')
    building_id = fields.Many2one('facilities.building', string='Building', 
                                 tracking=True, ondelete='set null')
    floor_id = fields.Many2one('facilities.floor', string='Floor', 
                              tracking=True, ondelete='set null')
    room_id = fields.Many2one('facilities.room', string='Room', 
                             tracking=True, ondelete='set null')
    
    # Asset Integration
    asset_id = fields.Many2one('facilities.asset', string='Associated Asset', 
                              tracking=True, ondelete='set null')
    
    # Technical Specifications
    manufacturer = fields.Char(string='Manufacturer', tracking=True)
    model = fields.Char(string='Model', tracking=True)
    serial_number = fields.Char(string='Serial Number', tracking=True)
    installation_date = fields.Date(string='Installation Date', tracking=True)
    calibration_date = fields.Date(string='Last Calibration Date', tracking=True)
    next_calibration_date = fields.Date(string='Next Calibration Date', tracking=True)
    
    # Meter Configuration
    unit_of_measure = fields.Selection([
        ('kwh', 'kWh (Kilowatt-hour)'),
        ('mwh', 'MWh (Megawatt-hour)'),
        ('cubic_meter', 'm³ (Cubic Meter)'),
        ('liter', 'L (Liter)'),
        ('gallon', 'Gallon'),
        ('btu', 'BTU (British Thermal Unit)'),
        ('therm', 'Therm'),
        ('ton_hour', 'Ton-hour'),
        ('other', 'Other')
    ], string='Unit of Measure', required=True, tracking=True)
    
    custom_unit = fields.Char(string='Custom Unit', tracking=True)
    reading_precision = fields.Integer(string='Reading Precision', default=2, 
                                     help="Number of decimal places for readings")
    
    # Meter Status
    state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
        ('calibration', 'Calibration Required'),
        ('faulty', 'Faulty')
    ], string='Status', default='active', tracking=True, required=True)
    
    is_automatic = fields.Boolean(string='Automatic Reading', default=False, 
                                 help="Meter supports automatic readings")
    reading_frequency = fields.Selection([
        ('manual', 'Manual'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly')
    ], string='Reading Frequency', default='manual', tracking=True)
    
    # Reading Information
    current_reading = fields.Float(string='Current Reading', digits=(16, 2), tracking=True)
    last_reading_date = fields.Datetime(string='Last Reading Date', tracking=True)
    last_reading_user_id = fields.Many2one('res.users', string='Last Reading User', 
                                          tracking=True)
    
    # Energy Consumption Tracking
    consumption_reading_ids = fields.One2many('facilities.energy.consumption', 
                                            'meter_id', string='Consumption Readings')
    total_consumption = fields.Float(string='Total Consumption', digits=(16, 2), 
                                   compute='_compute_total_consumption', store=True)
    
    # Cost Tracking
    cost_per_unit = fields.Float(string='Cost per Unit', digits=(16, 4), tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    estimated_monthly_cost = fields.Float(string='Estimated Monthly Cost', 
                                        digits=(16, 2), compute='_compute_estimated_cost')
    
    # Thresholds and Alerts
    high_consumption_threshold = fields.Float(string='High Consumption Threshold', 
                                            digits=(16, 2), tracking=True)
    low_consumption_threshold = fields.Float(string='Low Consumption Threshold', 
                                           digits=(16, 2), tracking=True)
    alert_active = fields.Boolean(string='Alerts Active', default=True, tracking=True)
    
    # Notes and Documentation
    notes = fields.Text(string='Notes', tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    
    # Mail fields for chatter
    message_ids = fields.One2many('mail.message', 'res_id', string='Messages')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('meter_code', 'New') == 'New':
                vals['meter_code'] = self.env['ir.sequence'].next_by_code('facilities.utility.meter') or 'New'
        return super(UtilityMeter, self).create(vals_list)

    @api.depends('consumption_reading_ids.consumption')
    def _compute_total_consumption(self):
        for meter in self:
            meter.total_consumption = sum(meter.consumption_reading_ids.mapped('consumption'))

    @api.depends('total_consumption', 'cost_per_unit')
    def _compute_estimated_cost(self):
        for meter in self:
            if meter.cost_per_unit and meter.total_consumption:
                meter.estimated_monthly_cost = meter.total_consumption * meter.cost_per_unit
            else:
                meter.estimated_monthly_cost = 0.0

    @api.onchange('facility_id')
    def _onchange_facility_id(self):
        if self.facility_id:
            self.building_id = False
            self.floor_id = False
            self.room_id = False

    @api.onchange('building_id')
    def _onchange_building_id(self):
        if self.building_id:
            self.floor_id = False
            self.room_id = False

    @api.onchange('floor_id')
    def _onchange_floor_id(self):
        if self.floor_id:
            self.room_id = False

    @api.onchange('meter_type')
    def _onchange_meter_type(self):
        if self.meter_type:
            # Set default unit based on meter type
            unit_mapping = {
                'electricity': 'kwh',
                'water': 'cubic_meter',
                'gas': 'cubic_meter',
                'steam': 'ton_hour',
                'cooling': 'ton_hour',
                'heating': 'btu',
                'other': 'other'
            }
            self.unit_of_measure = unit_mapping.get(self.meter_type, 'other')

    @api.constrains('high_consumption_threshold', 'low_consumption_threshold')
    def _check_thresholds(self):
        for meter in self:
            if (meter.high_consumption_threshold and meter.low_consumption_threshold and 
                meter.high_consumption_threshold <= meter.low_consumption_threshold):
                raise ValidationError(_("High consumption threshold must be greater than low consumption threshold."))

    def action_activate(self):
        for meter in self:
            if meter.state == 'inactive':
                meter.state = 'active'

    def action_deactivate(self):
        for meter in self:
            if meter.state == 'active':
                meter.state = 'inactive'

    def action_maintenance(self):
        for meter in self:
            meter.state = 'maintenance'

    def action_calibration_required(self):
        for meter in self:
            meter.state = 'calibration'

    def action_faulty(self):
        for meter in self:
            meter.state = 'faulty'

    def get_location_display(self):
        """Get a formatted string of the meter location"""
        location_parts = []
        if self.room_id:
            location_parts.append(self.room_id.name)
        if self.floor_id:
            location_parts.append(f"Floor {self.floor_id.name}")
        if self.building_id:
            location_parts.append(self.building_id.name)
        if self.facility_id:
            location_parts.append(self.facility_id.name)
        return " > ".join(location_parts) if location_parts else ""

    def get_consumption_summary(self, period='month'):
        """Get consumption summary for a given period"""
        today = fields.Date.today()
        if period == 'month':
            start_date = today.replace(day=1)
        elif period == 'week':
            start_date = today - timedelta(days=today.weekday())
        elif period == 'year':
            start_date = today.replace(month=1, day=1)
        else:
            start_date = today - timedelta(days=30)
        
        readings = self.consumption_reading_ids.filtered(
            lambda r: r.reading_date >= start_date and r.reading_date <= today
        )
        
        return {
            'period': period,
            'start_date': start_date,
            'end_date': today,
            'total_consumption': sum(readings.mapped('consumption')),
            'average_daily': sum(readings.mapped('consumption')) / max(len(readings), 1),
            'readings_count': len(readings),
            'estimated_cost': sum(readings.mapped('consumption')) * (self.cost_per_unit or 0)
        }

    def action_view_consumption_readings(self):
        """Action to view consumption readings for this meter"""
        self.ensure_one()
        return {
            'name': _('Consumption Readings'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.energy.consumption',
            'view_mode': 'list,form',
            'domain': [('meter_id', '=', self.id)],
            'context': {
                'default_meter_id': self.id,
                'default_facility_id': self.facility_id.id,
                'default_building_id': self.building_id.id,
                'default_floor_id': self.floor_id.id,
                'default_room_id': self.room_id.id,
            },
        }

    def action_view_asset(self):
        """Action to view the associated asset"""
        self.ensure_one()
        if not self.asset_id:
            return False
        return {
            'name': _('Asset'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.asset',
            'view_mode': 'form',
            'res_id': self.asset_id.id,
            'context': {
                'default_facility_id': self.facility_id.id,
                'default_building_id': self.building_id.id,
                'default_floor_id': self.floor_id.id,
                'default_room_id': self.room_id.id,
            },
        }
