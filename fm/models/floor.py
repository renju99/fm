# models/floor.py
from odoo import models, fields, api

class FacilityFloor(models.Model):
    _name = 'facilities.floor'
    _description = 'Facility Floor'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Floor Number/Name', required=True)
    code = fields.Char(string='Floor Code', required=True, copy=False, readonly=True, default='New')
    building_id = fields.Many2one('facilities.building', string='Building', required=True, ondelete='restrict', help="The building this floor belongs to.")
    facility_id = fields.Many2one('facilities.facility', related='building_id.facility_id', string='Facility', store=True, readonly=True, help="The facility this floor indirectly belongs to via its building.")
    manager_id = fields.Many2one('hr.employee', string='Floor Manager')
    active = fields.Boolean(string='Active', default=True)

    # Floor Specific Fields
    level = fields.Integer(string='Level', help="Floor level (e.g., 0 for ground, 1 for first floor).")
    area_sqm = fields.Float(string='Area (sqm)', digits=(10, 2))
    description = fields.Html(string='Description')
    notes = fields.Html(string='Notes')

    # NEW: One2many relationship to Rooms
    room_ids = fields.One2many('facilities.room', 'floor_id', string='Rooms', help="List of rooms on this floor.")
    room_count = fields.Integer(compute='_compute_room_count', string='Number of Rooms', store=True)

    @api.depends('room_ids')
    def _compute_room_count(self):
        for rec in self:
            rec.room_count = len(rec.room_ids)

    @api.model_create_multi
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('facilities.floor') or 'New'
        
        return super(FacilityFloor, self).create(vals_list)

    @api.constrains('building_id')
    def _check_building_id(self):
        for rec in self:
            if not rec.building_id:
                raise fields.ValidationError("A floor must be linked to a Building.")
    
    @api.constrains('level')
    def _check_floor_level(self):
        """Validate floor level is reasonable."""
        for floor in self:
            if floor.level is not None:
                if floor.level < -10:
                    raise ValidationError(_("Floor level cannot be below -10 (basement levels)."))
                if floor.level > 200:
                    raise ValidationError(_("Floor level cannot exceed 200."))
    
    @api.constrains('area_sqm')
    def _check_floor_area(self):
        """Validate floor area is reasonable and doesn't exceed building area."""
        for floor in self:
            if floor.area_sqm and floor.area_sqm <= 0:
                raise ValidationError(_("Floor area must be greater than 0."))
            
            # Check against building total area if available
            if floor.area_sqm and floor.building_id.total_area_sqm:
                if floor.area_sqm > floor.building_id.total_area_sqm:
                    raise ValidationError(_("Floor area (%.2f sqm) cannot exceed building total area (%.2f sqm).") % 
                                        (floor.area_sqm, floor.building_id.total_area_sqm))
    
    @api.constrains('code')
    def _check_floor_code_unique(self):
        """Ensure floor codes are unique within the same building."""
        for floor in self:
            if floor.code and floor.code != 'New':
                existing = self.search([
                    ('code', '=', floor.code),
                    ('building_id', '=', floor.building_id.id),
                    ('id', '!=', floor.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("Floor code '%s' already exists in building '%s'.") % (floor.code, floor.building_id.name))
    
    @api.constrains('level', 'building_id')
    def _check_floor_level_unique(self):
        """Ensure floor levels are unique within the same building."""
        for floor in self:
            if floor.level is not None:
                existing = self.search([
                    ('level', '=', floor.level),
                    ('building_id', '=', floor.building_id.id),
                    ('id', '!=', floor.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("Floor level '%d' already exists in building '%s'.") % (floor.level, floor.building_id.name))