from odoo import models, fields, api

class AssetCategory(models.Model):
    _name = 'facilities.asset.category'
    _description = 'Asset Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'name'

    @api.model
    def _valid_field_parameter(self, field, name):
        return name == 'unaccent' or super()._valid_field_parameter(field, name)

    name = fields.Char('Category Name', required=True, translate=True, tracking=True)
    active = fields.Boolean('Active', default=True, tracking=True)
    
    # Asset Management
    asset_ids = fields.One2many('facilities.asset', 'category_id', string='Assets')
    asset_count = fields.Integer(
        'Assets Count', compute='_compute_asset_count', store=True)
    
    # Category Properties
    category_type = fields.Selection([
        ('equipment', 'Equipment'),
        ('furniture', 'Furniture'),
        ('vehicle', 'Vehicle'),
        ('it', 'IT Hardware'),
        ('building', 'Building Component'),
        ('infrastructure', 'Infrastructure'),
        ('tool', 'Tool'),
        ('other', 'Other')
    ], string='Category Type', default='other', tracking=True)
    
    
    @api.depends('asset_ids')
    def _compute_asset_count(self):
        for category in self:
            category.asset_count = len(category.asset_ids)

    def action_view_assets(self):
        """Open assets in this category"""
        action = self.env.ref('fm.action_asset').read()[0]
        action['domain'] = [('category_id', '=', self.id)]
        action['context'] = {'default_category_id': self.id}
        return action
