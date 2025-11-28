from odoo import models, fields, api
from odoo.exceptions import ValidationError

class AssetTag(models.Model):
    _name = 'facilities.asset.tag'
    _description = 'Asset Tag'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char('Tag Name', required=True, translate=True, tracking=True)
    description = fields.Text('Description', translate=True)
    color = fields.Integer('Color Index', default=0)
    active = fields.Boolean('Active', default=True, tracking=True)
    
    # Tag Properties
    tag_type = fields.Selection([
        ('functional', 'Functional'),
        ('location', 'Location'),
        ('priority', 'Priority'),
        ('status', 'Status'),
        ('custom', 'Custom')
    ], string='Tag Type', default='custom', tracking=True)
    
    # Usage tracking
    asset_count = fields.Integer('Asset Count', compute='_compute_asset_count', store=True)
    asset_ids = fields.Many2many('facilities.asset', 'asset_tag_rel', 'tag_id', 'asset_id', string='Assets')
    
    # Tag hierarchy
    parent_id = fields.Many2one('facilities.asset.tag', string='Parent Tag', 
                               ondelete='cascade', tracking=True)
    child_ids = fields.One2many('facilities.asset.tag', 'parent_id', string='Child Tags')
    
    # Tag metadata
    sequence = fields.Integer('Sequence', default=10, help="Determines the order of tags")
    is_system = fields.Boolean('System Tag', default=False, 
                              help="System tags cannot be deleted or modified")
    
    @api.depends('asset_ids')
    def _compute_asset_count(self):
        for tag in self:
            tag.asset_count = len(tag.asset_ids)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Ensure unique tag names within the same type"""
        for vals in vals_list:
            if vals.get('name') and vals.get('tag_type'):
                existing = self.search([
                    ('name', '=', vals['name']),
                    ('tag_type', '=', vals['tag_type'])
                ])
                if existing:
                    raise ValidationError(f"Tag '{vals['name']}' already exists for type '{vals['tag_type']}'")
        return super().create(vals_list)
    
    def write(self, vals):
        """Prevent modification of system tags"""
        if 'is_system' in vals and any(tag.is_system for tag in self):
            raise ValidationError("Cannot modify system tags")
        return super().write(vals)
    
    def unlink(self):
        """Prevent deletion of system tags"""
        if any(tag.is_system for tag in self):
            raise ValidationError("Cannot delete system tags")
        return super().unlink()
    
    def action_view_assets(self):
        """Action to view assets with this tag"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Assets - {self.name}',
            'res_model': 'facilities.asset',
            'view_mode': 'kanban,list,form',
            'domain': [('asset_tags', 'in', self.id)],
            'context': {'default_asset_tags': [(4, self.id)]},
        }