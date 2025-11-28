# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class CurrencyExchangeRate(models.Model):
    _name = 'facilities.currency.exchange.rate'
    _description = 'Currency Exchange Rate for Facilities'
    _order = 'date desc, currency_id'

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        help='Foreign currency'
    )
    
    base_currency_id = fields.Many2one(
        'res.currency',
        string='Base Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        help='Base currency for conversion'
    )
    
    rate = fields.Float(
        string='Exchange Rate',
        digits=(12, 6),
        required=True,
        help='Exchange rate from base currency to foreign currency'
    )
    
    inverse_rate = fields.Float(
        string='Inverse Rate',
        digits=(12, 6),
        compute='_compute_inverse_rate',
        store=True,
        help='Exchange rate from foreign currency to base currency'
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        help='Date of the exchange rate'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this rate is active'
    )
    
    source = fields.Selection([
        ('manual', 'Manual Entry'),
        ('system', 'System Import'),
        ('api', 'API Update'),
        ('bank', 'Bank Rate')
    ], string='Source', default='manual', help='Source of exchange rate')
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this exchange rate'
    )
    
    @api.depends('rate')
    def _compute_inverse_rate(self):
        for record in self:
            if record.rate:
                record.inverse_rate = 1 / record.rate
            else:
                record.inverse_rate = 0
    
    @api.constrains('rate')
    def _check_rate(self):
        for record in self:
            if record.rate <= 0:
                raise ValidationError(_('Exchange rate must be positive.'))
    
    @api.constrains('currency_id', 'base_currency_id')
    def _check_currencies(self):
        for record in self:
            if record.currency_id == record.base_currency_id:
                raise ValidationError(_('Currency and base currency must be different.'))


class MultiCurrencyMixin(models.AbstractModel):
    _name = 'facilities.multi.currency.mixin'
    _description = 'Multi-Currency Support Mixin'

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        help='Currency for this record'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company for this record'
    )
    
    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Company Currency',
        readonly=True
    )
    
    exchange_rate = fields.Float(
        string='Exchange Rate',
        digits=(12, 6),
        default=1.0,
        help='Exchange rate used for conversion'
    )
    
    exchange_rate_date = fields.Date(
        string='Exchange Rate Date',
        default=fields.Date.today,
        help='Date of exchange rate'
    )
    
    def _get_exchange_rate(self, from_currency, to_currency, date=None):
        """Get exchange rate between two currencies"""
        if not date:
            date = fields.Date.today()
        
        if from_currency == to_currency:
            return 1.0
        
        # Try to get rate from our custom exchange rates first
        rate_record = self.env['facilities.currency.exchange.rate'].search([
            ('currency_id', '=', from_currency.id),
            ('base_currency_id', '=', to_currency.id),
            ('date', '<=', date),
            ('active', '=', True)
        ], order='date desc', limit=1)
        
        if rate_record:
            return rate_record.rate
        
        # Fallback to Odoo's currency conversion
        return from_currency._get_conversion_rate(from_currency, to_currency, self.env.company, date)
    
    def _convert_amount(self, amount, from_currency, to_currency, date=None):
        """Convert amount between currencies"""
        if not date:
            date = fields.Date.today()
        
        if from_currency == to_currency:
            return amount
        
        rate = self._get_exchange_rate(from_currency, to_currency, date)
        return amount * rate


# Note: Multi-currency functionality is now directly integrated into the base models
# through inheritance from facilities.multi.currency.mixin


class CurrencyConversionWizard(models.TransientModel):
    _name = 'facilities.currency.conversion.wizard'
    _description = 'Currency Conversion Wizard'

    from_currency_id = fields.Many2one(
        'res.currency',
        string='From Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    
    to_currency_id = fields.Many2one(
        'res.currency',
        string='To Currency',
        required=True
    )
    
    amount = fields.Float(
        string='Amount',
        required=True,
        digits=(12, 2)
    )
    
    conversion_date = fields.Date(
        string='Conversion Date',
        required=True,
        default=fields.Date.today
    )
    
    exchange_rate = fields.Float(
        string='Exchange Rate',
        digits=(12, 6),
        compute='_compute_exchange_rate',
        readonly=True
    )
    
    converted_amount = fields.Float(
        string='Converted Amount',
        digits=(12, 2),
        compute='_compute_converted_amount',
        readonly=True
    )
    
    @api.depends('from_currency_id', 'to_currency_id', 'conversion_date')
    def _compute_exchange_rate(self):
        for wizard in self:
            if wizard.from_currency_id and wizard.to_currency_id:
                mixin = self.env['facilities.multi.currency.mixin']
                wizard.exchange_rate = mixin._get_exchange_rate(
                    wizard.from_currency_id,
                    wizard.to_currency_id,
                    wizard.conversion_date
                )
            else:
                wizard.exchange_rate = 1.0
    
    @api.depends('amount', 'exchange_rate')
    def _compute_converted_amount(self):
        for wizard in self:
            wizard.converted_amount = wizard.amount * wizard.exchange_rate
    
    def action_convert(self):
        """Perform currency conversion and return result"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Conversion Result'),
            'res_model': 'facilities.currency.conversion.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
