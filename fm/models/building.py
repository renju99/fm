# models/building.py
from odoo import models, fields, api

class FacilityBuilding(models.Model):
    _name = 'facilities.building'
    _description = 'Facility Building'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Building Name', required=True)
    code = fields.Char(string='Building Code', required=True, copy=False, readonly=True, default='New')
    facility_id = fields.Many2one('facilities.facility', string='Facility/Property', required=True, ondelete='restrict', help="The main facility or property this building belongs to.")
    manager_id = fields.Many2one('hr.employee', string='Building Manager')
    active = fields.Boolean(string='Active', default=True)

    # Building Specific Fields
    address = fields.Char(string='Address', help="Street address of the building if different from facility.")
    building_type = fields.Selection([
        ('office', 'Office'),
        ('residential', 'Residential'),
        ('warehouse', 'Warehouse'),
        ('retail', 'Retail'),
        ('hospital', 'Hospital'),
        ('educational', 'Educational'),
        ('other', 'Other'),
    ], string='Building Type', default='office')
    number_of_floors = fields.Integer(string='Number of Floors')
    total_area_sqm = fields.Float(string='Total Area (sqm)', digits=(10, 2))
    year_constructed = fields.Integer(string='Year Constructed')
    description = fields.Html(string='Description')
    image = fields.Image(string="Building Image", max_width=1024, max_height=1024)

    # NEW: One2many relationship to Floors
    floor_ids = fields.One2many('facilities.floor', 'building_id', string='Floors', help="List of floors within this building.")
    floor_count = fields.Integer(compute='_compute_floor_count', string='Floor Count', store=True)
    
    # NEW: One2many relationship to Assets
    asset_ids = fields.One2many('facilities.asset', 'building_id', string='Assets', help="List of assets located in this building.")

    @api.depends('floor_ids')
    def _compute_floor_count(self):
        for rec in self:
            rec.floor_count = len(rec.floor_ids)

    @api.model_create_multi
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('facilities.building') or 'New'
        
        return super(FacilityBuilding, self).create(vals_list)

    @api.constrains('facility_id')
    def _check_facility_id(self):
        for rec in self:
            if not rec.facility_id:
                raise fields.ValidationError("A building must be linked to a Facility.")
    
    @api.constrains('number_of_floors')
    def _check_number_of_floors(self):
        """Validate number of floors is reasonable."""
        for building in self:
            if building.number_of_floors and building.number_of_floors < 0:
                raise ValidationError(_("Number of floors cannot be negative."))
            if building.number_of_floors and building.number_of_floors > 200:
                raise ValidationError(_("Number of floors cannot exceed 200. Please verify this value."))
    
    @api.constrains('total_area_sqm')
    def _check_total_area(self):
        """Validate building area is reasonable."""
        for building in self:
            if building.total_area_sqm and building.total_area_sqm <= 0:
                raise ValidationError(_("Building area must be greater than 0."))
            if building.total_area_sqm and building.total_area_sqm > 10000000:  # 10M sqm
                raise ValidationError(_("Building area seems unrealistic. Please verify this value."))
    
    @api.constrains('year_constructed')
    def _check_year_constructed(self):
        """Validate construction year is reasonable."""
        from datetime import date
        current_year = date.today().year
        for building in self:
            if building.year_constructed:
                if building.year_constructed < 1800:
                    raise ValidationError(_("Construction year cannot be before 1800."))
                if building.year_constructed > current_year + 10:
                    raise ValidationError(_("Construction year cannot be more than 10 years in the future."))
    
    @api.constrains('code')
    def _check_building_code_unique(self):
        """Ensure building codes are unique within the same facility."""
        for building in self:
            if building.code and building.code != 'New':
                existing = self.search([
                    ('code', '=', building.code),
                    ('facility_id', '=', building.facility_id.id),
                    ('id', '!=', building.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("Building code '%s' already exists in facility '%s'.") % (building.code, building.facility_id.name))