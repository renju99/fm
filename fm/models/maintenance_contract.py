# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class MaintenanceContract(models.Model):
    _name = 'facilities.maintenance.contract'
    _description = 'Maintenance Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, name'

    name = fields.Char(
        string='Contract Name',
        required=True,
        tracking=True,
        help='Name of the maintenance contract'
    )
    
    contract_number = fields.Char(
        string='Contract Number',
        required=True,
        tracking=True,
        help='Unique contract number'
    )
    
    # Use standard partner instead of custom vendor
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True,
        domain=[('is_company', '=', True), ('supplier_rank', '>', 0)],
        tracking=True,
        help='Vendor for this contract'
    )
    
    contract_type = fields.Selection([
        ('maintenance', 'Maintenance Contract'),
        ('service', 'Service Contract'),
        ('supply', 'Supply Contract'),
        ('other', 'Other')
    ], string='Contract Type', required=True, default='maintenance', tracking=True)
    
    # Contract Dates
    start_date = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
        help='Contract start date'
    )
    
    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
        help='Contract end date'
    )
    
    # Use standard analytic account for cost tracking
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        help='Analytic account for cost tracking'
    )
    
    # Financial Information
    contract_value = fields.Monetary(
        string='Contract Value',
        currency_field='currency_id',
        required=True,
        tracking=True,
        help='Total contract value'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True
    )
    
    # Contract Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated')
    ], string='Status', default='draft', tracking=True)
    
    # Contract Details
    description = fields.Text(
        string='Description',
        help='Contract description and scope of work'
    )
    
    # Relations
    workorder_ids = fields.One2many(
        'facilities.workorder',
        'contract_id',
        string='Work Orders',
        help='Work orders under this contract'
    )
    
    # Use standard invoice relationship
    invoice_ids = fields.One2many(
        'account.move',
        'contract_id',
        string='Invoices',
        domain=[('move_type', '=', 'in_invoice')],
        help='Contract invoices'
    )
    
    # Statistics
    total_workorders = fields.Integer(
        string='Total Work Orders',
        compute='_compute_statistics',
        store=True,
        help='Total work orders under contract'
    )
    
    total_invoiced = fields.Monetary(
        string='Total Invoiced',
        currency_field='currency_id',
        compute='_compute_statistics',
        store=True,
        help='Total amount invoiced'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    @api.depends('workorder_ids', 'invoice_ids.amount_total')
    def _compute_statistics(self):
        for contract in self:
            contract.total_workorders = len(contract.workorder_ids)
            invoices = contract.invoice_ids.filtered(lambda i: i.state == 'posted')
            contract.total_invoiced = sum(invoices.mapped('amount_total'))
    
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for contract in self:
            if contract.start_date and contract.end_date:
                if contract.start_date >= contract.end_date:
                    raise ValidationError(_('End date must be after start date.'))
    
    @api.constrains('contract_number')
    def _check_unique_contract_number(self):
        for contract in self:
            existing = self.search([
                ('contract_number', '=', contract.contract_number),
                ('id', '!=', contract.id),
                ('company_id', '=', contract.company_id.id)
            ])
            if existing:
                raise ValidationError(_('Contract number must be unique within the company.'))
    
    def action_activate(self):
        """Activate contract"""
        self.write({'state': 'active'})
        self.message_post(body=_('Contract activated'))
    
    def action_terminate(self):
        """Terminate contract"""
        self.write({'state': 'terminated'})
        self.message_post(body=_('Contract terminated'))
    
    @api.model
    def _cron_check_expiring_contracts(self):
        """Cron job to check for expiring contracts"""
        today = fields.Date.today()
        expiring_contracts = self.search([
            ('state', '=', 'active'),
            ('end_date', '<=', today + timedelta(days=30)),
            ('end_date', '>', today)
        ])
        
        for contract in expiring_contracts:
            contract.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=contract.end_date - timedelta(days=7),
                summary=_('Contract Expiring Soon'),
                note=_('Contract %s is expiring on %s. Please take necessary action.') % (
                    contract.name, contract.end_date
                )
            )
    
    def action_view_workorders(self):
        """View work orders for this contract"""
        action = {
            'name': _('Work Orders - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {
                'default_contract_id': self.id,
                'create': False,  # Disable create from this view
            }
        }
        
        # If only one work order, open it directly
        workorders = self.workorder_ids
        if len(workorders) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': workorders.id,
                'views': [(False, 'form')]
            })
        
        return action
    
    def action_view_invoices(self):
        """View invoices for this contract"""
        action = {
            'name': _('Invoices - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id), ('move_type', '=', 'in_invoice')],
            'context': {
                'default_contract_id': self.id,
                'default_move_type': 'in_invoice',
                'create': False,  # Disable create from this view
            }
        }
        
        # If only one invoice, open it directly
        invoices = self.invoice_ids
        if len(invoices) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': invoices.id,
                'views': [(False, 'form')]
            })
        
        return action


class AccountMoveContractInherit(models.Model):
    _inherit = 'account.move'

    # Add contract_id field to account.move for maintenance contract integration
    contract_id = fields.Many2one(
        'facilities.maintenance.contract',
        string='Maintenance Contract',
        help='Maintenance contract related to this invoice'
    )
