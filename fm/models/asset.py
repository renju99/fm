from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64
import io
import logging
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)

try:
    import qrcode
except ImportError:
    qrcode = None

class FacilityAsset(models.Model):
    _name = 'facilities.asset'
    _description = 'Facility Asset'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, asset_code'

    # Standard Odoo fields for multi-company and audit
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company, 
                                tracking=True, index=True)
    # Note: create_date, write_date, create_uid, write_uid are automatically provided by Odoo

    name = fields.Char('Asset Name', required=True, tracking=True)
    asset_tag = fields.Char(string="Asset Tag", tracking=True)
    serial_number = fields.Char(string="Serial Number", tracking=True)
    location = fields.Char(string="Location", compute='_compute_location')
    facility_id = fields.Many2one('facilities.facility', string='Project', required=True, tracking=True, ondelete='restrict')
    asset_code = fields.Char('Asset Code', size=20, tracking=True, copy=False)

    # Timeline History Events for UI
    history_events = fields.Json(string="Asset History Events", compute='_compute_history_events', store=False)
    history_events_display = fields.Text(string="Asset History Display", compute='_compute_history_events_display', store=False)
    history_events_html = fields.Html(string="Asset History Timeline", compute='_compute_history_events_html', store=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('maintenance', 'Under Maintenance'),
        ('disposed', 'Disposed'),
    ], string='State', default='draft', tracking=True, required=True)

    def action_activate(self):
        for asset in self:
            if asset.state not in ['draft', 'maintenance']:
                raise ValidationError(_("Asset can only be activated from Draft or Maintenance state. Current state: %s") % asset.state)
            asset.state = 'active'

    def action_set_maintenance(self):
        for asset in self:
            if asset.state != 'active':
                raise ValidationError(_("Asset can only be set to maintenance from Active state. Current state: %s") % asset.state)
            asset.state = 'maintenance'

    def action_set_active(self):
        for asset in self:
            if asset.state not in ['draft', 'maintenance']:
                raise ValidationError(_("Asset can only be set to active from Draft or Maintenance state. Current state: %s") % asset.state)
            asset.state = 'active'

    def action_dispose(self):
        for asset in self:
            if asset.state == 'disposed':
                raise ValidationError(_("Asset is already disposed."))
            # Check for active workorders
            active_workorders = self.env['facilities.workorder'].search([
                ('asset_id', '=', asset.id),
                ('state', 'in', ['assigned', 'in_progress'])
            ])
            if active_workorders:
                raise ValidationError(_("Cannot dispose asset '%s' as it has active work orders. Please complete the work orders first.") % asset.name)
            asset.state = 'disposed'

    def action_create_maintenance_schedule(self):
        """Create a new maintenance schedule for this asset."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Maintenance Schedule',
            'res_model': 'asset.maintenance.schedule',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_id': self.id,
                'default_name': f'Maintenance Schedule - {self.name}',
                'default_maintenance_type': 'preventive',
                'default_interval_number': 1,
                'default_interval_type': 'monthly',
                'default_status': 'planned',
            }
        }

    @api.depends('energy_rating', 'power_consumption_watts', 'annual_energy_consumption')
    def _compute_energy_efficiency_score(self):
        for asset in self:
            score = 0
            if asset.energy_rating:
                # Convert energy rating to numeric score
                rating_scores = {
                    'A+++': 100, 'A++': 95, 'A+': 90, 'A': 85, 'B': 75,
                    'C': 65, 'D': 55, 'E': 45, 'F': 35, 'G': 25, 'unknown': 0
                }
                score += rating_scores.get(asset.energy_rating, 0) * 0.6
            
            # Factor in power consumption efficiency
            if asset.power_consumption_watts and asset.annual_energy_consumption:
                # Lower consumption per watt is better
                efficiency_ratio = asset.annual_energy_consumption / max(asset.power_consumption_watts, 1)
                efficiency_score = max(0, min(40, 40 - (efficiency_ratio / 100)))
                score += efficiency_score
            
            asset.energy_efficiency_score = min(score, 100)

    @api.depends('utility_meter_ids', 'energy_cost_per_hour')
    def _compute_monthly_energy_cost(self):
        for asset in self:
            if asset.primary_meter_id:
                # Get consumption readings from the last month
                last_month = fields.Datetime.now() - timedelta(days=30)
                readings = self.env['facilities.energy.consumption'].search([
                    ('meter_id', '=', asset.primary_meter_id.id),
                    ('reading_date', '>=', last_month),
                    ('is_validated', '=', True)
                ])
                asset.monthly_energy_cost = sum(readings.mapped('total_cost'))
            elif asset.energy_cost_per_hour:
                # Estimate based on hourly cost (assuming 24/7 operation)
                asset.monthly_energy_cost = asset.energy_cost_per_hour * 24 * 30
            else:
                asset.monthly_energy_cost = 0.0

    @api.depends('utility_meter_ids')
    def _compute_energy_trend(self):
        for asset in self:
            if not asset.primary_meter_id:
                asset.energy_consumption_trend = 'unknown'
                continue
            
            # Get consumption data for the last 3 months
            three_months_ago = fields.Datetime.now() - timedelta(days=90)
            recent_readings = self.env['facilities.energy.consumption'].search([
                ('meter_id', '=', asset.primary_meter_id.id),
                ('reading_date', '>=', three_months_ago),
                ('is_validated', '=', True)
            ], order='reading_date')
            
            if len(recent_readings) < 2:
                asset.energy_consumption_trend = 'unknown'
                continue
            
            # Calculate trend by comparing first and last month
            first_month_readings = recent_readings[:len(recent_readings)//3]
            last_month_readings = recent_readings[-len(recent_readings)//3:]
            
            first_month_avg = sum(first_month_readings.mapped('consumption')) / max(len(first_month_readings), 1)
            last_month_avg = sum(last_month_readings.mapped('consumption')) / max(len(last_month_readings), 1)
            
            if first_month_avg > 0:
                change_percentage = ((last_month_avg - first_month_avg) / first_month_avg) * 100
                if change_percentage < -5:
                    asset.energy_consumption_trend = 'improving'
                elif change_percentage > 5:
                    asset.energy_consumption_trend = 'declining'
                else:
                    asset.energy_consumption_trend = 'stable'
            else:
                asset.energy_consumption_trend = 'unknown'

    def action_view_energy_consumption(self):
        """View energy consumption data for this asset"""
        self.ensure_one()
        domain = []
        if self.primary_meter_id:
            domain = [('meter_id', '=', self.primary_meter_id.id)]
        elif self.utility_meter_ids:
            domain = [('meter_id', 'in', self.utility_meter_ids.ids)]
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Energy Consumption - {self.name}',
            'res_model': 'facilities.energy.consumption',
            'view_mode': 'list,form,graph,calendar',
            'domain': domain,
            'context': {
                'search_default_group_by_meter_id': 1,
                'search_default_group_by_reading_date': 1,
            }
        }

    def action_view_utility_meters(self):
        """View utility meters associated with this asset"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Utility Meters - {self.name}',
            'res_model': 'facilities.utility.meter',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
        }

    # Relationships
    maintenance_ids = fields.One2many('asset.maintenance.schedule', 'asset_id', string='Maintenance Schedules')
    depreciation_ids = fields.One2many('facilities.asset.depreciation', 'asset_id', string='Depreciation Records')
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Documents',
        domain="[('res_model','=','facilities.asset')]"
    )
    category_id = fields.Many2one('facilities.asset.category', string='Category', tracking=True)
    
    # Energy Management Integration
    is_energy_consuming = fields.Boolean(string='Energy Consuming Asset', default=False, tracking=True,
                                       help="Mark if this asset consumes energy and should be tracked")
    energy_rating = fields.Selection([
        ('A+++', 'A+++ (Most Efficient)'),
        ('A++', 'A++'),
        ('A+', 'A+'),
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('E', 'E'),
        ('F', 'F'),
        ('G', 'G (Least Efficient)'),
        ('unknown', 'Unknown')
    ], string='Energy Rating', tracking=True)
    
    power_consumption_watts = fields.Float(string='Power Consumption (Watts)', digits=(16, 2), tracking=True)
    annual_energy_consumption = fields.Float(string='Annual Energy Consumption (kWh)', digits=(16, 2), tracking=True)
    energy_cost_per_hour = fields.Float(string='Energy Cost per Hour', digits=(16, 4), tracking=True)
    
    # Utility Meter Integration
    utility_meter_ids = fields.One2many('facilities.utility.meter', 'asset_id', string='Associated Meters')
    primary_meter_id = fields.Many2one('facilities.utility.meter', string='Primary Meter', 
                                      domain="[('asset_id', '=', id)]", tracking=True)
    
    # Energy Performance Metrics
    energy_efficiency_score = fields.Float(string='Energy Efficiency Score', digits=(16, 2), 
                                         compute='_compute_energy_efficiency_score', store=True)
    monthly_energy_cost = fields.Float(string='Monthly Energy Cost', digits=(16, 2), 
                                     compute='_compute_monthly_energy_cost', store=True)
    energy_consumption_trend = fields.Selection([
        ('improving', 'Improving'),
        ('stable', 'Stable'),
        ('declining', 'Declining'),
        ('unknown', 'Unknown')
    ], string='Energy Consumption Trend', compute='_compute_energy_trend', store=True)

    # Dates - using consistent naming pattern: {event}_date
    purchased_date = fields.Date('Purchase Date', tracking=True, help="Date when the asset was purchased")
    installed_date = fields.Date(string='Installation Date', tracking=True, help="Date when the asset was installed")
    warranty_expires_date = fields.Date('Warranty Expiration Date', tracking=True, help="Date when warranty expires")

    # Physical Properties
    condition = fields.Selection(
        [
            ('new', 'New'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('poor', 'Poor'),
        ],
        default='good',
        string='Condition',
        tracking=True
    )

    # Location Hierarchy Fields
    room_id = fields.Many2one(
        'facilities.room', string='Room',
        tracking=True
    )
    building_id = fields.Many2one(
        'facilities.building', string='Building',
        compute='_compute_building_floor',
        store=True,
        readonly=False
    )
    floor_id = fields.Many2one(
        'facilities.floor', string='Floor',
        compute='_compute_building_floor',
        store=True,
        readonly=False
    )

    @api.depends('room_id')
    def _compute_building_floor(self):
        for asset in self:
            asset.building_id = asset.room_id.building_id if asset.room_id and asset.room_id.building_id else False
            asset.floor_id = asset.room_id.floor_id if asset.room_id and asset.room_id.floor_id else False

    # People & Organization
    responsible_id = fields.Many2one('res.users', string='Responsible Person', tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', tracking=True)
    manufacturer_id = fields.Many2one('res.partner', string='Manufacturer', tracking=True)
    service_provider_id = fields.Many2one('res.partner', string='Service Provider', tracking=True)

    # Financial
    purchase_cost = fields.Monetary(string='Purchase Cost', currency_field='currency_id', tracking=True, help="Total purchase cost including taxes, shipping, and all associated expenses")
    current_value = fields.Monetary(string='Current Value', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    # Technical Details
    model_number = fields.Char(string='Model Number', tracking=True)
    expected_lifespan = fields.Integer(string='Expected Lifespan (Years)', tracking=True)

    # Enhanced Asset Management Fields
    criticality = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Business Criticality', default='medium', tracking=True,
       help="How critical this asset is to business operations")
    
    energy_rating = fields.Selection([
        ('a', 'A - Excellent'),
        ('b', 'B - Good'),
        ('c', 'C - Average'),
        ('d', 'D - Below Average'),
        ('e', 'E - Poor')
    ], string='Energy Efficiency Rating', tracking=True)
    
    environmental_impact = fields.Selection([
        ('low', 'Low Impact'),
        ('medium', 'Medium Impact'),
        ('high', 'High Impact')
    ], string='Environmental Impact', default='low', tracking=True)
    
    
    last_inspected_date = fields.Date(string='Last Inspection Date', tracking=True, help="Date of last inspection")
    next_inspection_date = fields.Date(string='Next Inspection Date', tracking=True, help="Date of next scheduled inspection")
    
    # Real-time Condition Monitoring
    temperature = fields.Float(string='Current Temperature (°C)', help="Real-time temperature reading")
    humidity = fields.Float(string='Current Humidity (%)', help="Real-time humidity reading")
    vibration = fields.Float(string='Vibration Level', help="Real-time vibration measurement")
    pressure = fields.Float(string='Pressure Reading', help="Real-time pressure measurement")
    power_consumption = fields.Float(string='Power Consumption (kW)', help="Real-time power consumption")
    runtime_hours = fields.Float(string='Runtime Hours', help="Total runtime hours")
    
    # NEW: Condition-based Triggers
    condition_thresholds = fields.One2many('facilities.asset.threshold', 'asset_id', string='Condition Thresholds')
    alert_enabled = fields.Boolean(string='Enable Alerts', default=True, help="Enable real-time alerts for this asset")
    critical_condition = fields.Boolean(string='Critical Condition', compute='_compute_critical_condition', store=True)
    
    # NEW: Enhanced Barcode & RFID Integration
    barcode = fields.Char('Barcode', copy=False, index=True, tracking=True)
    rfid_tag = fields.Char(string='RFID Tag ID', help="RFID tag identifier for asset tracking")
    qr_code = fields.Char(string='QR Code', help="QR code for mobile scanning")
    nfc_tag = fields.Char(string='NFC Tag ID', help="NFC tag identifier")
    
    # NEW: Mobile Asset Tracking
    last_scan_location = fields.Char(string='Last Scan Location', help="Location where asset was last scanned")
    last_scan_time = fields.Datetime(string='Last Scan Time', help="Timestamp of last mobile scan")
    scanned_by_id = fields.Many2one('res.users', string='Scanned By', help="User who last scanned the asset")
    
    # NEW: Asset Lifecycle Automation
    auto_dispose_on_zero_value = fields.Boolean(string='Auto-dispose on Zero Value', default=False,
                                              help="Automatically dispose asset when depreciation reaches zero")
    disposal_workflow_state = fields.Selection([
        ('none', 'No Disposal'),
        ('pending', 'Disposal Pending'),
        ('approved', 'Disposal Approved'),
        ('in_progress', 'Disposal In Progress'),
        ('completed', 'Disposal Completed')
    ], string='Disposal Workflow State', default='none', tracking=True)
    
    ml_model_id = fields.Char(string='ML Model ID', help="Machine learning model identifier for this asset")
    prediction_confidence = fields.Float(string='Prediction Confidence (%)', help="Confidence level of failure prediction")
    next_failure_prediction = fields.Datetime(string='Predicted Next Failure', help="ML-predicted next failure date")
    
    # NEW: Asset Health Scoring
    health_score = fields.Float(string='Asset Health Score', compute='_compute_health_score', store=True)
    health_trend = fields.Selection([
        ('improving', 'Improving'),
        ('stable', 'Stable'),
        ('declining', 'Declining'),
        ('critical', 'Critical')
    ], string='Health Trend', compute='_compute_health_trend', store=True)
    
    # Asset Location Enhancement
    gps_coordinates = fields.Char(string='GPS Coordinates', help="Latitude,Longitude format")
    floor_plan_location = fields.Char(string='Floor Plan Location', help="X,Y coordinates on floor plan")
    
    # Financial Enhancement
    insurance_value = fields.Monetary(string='Insurance Value', currency_field='currency_id', tracking=True)
    replacement_cost = fields.Monetary(string='Replacement Cost', currency_field='currency_id', tracking=True)
    annual_operating_cost = fields.Monetary(string='Annual Operating Cost', currency_field='currency_id')
    
    # Usage and Performance
    operating_hours_total = fields.Float(string='Total Operating Hours', default=0.0)
    operating_hours_yearly = fields.Float(string='Operating Hours This Year', default=0.0)
    utilization_target = fields.Float(string='Target Utilization (%)', default=80.0)
    actual_utilization = fields.Float(string='Actual Utilization (%)', compute='_compute_utilization')
    
    # Asset Lifecycle Enhancement
    installation_status = fields.Selection([
        ('not_installed', 'Not Installed'),
        ('in_progress', 'Installation In Progress'),
        ('installed', 'Installed'),
        ('commissioned', 'Commissioned'),
        ('decommissioned', 'Decommissioned')
    ], string='Installation Status', default='not_installed', tracking=True)
    
    commissioned_date = fields.Date(string='Commissioning Date', tracking=True, help="Date when asset was commissioned")
    decommissioned_date = fields.Date(string='Decommissioning Date', tracking=True, help="Date when asset was decommissioned")

    # Media & Documentation
    image_1920 = fields.Image("Image")
    notes = fields.Html('Notes')
    active = fields.Boolean('Active', default=True)

    # Barcode System  
    barcode_image = fields.Image(
        "QR Code Image",
        compute='_compute_barcode_image',
        store=True,
        attachment=True,
        max_width=256,
        max_height=256
    )

    warranty_status = fields.Selection(
        [
            ('valid', 'Valid'),
            ('expired', 'Expired'),
            ('none', 'No Warranty')
        ],
        string='Warranty Status',
        compute='_compute_warranty_status',
        store=True,
        tracking=True
    )


    is_enterprise = fields.Boolean(
        string="Enterprise Mode",
        compute='_compute_is_enterprise',
        help="Technical field to check if enterprise features are available"
    )

    # Additional missing fields for comprehensive asset management
    supplier_id = fields.Many2one('res.partner', string='Supplier', tracking=True, 
                                 help="Original supplier/vendor of the asset")
    supplier_reference = fields.Char(string='Supplier Reference', tracking=True,
                                   help="Reference number from supplier")
    internal_reference = fields.Char(string='Internal Reference', tracking=True,
                                   help="Internal reference number for the asset")
    
    # Asset Specifications
    specifications = fields.Html(string='Technical Specifications', 
                               help="Detailed technical specifications of the asset")
    operating_manual_url = fields.Char(string='Operating Manual URL', 
                                     help="Link to operating manual or documentation")
    maintenance_manual_url = fields.Char(string='Maintenance Manual URL', 
                                       help="Link to maintenance manual or documentation")
    
    # Regulatory Information
    regulatory_requirements = fields.Text(string='Regulatory Requirements', 
                                        help="Regulatory requirements that apply to this asset")
    certification_expiry = fields.Date(string='Certification Expiry Date', 
                                     help="Date when asset certification expires")
    inspection_required = fields.Boolean(string='Inspection Required', default=False,
                                        help="Whether regular inspections are required for this asset")
    
    # Asset Performance Metrics
    uptime_percentage = fields.Float(string='Uptime Percentage (%)', default=100.0,
                                    help="Percentage of time asset is operational")
    efficiency_rating = fields.Float(string='Efficiency Rating (%)', default=100.0,
                                   help="Operational efficiency rating of the asset")
    last_performance_review = fields.Date(string='Last Performance Review', 
                                        help="Date of last performance review")
    
    # Cost Tracking
    total_maintenance_cost = fields.Monetary(string='Total Maintenance Cost', 
                                           currency_field='currency_id', tracking=True,
                                           help="Total cost of all maintenance activities")
    total_operating_cost = fields.Monetary(string='Total Operating Cost', 
                                         currency_field='currency_id', tracking=True,
                                         help="Total operating cost over asset lifetime")
    salvage_value = fields.Monetary(string='Salvage Value', 
                                  currency_field='currency_id', tracking=True,
                                  help="Estimated value at end of useful life")
    
    # Asset Relationships
    parent_asset_id = fields.Many2one('facilities.asset', string='Parent Asset', 
                                     help="Parent asset if this is a component")
    child_asset_ids = fields.One2many('facilities.asset', 'parent_asset_id', string='Child Assets',
                                     help="Component assets that are part of this asset")
    related_asset_ids = fields.Many2many('facilities.asset', 'asset_related_rel', 
                                        'asset_id', 'related_asset_id', string='Related Assets',
                                        help="Assets that are functionally related to this one")
    
    # Additional useful fields for comprehensive asset management
    asset_status = fields.Selection([
        ('operational', 'Operational'),
        ('standby', 'Standby'),
        ('out_of_service', 'Out of Service'),
        ('retired', 'Retired'),
        ('spare', 'Spare'),
        ('in_transit', 'In Transit'),
        ('under_repair', 'Under Repair'),
        ('quarantined', 'Quarantined')
    ], string='Asset Status', default='operational', tracking=True,
       help="Current operational status of the asset")
    
    priority_level = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
        ('critical', 'Critical')
    ], string='Priority Level', default='normal', tracking=True,
       help="Priority level for maintenance and attention")
    
    # Asset Classification
    asset_type = fields.Selection([
        ('equipment', 'Equipment'),
        ('machinery', 'Machinery'),
        ('vehicle', 'Vehicle'),
        ('building', 'Building'),
        ('furniture', 'Furniture'),
        ('it_hardware', 'IT Hardware'),
        ('tool', 'Tool'),
        ('instrument', 'Instrument'),
        ('other', 'Other')
    ], string='Asset Type', default='equipment', tracking=True)
    
    # Maintenance Planning
    preventive_maintenance_enabled = fields.Boolean(string='Preventive Maintenance Enabled', default=True,
                                                  help="Enable preventive maintenance scheduling")
    maintenance_priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Maintenance Priority', default='normal', tracking=True)
    
    # Asset Documentation
    asset_manual = fields.Binary(string='Asset Manual', attachment=True,
                                help="Upload asset manual or documentation")
    asset_manual_filename = fields.Char(string='Asset Manual Filename')
    safety_instructions = fields.Html(string='Safety Instructions',
                                     help="Safety instructions for operating this asset")
    emergency_procedures = fields.Html(string='Emergency Procedures',
                                     help="Emergency procedures for this asset")
    
    # Asset History and Tracking
    last_activity = fields.Datetime(string='Last Activity', 
                                   help="Timestamp of last activity on this asset")
    activity_count = fields.Integer(string='Activity Count', default=0,
                                   help="Total number of activities performed on this asset")
    last_maintenance_by = fields.Many2one('res.users', string='Last Maintained By',
                                         help="User who performed the last maintenance")
    last_maintenance_date = fields.Date(string='Last Maintenance Date',
                                       help="Date of last maintenance performed")
    
    # Asset Performance Indicators
    reliability_score = fields.Float(string='Reliability Score (%)', default=100.0,
                                   help="Asset reliability percentage")
    availability_score = fields.Float(string='Availability Score (%)', default=100.0,
                                    help="Asset availability percentage")
    performance_score = fields.Float(string='Performance Score (%)', default=100.0,
                                   help="Overall performance score")
    
    # Asset Lifecycle Management
    lifecycle_stage = fields.Selection([
        ('planning', 'Planning'),
        ('acquisition', 'Acquisition'),
        ('installation', 'Installation'),
        ('operation', 'Operation'),
        ('maintenance', 'Maintenance'),
        ('upgrade', 'Upgrade'),
        ('disposal', 'Disposal')
    ], string='Lifecycle Stage', default='operation', tracking=True)
    
    # Asset Risk Management
    risk_level = fields.Selection([
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk')
    ], string='Risk Level', compute='_compute_risk_level', store=True)
    
    
    # Asset Cost Center
    cost_center = fields.Char(string='Cost Center',
                             help="Cost center for tracking asset expenses")
    
    # Asset Tags and Labels
    asset_tags = fields.Many2many('facilities.asset.tag', string='Asset Tags',
                                 help="Custom tags for categorizing assets")
    custom_fields = fields.Json(string='Custom Fields',
                               help="Flexible custom fields for asset-specific data")
    
    # Additional useful fields for comprehensive asset management
    # Asset Dimensions and Specifications
    dimensions = fields.Char(string='Dimensions', help="Physical dimensions (L x W x H)")
    weight = fields.Float(string='Weight (kg)', help="Weight of the asset in kilograms")
    power_rating = fields.Char(string='Power Rating', help="Power rating (e.g., 100kW, 220V)")
    capacity = fields.Char(string='Capacity', help="Operating capacity of the asset")
    
    # Asset Location Details
    exact_location = fields.Char(string='Exact Location', help="Specific location description")
    location_notes = fields.Text(string='Location Notes', help="Additional location information")
    
    # Asset Maintenance Information
    maintenance_contact = fields.Char(string='Maintenance Contact', 
                                    help="Contact person for maintenance issues")
    maintenance_phone = fields.Char(string='Maintenance Phone', 
                                  help="Phone number for maintenance contact")
    maintenance_email = fields.Char(string='Maintenance Email', 
                                   help="Email for maintenance contact")
    
    # Asset Financial Information
    depreciation_method = fields.Selection([
        ('straight_line', 'Straight Line'),
        ('declining_balance', 'Declining Balance'),
        ('sum_of_years', 'Sum of Years'),
        ('units_of_production', 'Units of Production'),
        ('none', 'No Depreciation')
    ], string='Depreciation Method', default='straight_line', tracking=True)
    
    depreciation_rate = fields.Float(string='Depreciation Rate (%)', 
                                   help="Annual depreciation rate percentage")
    
    # Asset Security and Access
    access_level = fields.Selection([
        ('public', 'Public'),
        ('restricted', 'Restricted'),
        ('confidential', 'Confidential'),
        ('secret', 'Secret')
    ], string='Access Level', default='restricted', tracking=True)
    
    security_clearance = fields.Char(string='Security Clearance Required', 
                                   help="Required security clearance level")
    
    # Asset Environmental Information
    environmental_rating = fields.Selection([
        ('a', 'A - Excellent'),
        ('b', 'B - Good'),
        ('c', 'C - Average'),
        ('d', 'D - Below Average'),
        ('e', 'E - Poor')
    ], string='Environmental Rating', tracking=True)
    
    carbon_footprint = fields.Float(string='Carbon Footprint (kg CO2)', 
                                  help="Estimated carbon footprint of the asset")
    
    # Asset Integration and Connectivity
    integration_capabilities = fields.Text(string='Integration Capabilities', 
                                         help="Description of integration capabilities")
    api_endpoints = fields.Text(string='API Endpoints', 
                               help="Available API endpoints for integration")
    data_format = fields.Char(string='Data Format', 
                             help="Format of data exported by the asset")
    
    # Asset Backup and Recovery
    backup_required = fields.Boolean(string='Backup Required', default=False,
                                   help="Whether backup procedures are required")
    backup_frequency = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually')
    ], string='Backup Frequency', default='weekly')
    
    recovery_time_objective = fields.Float(string='Recovery Time Objective (hours)', 
                                         help="Target time to restore asset functionality")
    
    # Asset Training and Documentation
    training_required = fields.Boolean(string='Training Required', default=False,
                                     help="Whether operator training is required")
    training_duration = fields.Float(string='Training Duration (hours)', 
                                   help="Duration of required training")
    certification_required = fields.Boolean(string='Certification Required', default=False,
                                          help="Whether operator certification is required")
    
    # Asset Disposal Information
    disposal_method = fields.Selection([
        ('sell', 'Sell'),
        ('donate', 'Donate'),
        ('recycle', 'Recycle'),
        ('scrap', 'Scrap'),
        ('return_to_supplier', 'Return to Supplier'),
        ('other', 'Other')
    ], string='Disposal Method', tracking=True)
    
    disposal_notes = fields.Text(string='Disposal Notes', 
                                help="Notes about disposal requirements or procedures")
    
    # Asset Insurance and Liability
    insurance_policy_number = fields.Char(string='Insurance Policy Number', 
                                        help="Insurance policy number for the asset")
    insurance_expiry_date = fields.Date(string='Insurance Expiry Date', 
                                      help="Date when insurance expires")
    insurance_status = fields.Selection([
        ('valid', 'Valid'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('no_insurance', 'No Insurance')
    ], string='Insurance Status', compute='_compute_insurance_status', store=True)
    liability_coverage = fields.Monetary(string='Liability Coverage', 
                                       currency_field='currency_id',
                                       help="Liability coverage amount")
    
    # Asset Performance Benchmarks
    performance_benchmark = fields.Float(string='Performance Benchmark', 
                                       help="Target performance metric for the asset")
    benchmark_unit = fields.Char(string='Benchmark Unit', 
                                help="Unit of measurement for the benchmark")
    benchmark_source = fields.Char(string='Benchmark Source', 
                                  help="Source of the performance benchmark")

    @api.depends('warranty_expires_date')
    def _compute_warranty_status(self):
        today = fields.Date.today()
        for asset in self:
            if not asset.warranty_expires_date:
                asset.warranty_status = 'none'
            elif asset.warranty_expires_date >= today:
                asset.warranty_status = 'valid'
            else:
                asset.warranty_status = 'expired'


    def create_default_maintenance_schedule(self):
        """Create a default preventive maintenance schedule for assets that don't have one."""
        for asset in self:
            if not asset.maintenance_ids.filtered(lambda m: m.maintenance_type == 'preventive' and m.active):
                # Create a default monthly preventive maintenance schedule
                self.env['asset.maintenance.schedule'].create({
                    'name': f'Monthly Preventive - {asset.name}',
                    'asset_id': asset.id,
                    'maintenance_type': 'preventive',
                    'interval_number': 1,
                    'interval_type': 'monthly',
                    'status': 'planned',
                    'active': True,
                })
                asset.message_post(
                    body="Default monthly preventive maintenance schedule created automatically."
                )


    @api.model
    def create_bulk_maintenance_schedules(self, maintenance_type='preventive', interval_number=1, interval_type='monthly'):
        """Create maintenance schedules in bulk for assets that don't have them."""
        assets_without_schedules = self.search([
            ('active', '=', True),
            ('state', 'in', ['active', 'draft'])
        ]).filtered(lambda a: not a.maintenance_ids.filtered(lambda m: m.maintenance_type == maintenance_type and m.active))
        
        created_count = 0
        for asset in assets_without_schedules:
            try:
                self.env['asset.maintenance.schedule'].create({
                    'name': f'{interval_type.title()} {maintenance_type.title()} - {asset.name}',
                    'asset_id': asset.id,
                    'maintenance_type': maintenance_type,
                    'interval_number': interval_number,
                    'interval_type': interval_type,
                    'status': 'planned',
                    'active': True,
                })
                created_count += 1
            except Exception as e:
                _logger.error(f"Failed to create maintenance schedule for asset {asset.name}: {str(e)}")
        
        _logger.info(f"Created {created_count} maintenance schedules for assets")
        return created_count

    def _compute_is_enterprise(self):
        enterprise_installed = self.env['ir.module.module'].search_count([
            ('name', '=', 'web_enterprise'),
            ('state', '=', 'installed')
        ])
        for asset in self:
            asset.is_enterprise = enterprise_installed

    @api.depends('barcode')
    def _compute_barcode_image(self):
        for asset in self:
            if asset.barcode and qrcode:
                try:
                    qr = qrcode.QRCode(version=1, box_size=4, border=1)
                    qr.add_data(asset.barcode)
                    qr.make(fit=True)
                    img = qr.make_image()

                    buffered = io.BytesIO()
                    img.save(buffered, format="PNG")
                    img_str = base64.b64encode(buffered.getvalue())
                    asset.barcode_image = img_str
                except Exception:
                    asset.barcode_image = False
            else:
                asset.barcode_image = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('asset_code'):
                vals['asset_code'] = self.env['ir.sequence'].next_by_code('facilities.asset') or 'AS0000'
            if not vals.get('barcode'):
                vals['barcode'] = self.env['ir.sequence'].next_by_code('facilities.asset.barcode') or 'AS0000'
        return super().create(vals_list)

    def name_get(self):
        return [(record.id, f"{record.name} [{record.asset_code}]") for record in self]

    def action_open_dashboard(self):
        self.ensure_one()
        if self.is_enterprise:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Asset Dashboard (Enterprise)',
                'res_model': 'facilities.asset',
                'view_mode': 'dashboard',
                'views': [(False, 'dashboard')],
                'target': 'current',
                'context': dict(self.env.context),
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Asset Dashboard (Community)',
                'res_model': 'facilities.asset',
                'view_mode': 'kanban,graph,pivot',
                'views': [(False, 'kanban'), (False, 'graph'), (False, 'pivot')],
                'target': 'current',
                'context': dict(self.env.context),
            }

    @api.depends('maintenance_ids', 'depreciation_ids')
    def _compute_history_events(self):
        for asset in self:
            events = []
            # Maintenance events (EXCLUDE preventive work orders)
            for maint in asset.maintenance_ids:
                # If maintenance schedule links to a workorder, and that workorder is NOT preventive, include it
                if hasattr(maint, 'workorder_ids') and maint.workorder_ids:
                    for workorder in maint.workorder_ids:
                        if getattr(workorder, 'work_order_type', None) != 'preventive' and maint.last_maintenance_date:
                            events.append({
                                'date': str(maint.last_maintenance_date),
                                'type': 'maintenance',
                                'name': maint.name,
                                'notes': maint.notes,
                                'details': f"Type: {maint.maintenance_type} ({workorder.work_order_type})"
                            })
                else:
                    # If no workorder connection, just append (legacy)
                    if getattr(maint, 'maintenance_type', None) != 'preventive' and maint.last_maintenance_date:
                        events.append({
                            'date': str(maint.last_maintenance_date),
                            'type': 'maintenance',
                            'name': maint.name,
                            'notes': maint.notes,
                            'details': f"Type: {maint.maintenance_type}"
                        })
            # Depreciation events
            for dep in asset.depreciation_ids:
                events.append({
                    'date': str(dep.depreciation_date),
                    'type': 'depreciation',
                    'name': 'Depreciation',
                    'notes': f"Amount: {dep.depreciation_amount}",
                    'details': f"Value After: {dep.value_after}"
                })
            # Movement events (Stock Picking)
            pickings = self.env['stock.picking'].search([('workorder_id.asset_id', '=', asset.id)])
            for picking in pickings:
                if picking.scheduled_date:
                    events.append({
                        'date': str(picking.scheduled_date),
                        'type': 'movement',
                        'name': picking.name,
                        'notes': f"Transferred: {picking.origin}",
                        'details': f"State: {picking.state}"
                    })
            asset.history_events = sorted(events, key=lambda e: e['date'], reverse=True)

    @api.depends('history_events')
    def _compute_history_events_html(self):
        for asset in self:
            html = "<div class='o_asset_timeline'>"
            for event in asset.history_events or []:
                color = {
                    "maintenance": "#28a745",
                    "depreciation": "#ffc107",
                    "movement": "#17a2b8"
                }.get(event.get("type"), "#007bff")
                html += f"""
                    <div class="o_timeline_event" style="margin-bottom:1em; padding-left:1.5em; position:relative;">
                        <span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:{color}; position:absolute; left:0; top:0.5em;"></span>
                        <strong>{event.get('date', '')}</strong>
                        <span class="badge" style="background:{color}; color:white; margin-left:0.5em;">{event.get('type', '').capitalize()}</span>
                        <div><b>{event.get('name', '')}</b></div>
                        <div>{event.get('notes', '')}</div>
                        <div style="color:#6c757d; font-size:0.85em;">{event.get('details', '')}</div>
                    </div>
                """
            if not (asset.history_events or []):
                html += "<span>No history yet.</span>"
            html += "</div>"
            asset.history_events_html = html

    @api.depends('room_id', 'floor_id', 'building_id', 'facility_id')
    def _compute_location(self):
        for asset in self:
            location_parts = []
            
            # Build hierarchical location string from most specific to most general
            if asset.room_id:
                location_parts.append(f"Room {asset.room_id.name}")
            if asset.floor_id:
                location_parts.append(f"Floor {asset.floor_id.name}")
            if asset.building_id:
                location_parts.append(f"Building {asset.building_id.name}")
            if asset.facility_id:
                location_parts.append(f"Facility {asset.facility_id.name}")
            
            # Create full hierarchical path
            asset.location = " > ".join(location_parts) if location_parts else "Location not specified"

    @api.depends('operating_hours_yearly', 'utilization_target')
    def _compute_utilization(self):
        for asset in self:
            if asset.utilization_target > 0:
                # Assuming 8760 hours per year (365 * 24)
                max_hours = 8760
                target_hours = (asset.utilization_target / 100) * max_hours
                if target_hours > 0:
                    asset.actual_utilization = min(100, (asset.operating_hours_yearly / target_hours) * 100)
                else:
                    asset.actual_utilization = 0.0
            else:
                asset.actual_utilization = 0.0


    @api.depends('temperature', 'humidity', 'vibration', 'pressure', 'condition_thresholds')
    def _compute_critical_condition(self):
        for asset in self:
            critical = False
            for threshold in asset.condition_thresholds:
                if threshold.is_exceeded:
                    critical = True
                    break
            asset.critical_condition = critical

    @api.depends('condition', 'warranty_status', 'actual_utilization', 'critical_condition')
    def _compute_health_score(self):
        for asset in self:
            score = 100.0
            
            # Condition impact
            condition_scores = {
                'new': 100,
                'good': 85,
                'fair': 60,
                'poor': 30
            }
            score *= condition_scores.get(asset.condition, 50) / 100
            
            
            # Warranty impact
            if asset.warranty_status == 'expired':
                score *= 0.9
            
            # Utilization impact
            if asset.actual_utilization > 95:
                score *= 0.8  # Over-utilization penalty
            
            
            # Critical condition impact
            if asset.critical_condition:
                score *= 0.5
            
            asset.health_score = max(0, min(100, score))

    @api.depends('health_score', 'maintenance_cost_ytd')
    def _compute_health_trend(self):
        for asset in self:
            if asset.health_score >= 80:
                asset.health_trend = 'improving'
            elif asset.health_score >= 60:
                asset.health_trend = 'stable'
            elif asset.health_score >= 40:
                asset.health_trend = 'declining'
            else:
                asset.health_trend = 'critical'

    # Additional computed methods for new fields
    @api.depends('maintenance_ids.cost')
    def _compute_total_maintenance_cost(self):
        """Compute total maintenance cost from all maintenance records"""
        for asset in self:
            total_cost = sum(asset.maintenance_ids.mapped('cost')) if asset.maintenance_ids else 0.0
            asset.total_maintenance_cost = total_cost

    @api.depends('annual_operating_cost', 'purchased_date')
    def _compute_total_operating_cost(self):
        """Compute total operating cost over asset lifetime"""
        for asset in self:
            if asset.purchased_date and asset.annual_operating_cost:
                years_owned = max(1, (fields.Date.today() - asset.purchased_date).days / 365.25)
                asset.total_operating_cost = asset.annual_operating_cost * years_owned
            else:
                asset.total_operating_cost = 0.0

    @api.depends('condition', 'expected_lifespan', 'purchased_date')
    def _compute_salvage_value(self):
        """Compute estimated salvage value based on condition and age"""
        for asset in self:
            if asset.purchased_date and asset.expected_lifespan and asset.purchase_cost:
                years_owned = max(0, (fields.Date.today() - asset.purchased_date).days / 365.25)
                remaining_life = max(0, asset.expected_lifespan - years_owned)
                
                # Condition-based depreciation
                condition_factor = {
                    'new': 0.8,
                    'good': 0.6,
                    'fair': 0.4,
                    'poor': 0.2
                }.get(asset.condition, 0.5)
                
                # Age-based depreciation
                age_factor = max(0.1, remaining_life / asset.expected_lifespan)
                
                asset.salvage_value = asset.purchase_cost * condition_factor * age_factor
            else:
                asset.salvage_value = 0.0

    @api.depends('criticality', 'condition', 'warranty_status', 'asset_status')
    def _compute_risk_level(self):
        """Compute risk level based on multiple factors"""
        for asset in self:
            risk_score = 0
            
            # Criticality weight (0-30 points)
            criticality_scores = {'low': 5, 'medium': 15, 'high': 25, 'critical': 30}
            risk_score += criticality_scores.get(asset.criticality, 15)
            
            # Condition weight (0-25 points)
            condition_scores = {'new': 5, 'good': 10, 'fair': 20, 'poor': 25}
            risk_score += condition_scores.get(asset.condition, 15)
            
            # Asset status weight (0-20 points)
            status_scores = {
                'operational': 5, 'standby': 10, 'out_of_service': 15, 
                'under_repair': 20, 'quarantined': 25
            }
            risk_score += status_scores.get(asset.asset_status, 10)
            
            
            
            # Determine risk level based on total score
            if risk_score <= 20:
                asset.risk_level = 'low'
            elif risk_score <= 40:
                asset.risk_level = 'medium'
            elif risk_score <= 60:
                asset.risk_level = 'high'
            else:
                asset.risk_level = 'critical'

    @api.depends('maintenance_ids', 'maintenance_ids.completion_date')
    def _compute_last_maintenance_info(self):
        """Compute last maintenance information"""
        for asset in self:
            completed_maintenance = asset.maintenance_ids.filtered(
                lambda m: m.completion_date and m.status == 'completed'
            ).sorted('completion_date', reverse=True)
            
            if completed_maintenance:
                asset.last_maintenance_date = completed_maintenance[0].completion_date
                asset.last_maintenance_by = completed_maintenance[0].technician_id
            else:
                asset.last_maintenance_date = False
                asset.last_maintenance_by = False

    @api.depends('maintenance_ids', 'maintenance_ids.start_date')
    def _compute_activity_count(self):
        """Compute total activity count"""
        for asset in self:
            asset.activity_count = len(asset.maintenance_ids)

    @api.depends('maintenance_ids.start_date')
    def _compute_last_activity(self):
        """Compute last activity timestamp"""
        for asset in self:
            if asset.maintenance_ids:
                latest_activity = max(asset.maintenance_ids.mapped('start_date'))
                asset.last_activity = latest_activity
            else:
                asset.last_activity = False

    # Additional computed methods for performance indicators
    @api.depends('maintenance_ids', 'maintenance_ids.status', 'maintenance_ids.completion_date')
    def _compute_reliability_score(self):
        """Compute reliability score based on maintenance history"""
        for asset in self:
            if asset.maintenance_ids:
                total_maintenance = len(asset.maintenance_ids)
                completed_maintenance = len(asset.maintenance_ids.filtered(lambda m: m.status == 'completed'))
                if total_maintenance > 0:
                    asset.reliability_score = (completed_maintenance / total_maintenance) * 100
                else:
                    asset.reliability_score = 100.0
            else:
                asset.reliability_score = 100.0

    @api.depends('maintenance_ids', 'maintenance_ids.status', 'maintenance_ids.duration')
    def _compute_availability_score(self):
        """Compute availability score based on downtime"""
        for asset in self:
            if asset.maintenance_ids:
                total_downtime = sum(asset.maintenance_ids.filtered(
                    lambda m: m.status == 'completed' and m.duration
                ).mapped('duration'))
                # Assuming 8760 hours per year (365 * 24)
                total_hours = 8760
                if total_hours > 0:
                    asset.availability_score = max(0, ((total_hours - total_downtime) / total_hours) * 100)
                else:
                    asset.availability_score = 100.0
            else:
                asset.availability_score = 100.0

    @api.depends('reliability_score', 'availability_score', 'health_score')
    def _compute_performance_score(self):
        """Compute overall performance score"""
        for asset in self:
            scores = [asset.reliability_score, asset.availability_score, asset.health_score]
            valid_scores = [s for s in scores if s is not None and s > 0]
            if valid_scores:
                asset.performance_score = sum(valid_scores) / len(valid_scores)
            else:
                asset.performance_score = 100.0

    # Additional computed methods for new fields
    @api.depends('purchase_date', 'expected_lifespan', 'depreciation_rate')
    def _compute_depreciation_rate(self):
        """Compute default depreciation rate if not specified"""
        for asset in self:
            if not asset.depreciation_rate and asset.expected_lifespan:
                # Default to straight-line depreciation
                asset.depreciation_rate = 100.0 / asset.expected_lifespan

    @api.depends('insurance_expiry_date')
    def _compute_insurance_status(self):
        """Compute insurance status"""
        for asset in self:
            if asset.insurance_expiry_date:
                days_until_expiry = (asset.insurance_expiry_date - fields.Date.today()).days
                if days_until_expiry < 0:
                    asset.insurance_status = 'expired'
                elif days_until_expiry <= 30:
                    asset.insurance_status = 'expiring_soon'
                else:
                    asset.insurance_status = 'valid'
            else:
                asset.insurance_status = 'no_insurance'


    # Asset Lifecycle Automation Methods

    def action_trigger_maintenance(self):
        """Automatically trigger maintenance based on condition"""
        self.ensure_one()
        if self.critical_condition:
            # Create emergency maintenance work order
            from datetime import date
            today = date.today()
            workorder_vals = {
                'name': f"Emergency Maintenance - {self.name}",
                'asset_id': self.id,
                'work_order_type': 'corrective',
                'priority': '3',  # High priority
                'description': f"Automatically triggered due to critical condition on {self.name}",
                'state': 'draft',
                'start_date': today,
                'end_date': today  # Same day for calendar display
            }
            self.env['facilities.workorder'].create(workorder_vals)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Maintenance Triggered',
                    'message': f'Emergency maintenance work order created for {self.name}',
                    'type': 'warning'
                }
            }
        return True

    def action_dispose_asset(self):
        """Initiate asset disposal workflow"""
        self.ensure_one()
        if self.current_value <= 0 and self.auto_dispose_on_zero_value:
            self.disposal_workflow_state = 'pending'
            # Create disposal approval request
            return {
                'type': 'ir.actions.act_window',
                'name': 'Asset Disposal',
                'res_model': 'facilities.asset.disposal.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_asset_id': self.id},
            }
        return True

    # Enhanced Asset Status and Risk Assessment
    risk_score = fields.Float(string='Risk Score', compute='_compute_risk_score', store=True)
    maintenance_cost_ytd = fields.Monetary(string='Maintenance Cost YTD', 
                                          compute='_compute_maintenance_cost', 
                                          currency_field='currency_id')
    total_cost_of_ownership = fields.Monetary(string='Total Cost of Ownership',
                                             compute='_compute_total_cost_ownership',
                                             currency_field='currency_id')
    
    asset_health_score = fields.Float(string='Health Score (Decimal)', 
                                     compute='_compute_health_score', store=True,
                                     help='Asset health score as a decimal (0.0-1.0 representing 0%-100%)')
    
    @api.depends('criticality', 'condition', 'warranty_status')
    def _compute_risk_score(self):
        """Calculate risk score based on multiple factors"""
        for asset in self:
            score = 0
            
            # Criticality weight (0-40 points)
            criticality_scores = {'low': 10, 'medium': 20, 'high': 30, 'critical': 40}
            score += criticality_scores.get(asset.criticality, 20)
            
            # Condition weight (0-30 points)
            condition_scores = {'new': 5, 'good': 10, 'fair': 20, 'poor': 30}
            score += condition_scores.get(asset.condition, 15)
            
            
            # Warranty status weight (0-10 points)
            warranty_scores = {'valid': 0, 'none': 5, 'expired': 10}
            score += warranty_scores.get(asset.warranty_status, 5)
            
            asset.risk_score = min(100, score)

    def _compute_maintenance_cost(self):
        """Calculate maintenance cost for current year"""
        current_year = fields.Date.today().year
        for asset in self:
            # Get maintenance costs from work orders or maintenance records
            maintenance_cost = 0.0
            if hasattr(self.env, 'facilities.workorder'):
                workorders = self.env['facilities.workorder'].search([
                    ('asset_id', '=', asset.id),
                    ('start_date', '>=', f'{current_year}-01-01'),
                    ('start_date', '<=', f'{current_year}-12-31')
                ])
                maintenance_cost = sum(workorders.mapped('cost')) if workorders else 0.0
            asset.maintenance_cost_ytd = maintenance_cost

    @api.depends('purchase_cost', 'maintenance_cost_ytd', 'annual_operating_cost')
    def _compute_total_cost_ownership(self):
        """Calculate total cost of ownership"""
        for asset in self:
            years_owned = 1
            if asset.purchased_date:
                years_owned = max(1, (fields.Date.today() - asset.purchased_date).days / 365.25)
            
            total_maintenance = asset.maintenance_cost_ytd * years_owned
            total_operating = asset.annual_operating_cost * years_owned
            
            asset.total_cost_of_ownership = (asset.purchase_cost or 0) + total_maintenance + total_operating


    @api.model
    def _update_health_scores(self):
        """Cron method to update asset health scores"""
        try:
            assets = self.search([('active', '=', True)])
            
            for asset in assets:
                # Trigger health score computation
                asset._compute_health_score()
                asset._compute_health_trend()
            
            _logger.info(f"Health scores updated for {len(assets)} assets.")
            
        except Exception as e:
            _logger.error(f"Error in health score update cron: {str(e)}")

    # Additional utility methods for asset management
    def action_generate_report(self):
        """Generate comprehensive asset report"""
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'fm.asset_report',
            'report_type': 'qweb-pdf',
            'data': {'asset_ids': [self.id]},
        }

    def action_schedule_maintenance(self):
        """Schedule preventive maintenance for the asset"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Schedule Maintenance',
            'res_model': 'asset.maintenance.schedule',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_id': self.id,
                'default_maintenance_type': 'preventive',
            },
        }

    def action_view_maintenance_history(self):
        """View complete maintenance history for the asset"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Maintenance History - {self.name}',
            'res_model': 'asset.maintenance.schedule',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id},
        }

    def action_view_depreciation_history(self):
        """View depreciation history for the asset"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Depreciation History - {self.name}',
            'res_model': 'facilities.asset.depreciation',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id},
        }


    def action_export_asset_data(self):
        """Export asset data in various formats"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Export Asset Data',
            'res_model': 'facilities.asset.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_asset_ids': [(6, 0, [self.id])]},
        }

    def action_import_asset_data(self):
        """Import asset data from external sources"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Import Asset Data',
            'res_model': 'facilities.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_asset_id': self.id},
        }

    @api.model
    def get_asset_dashboard_data(self):
        """Get data for asset dashboard"""
        assets = self.search([('active', '=', True)])
        
        dashboard_data = {
            'total_assets': len(assets),
            'active_assets': len(assets.filtered(lambda a: a.state == 'active')),
            'critical_assets': len(assets.filtered(lambda a: a.criticality == 'critical')),
            'assets_by_category': {},
            'assets_by_condition': {},
            'assets_by_criticality': {},
        }
        
        # Categorize assets
        for asset in assets:
            category = asset.category_id.name or 'Uncategorized'
            dashboard_data['assets_by_category'][category] = dashboard_data['assets_by_category'].get(category, 0) + 1
            
            condition = asset.condition
            dashboard_data['assets_by_condition'][condition] = dashboard_data['assets_by_condition'].get(condition, 0) + 1
            
            criticality = asset.criticality
            dashboard_data['assets_by_criticality'][criticality] = dashboard_data['assets_by_criticality'].get(criticality, 0) + 1
        
        return dashboard_data

    @api.model
    def get_assets_needing_attention(self):
        """Get assets that need immediate attention"""
        return self.search([
            '|', '|', '|',
            ('warranty_status', '=', 'expired'),
            ('critical_condition', '=', True),
            ('asset_status', 'in', ['out_of_service', 'under_repair', 'quarantined'])
        ])

    def copy(self, default=None):
        """Override copy method to handle asset-specific fields"""
        if default is None:
            default = {}
        
        # Don't copy certain fields
        default.update({
            'asset_code': False,
            'barcode': False,
            'serial_number': False,
            'purchased_date': False,
            'installed_date': False,
            'commissioned_date': False,
            'last_maintenance_date': False,
            'last_activity': False,
            'activity_count': 0,
            'operating_hours_total': 0.0,
            'operating_hours_yearly': 0.0,
        })
        
        return super().copy(default)

    # Constraints and validations
    @api.constrains('purchased_date', 'installed_date', 'commissioned_date')
    def _check_date_sequence(self):
        """Ensure logical date sequence"""
        for asset in self:
            if asset.purchased_date and asset.installed_date:
                if asset.installed_date < asset.purchased_date:
                    raise ValidationError("Installation date cannot be before purchase date")
            
            if asset.installed_date and asset.commissioned_date:
                if asset.commissioned_date < asset.installed_date:
                    raise ValidationError("Commissioning date cannot be before installation date")
            
            if asset.purchased_date and asset.commissioned_date:
                if asset.commissioned_date < asset.purchased_date:
                    raise ValidationError("Commissioning date cannot be before purchase date")

    @api.constrains('expected_lifespan', 'purchased_date')
    def _check_lifespan(self):
        """Ensure expected lifespan is reasonable"""
        for asset in self:
            if asset.expected_lifespan and asset.expected_lifespan <= 0:
                raise ValidationError("Expected lifespan must be greater than 0")
            
            if asset.purchased_date and asset.expected_lifespan:
                # Check if asset has exceeded expected lifespan
                years_owned = (fields.Date.today() - asset.purchased_date).days / 365.25
                if years_owned > asset.expected_lifespan * 1.5:  # Allow 50% overrun
                    _logger.warning(f"Asset {asset.name} has exceeded expected lifespan by {years_owned - asset.expected_lifespan:.1f} years")

    @api.constrains('purchase_cost', 'current_value')
    def _check_values(self):
        """Ensure financial values are reasonable"""
        for asset in self:
            if asset.purchase_cost and asset.purchase_cost < 0:
                raise ValidationError("Purchase cost cannot be negative")
            
            if asset.current_value and asset.current_value < 0:
                raise ValidationError("Current value cannot be negative")
            
            if asset.purchase_cost and asset.current_value:
                if asset.current_value > asset.purchase_cost * 2:
                    _logger.warning(f"Asset {asset.name} current value is unusually high compared to purchase cost")

    @api.constrains('operating_hours_yearly', 'operating_hours_total')
    def _check_operating_hours(self):
        """Ensure operating hours are logical"""
        for asset in self:
            if asset.operating_hours_yearly and asset.operating_hours_yearly < 0:
                raise ValidationError("Operating hours cannot be negative")
            
            if asset.operating_hours_total and asset.operating_hours_total < 0:
                raise ValidationError("Total operating hours cannot be negative")
            
            if asset.operating_hours_yearly and asset.operating_hours_total:
                if asset.operating_hours_yearly > asset.operating_hours_total:
                    raise ValidationError("Yearly operating hours cannot exceed total operating hours")

    @api.constrains('utilization_target')
    def _check_utilization_target(self):
        """Ensure utilization target is reasonable"""
        for asset in self:
            if asset.utilization_target and (asset.utilization_target < 0 or asset.utilization_target > 100):
                raise ValidationError("Utilization target must be between 0 and 100")

    @api.constrains('depreciation_rate')
    def _check_depreciation_rate(self):
        """Ensure depreciation rate is reasonable"""
        for asset in self:
            if asset.depreciation_rate and (asset.depreciation_rate < 0 or asset.depreciation_rate > 100):
                raise ValidationError("Depreciation rate must be between 0 and 100")

    @api.constrains('recovery_time_objective')
    def _check_recovery_time(self):
        """Ensure recovery time objective is reasonable"""
        for asset in self:
            if asset.recovery_time_objective and asset.recovery_time_objective < 0:
                raise ValidationError("Recovery time objective cannot be negative")

    @api.constrains('training_duration')
    def _check_training_duration(self):
        """Ensure training duration is reasonable"""
        for asset in self:
            if asset.training_duration and asset.training_duration < 0:
                raise ValidationError("Training duration cannot be negative")

    @api.constrains('carbon_footprint')
    def _check_carbon_footprint(self):
        """Ensure carbon footprint is reasonable"""
        for asset in self:
            if asset.carbon_footprint and asset.carbon_footprint < 0:
                raise ValidationError("Carbon footprint cannot be negative")

    @api.constrains('uptime_percentage', 'efficiency_rating', 'reliability_score', 'availability_score', 'performance_score')
    def _check_percentage_fields(self):
        """Ensure percentage fields are within valid range"""
        for asset in self:
            percentage_fields = [
                ('uptime_percentage', asset.uptime_percentage),
                ('efficiency_rating', asset.efficiency_rating),
                ('reliability_score', asset.reliability_score),
                ('availability_score', asset.availability_score),
                ('performance_score', asset.performance_score)
            ]
            
            for field_name, value in percentage_fields:
                if value is not None and (value < 0 or value > 100):
                    raise ValidationError(f"{field_name.replace('_', ' ').title()} must be between 0 and 100")

    # Additional business logic methods
    def action_archive_asset(self):
        """Archive inactive assets"""
        self.ensure_one()
        if self.state == 'disposed':
            self.active = False
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Asset Archived',
                    'message': f'Asset {self.name} has been archived',
                    'type': 'success'
                }
            }
        else:
            raise ValidationError("Only disposed assets can be archived")

    def action_restore_asset(self):
        """Restore archived assets"""
        self.ensure_one()
        if not self.active:
            self.active = True
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Asset Restored',
                    'message': f'Asset {self.name} has been restored',
                    'type': 'success'
                }
            }
        else:
            raise ValidationError("Asset is already active")

    @api.onchange('facility_id')
    def _onchange_facility_id(self):
        """Auto-fill facility-related fields when facility is selected."""
        if self.facility_id:
            # Auto-fill facility contact information
            if self.facility_id.address:
                self.facility_address = self.facility_id.address
            if self.facility_id.phone:
                self.facility_phone = self.facility_id.phone
            if self.facility_id.email:
                self.facility_email = self.facility_id.email

    @api.onchange('room_id')
    def _onchange_room_id(self):
        """Auto-fill room-related fields when room is selected."""
        if self.room_id:
            # Auto-fill building and floor from room
            if self.room_id.floor_id:
                self.floor_id = self.room_id.floor_id
                if self.room_id.floor_id.building_id:
                    self.building_id = self.room_id.floor_id.building_id
                    if self.room_id.floor_id.building_id.facility_id:
                        self.facility_id = self.room_id.floor_id.building_id.facility_id

    @api.onchange('floor_id')
    def _onchange_floor_id(self):
        """Auto-fill floor-related fields when floor is selected."""
        if self.floor_id:
            # Auto-fill building from floor
            if self.floor_id.building_id:
                self.building_id = self.floor_id.building_id
                if self.floor_id.building_id.facility_id:
                    self.facility_id = self.floor_id.building_id.facility_id

    @api.onchange('building_id')
    def _onchange_building_id(self):
        """Auto-fill building-related fields when building is selected."""
        if self.building_id:
            # Auto-fill facility from building
            if self.building_id.facility_id:
                self.facility_id = self.building_id.facility_id

    def action_duplicate_asset(self):
        """Create a duplicate of the asset with modified values"""
        self.ensure_one()
        default_values = {
            'name': f"{self.name} (Copy)",
            'asset_code': False,
            'barcode': False,
            'serial_number': False,
            'purchased_date': False,
            'installed_date': False,
            'commissioned_date': False,
            'last_maintenance_date': False,
            'last_activity': False,
            'activity_count': 0,
            'operating_hours_total': 0.0,
            'operating_hours_yearly': 0.0,
            'state': 'draft',
            'asset_status': 'not_installed',
            'lifecycle_stage': 'planning'
        }
        
        new_asset = self.copy(default_values)
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Asset',
            'res_model': 'facilities.asset',
            'view_mode': 'form',
            'res_id': new_asset.id,
            'target': 'current',
        }

    @api.model
    def _check_disposal_candidates(self):
        """Cron helper: flag assets for disposal when value is zero or negative.
        This matches a server action expecting model._check_disposal_candidates()."""
        candidates = self.search([
            ('auto_dispose_on_zero_value', '=', True),
            ('current_value', '<=', 0),
            ('state', '!=', 'disposed'),
            ('disposal_workflow_state', 'not in', ['approved', 'completed'])
        ])
        for asset in candidates:
            try:
                if asset.disposal_workflow_state == 'none':
                    asset.disposal_workflow_state = 'pending'
                asset.message_post(body="Asset automatically flagged for disposal due to zero book value.")
            except Exception as e:
                _logger.error("Failed to flag asset %s for disposal: %s", asset.display_name, str(e))
        return len(candidates)

    def refresh_maintenance_due_status(self):
        """Refresh maintenance due status for assets.
        This method exists to resolve view validation errors during module upgrade."""
        for asset in self:
            # Trigger recomputation of maintenance-related fields
            if hasattr(asset, 'maintenance_ids'):
                asset.maintenance_ids._compute_next_maintenance_date()
        return True
    
    def unlink(self):
        """Prevent deletion of assets with active workorders or maintenance schedules."""
        for record in self:
            # Check for active workorders
            active_workorders = self.env['facilities.workorder'].search([
                ('asset_id', '=', record.id),
                ('state', 'in', ['assigned', 'in_progress'])
            ])
            if active_workorders:
                raise ValidationError(_("Cannot delete asset '%s' as it has active work orders. Please complete or cancel the work orders first.") % record.name)
            
            # Check for active maintenance schedules
            active_schedules = self.env['asset.maintenance.schedule'].search([
                ('asset_id', '=', record.id),
                ('status', 'in', ['active', 'scheduled'])
            ])
            if active_schedules:
                raise ValidationError(_("Cannot delete asset '%s' as it has active maintenance schedules. Please deactivate the schedules first.") % record.name)
        
        return super().unlink()
    
    @api.constrains('purchased_date', 'installed_date', 'commissioned_date', 'warranty_expires_date')
    def _check_asset_dates(self):
        """Validate asset dates follow logical sequence."""
        for asset in self:
            dates = []
            if asset.purchased_date:
                dates.append(('purchased', asset.purchased_date))
            if asset.installed_date:
                dates.append(('installed', asset.installed_date))
            if asset.commissioned_date:
                dates.append(('commissioned', asset.commissioned_date))
            if asset.warranty_expires_date:
                dates.append(('warranty_expires', asset.warranty_expires_date))
            
            # Check date sequence
            if asset.purchased_date and asset.installed_date and asset.purchased_date > asset.installed_date:
                raise ValidationError(_("Installation date cannot be before purchase date."))
            
            if asset.installed_date and asset.commissioned_date and asset.installed_date > asset.commissioned_date:
                raise ValidationError(_("Commissioning date cannot be before installation date."))
            
            if asset.purchased_date and asset.warranty_expires_date and asset.purchased_date > asset.warranty_expires_date:
                raise ValidationError(_("Warranty expiration date cannot be before purchase date."))
    
    @api.constrains('purchase_cost', 'current_value')
    def _check_asset_values(self):
        """Validate asset financial values."""
        for asset in self:
            if asset.purchase_cost and asset.purchase_cost < 0:
                raise ValidationError(_("Purchase cost cannot be negative."))
            if asset.current_value and asset.current_value < 0:
                raise ValidationError(_("Current value cannot be negative."))
            if asset.purchase_cost and asset.purchase_cost > 1000000000:  # 1 billion
                raise ValidationError(_("Purchase cost seems unrealistic. Please verify this value."))
    
    @api.constrains('expected_lifespan')
    def _check_expected_lifespan(self):
        """Validate expected lifespan is reasonable."""
        for asset in self:
            if asset.expected_lifespan and asset.expected_lifespan <= 0:
                raise ValidationError(_("Expected lifespan must be greater than 0."))
            if asset.expected_lifespan and asset.expected_lifespan > 200:
                raise ValidationError(_("Expected lifespan cannot exceed 200 years."))
    
    @api.constrains('asset_code')
    def _check_asset_code_unique(self):
        """Ensure asset codes are unique within the same facility."""
        for asset in self:
            if asset.asset_code and asset.asset_code != 'New':
                existing = self.search([
                    ('asset_code', '=', asset.asset_code),
                    ('facility_id', '=', asset.facility_id.id),
                    ('id', '!=', asset.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("Asset code '%s' already exists in facility '%s'.") % (asset.asset_code, asset.facility_id.name))
    
    @api.constrains('asset_tag')
    def _check_asset_tag_unique(self):
        """Ensure asset tags are globally unique."""
        for asset in self:
            if asset.asset_tag:
                existing = self.search([
                    ('asset_tag', '=', asset.asset_tag),
                    ('id', '!=', asset.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("Asset tag '%s' is already in use by asset '%s'.") % (asset.asset_tag, existing.name))