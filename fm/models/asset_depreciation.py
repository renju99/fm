from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

class AssetDepreciation(models.Model):
    _name = 'facilities.asset.depreciation'
    _description = 'Asset Depreciation Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'depreciation_date desc, asset_id'
    _rec_name = 'display_name'

    # Basic Information
    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True, 
                              ondelete='cascade', tracking=True)
    depreciation_date = fields.Date('Depreciation Date', required=True, 
                                   default=fields.Date.context_today, tracking=True)
    
    # Financial Values
    value_before = fields.Monetary('Value Before Depreciation', currency_field='currency_id', 
                                  required=True, tracking=True)
    depreciation_amount = fields.Monetary('Depreciation Amount', currency_field='currency_id', 
                                         required=True, tracking=True)
    value_after = fields.Monetary('Value After Depreciation', currency_field='currency_id', 
                                 compute='_compute_value_after', store=True, tracking=True)
    accumulated_depreciation = fields.Monetary('Accumulated Depreciation', 
                                              currency_field='currency_id',
                                              compute='_compute_accumulated_depreciation', 
                                              store=True)
    
    # Depreciation Method and Details
    depreciation_method = fields.Selection([
        ('straight_line', 'Straight Line'),
        ('declining_balance', 'Declining Balance'),
        ('sum_of_years', 'Sum of Years Digits'),
        ('units_of_production', 'Units of Production'),
        ('manual', 'Manual')
    ], string='Depreciation Method', default='straight_line', required=True, tracking=True)
    
    depreciation_rate = fields.Float('Depreciation Rate (%)', tracking=True,
                                   help="Annual depreciation rate for declining balance method")
    useful_life_years = fields.Float('Useful Life (Years)', tracking=True,
                                   help="Expected useful life for straight line method")
    salvage_value = fields.Monetary('Salvage Value', currency_field='currency_id',
                                   help="Expected value at end of useful life")
    
    # Period Information
    period_start = fields.Date('Period Start', tracking=True)
    period_end = fields.Date('Period End', tracking=True)
    is_year_end = fields.Boolean('Year-End Depreciation', default=False)
    
    # Automatic vs Manual
    is_automatic = fields.Boolean('Automatic Calculation', default=True, tracking=True)
    calculation_notes = fields.Html('Calculation Notes')
    
    # Status and Validation
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    # Technical Fields
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                 related='asset_id.currency_id', store=True)
    company_id = fields.Many2one('res.company', string='Company',
                                default=lambda self: self.env.company)
    
    _sql_constraints = [
        ('positive_depreciation', 'CHECK(depreciation_amount >= 0)', 
         'Depreciation amount must be positive!'),
        ('positive_value_before', 'CHECK(value_before >= 0)', 
         'Value before depreciation must be positive!'),
    ]

    @api.depends('asset_id', 'depreciation_date', 'depreciation_amount')
    def _compute_display_name(self):
        for record in self:
            if record.asset_id:
                record.display_name = f"{record.asset_id.name} - {record.depreciation_date} ({record.depreciation_amount})"
            else:
                record.display_name = "New Depreciation Record"

    @api.depends('value_before', 'depreciation_amount')
    def _compute_value_after(self):
        for record in self:
            record.value_after = record.value_before - record.depreciation_amount

    @api.depends('asset_id', 'depreciation_date')
    def _compute_accumulated_depreciation(self):
        for record in self:
            if record.asset_id:
                # Sum all depreciation up to this date
                prior_depreciations = self.search([
                    ('asset_id', '=', record.asset_id.id),
                    ('depreciation_date', '<=', record.depreciation_date),
                    ('state', '!=', 'cancelled'),
                    ('id', '!=', record.id)
                ])
                record.accumulated_depreciation = sum(prior_depreciations.mapped('depreciation_amount')) + record.depreciation_amount
            else:
                record.accumulated_depreciation = record.depreciation_amount

    @api.onchange('asset_id', 'depreciation_method', 'period_start', 'period_end')
    def _onchange_calculate_depreciation(self):
        """Auto-calculate depreciation when conditions change"""
        if self.is_automatic and self.asset_id and self.depreciation_method != 'manual':
            self._calculate_depreciation_amount()

    def _calculate_depreciation_amount(self):
        """Calculate depreciation amount based on selected method"""
        if not self.asset_id or not self.period_start or not self.period_end:
            return
            
        # Get the current book value
        current_value = self._get_current_book_value()
        
        if self.depreciation_method == 'straight_line':
            self._calculate_straight_line(current_value)
        elif self.depreciation_method == 'declining_balance':
            self._calculate_declining_balance(current_value)
        elif self.depreciation_method == 'sum_of_years':
            self._calculate_sum_of_years(current_value)
        elif self.depreciation_method == 'units_of_production':
            self._calculate_units_of_production(current_value)

    def _get_current_book_value(self):
        """Get current book value of the asset"""
        # Start with purchase cost or current value
        current_value = self.asset_id.current_value or self.asset_id.purchase_cost or 0
        
        # Subtract accumulated depreciation up to period start
        prior_depreciations = self.search([
            ('asset_id', '=', self.asset_id.id),
            ('depreciation_date', '<', self.period_start),
            ('state', '!=', 'cancelled')
        ])
        accumulated = sum(prior_depreciations.mapped('depreciation_amount'))
        
        return max(0, current_value - accumulated)

    def _calculate_straight_line(self, current_value):
        """Calculate straight-line depreciation"""
        if not self.useful_life_years or self.useful_life_years <= 0:
            self.useful_life_years = self.asset_id.expected_lifespan or 5
            
        depreciable_amount = current_value - (self.salvage_value or 0)
        period_months = (self.period_end - self.period_start).days / 30.44  # Average days per month
        annual_depreciation = depreciable_amount / self.useful_life_years
        
        self.depreciation_amount = (annual_depreciation * period_months) / 12
        self.value_before = current_value

    def _calculate_declining_balance(self, current_value):
        """Calculate declining balance depreciation"""
        if not self.depreciation_rate or self.depreciation_rate <= 0:
            self.depreciation_rate = 20.0  # Default 20% declining balance
            
        period_months = (self.period_end - self.period_start).days / 30.44
        periodic_rate = (self.depreciation_rate / 100) * (period_months / 12)
        
        self.depreciation_amount = current_value * periodic_rate
        self.value_before = current_value

    def _calculate_sum_of_years(self, current_value):
        """Calculate sum of years digits depreciation"""
        if not self.useful_life_years or self.useful_life_years <= 0:
            self.useful_life_years = self.asset_id.expected_lifespan or 5
            
        # Calculate years remaining
        asset_age = 0
        if self.asset_id.purchased_date:
            asset_age = (self.period_start - self.asset_id.purchased_date).days / 365.25
            
        years_remaining = max(1, self.useful_life_years - asset_age)
        sum_of_years = (self.useful_life_years * (self.useful_life_years + 1)) / 2
        
        depreciable_amount = current_value - (self.salvage_value or 0)
        period_months = (self.period_end - self.period_start).days / 30.44
        
        annual_depreciation = (years_remaining / sum_of_years) * depreciable_amount
        self.depreciation_amount = (annual_depreciation * period_months) / 12
        self.value_before = current_value

    def _calculate_units_of_production(self, current_value):
        """Calculate units of production depreciation"""
        # This would require usage data from the asset
        # For now, fall back to straight line
        self._calculate_straight_line(current_value)

    def action_calculate(self):
        """Manual trigger for depreciation calculation"""
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_("Can only calculate depreciation for draft records."))
            
        self._calculate_depreciation_amount()
        self.state = 'calculated'
        self.message_post(body=_("Depreciation calculated using %s method.") % dict(self._fields['depreciation_method'].selection)[self.depreciation_method])

    def action_post(self):
        """Post the depreciation record"""
        self.ensure_one()
        if self.state not in ['calculated', 'draft']:
            raise ValidationError(_("Can only post calculated or draft depreciation records."))
            
        # Update asset current value
        self.asset_id.current_value = self.value_after
        
        self.state = 'posted'
        self.message_post(body=_("Depreciation posted. Asset value updated to %s.") % self.value_after)

    def action_cancel(self):
        """Cancel the depreciation record"""
        self.ensure_one()
        if self.state == 'posted':
            raise ValidationError(_("Cannot cancel posted depreciation records."))
            
        self.state = 'cancelled'

    @api.model
    def create_automatic_depreciation(self, asset_id, period_end=None):
        """Create automatic depreciation for an asset"""
        if not period_end:
            period_end = fields.Date.today()
            
        asset = self.env['facilities.asset'].browse(asset_id)
        if not asset:
            return False
            
        # Check if depreciation already exists for this period
        existing = self.search([
            ('asset_id', '=', asset_id),
            ('period_end', '=', period_end),
            ('state', '!=', 'cancelled')
        ])
        if existing:
            return existing
            
        # Create new depreciation record
        values = {
            'asset_id': asset_id,
            'depreciation_date': period_end,
            'period_start': period_end.replace(day=1),  # First day of month
            'period_end': period_end,
            'is_automatic': True,
            'depreciation_method': 'straight_line',  # Default method
        }
        
        depreciation = self.create(values)
        depreciation.action_calculate()
        
        return depreciation
