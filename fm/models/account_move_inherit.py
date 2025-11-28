# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    # Add contract_id field to account.move for vendor contract integration
    # Note: Using standard Odoo purchase module for vendor contracts
    # contract_id = fields.Many2one(
    #     'purchase.order',
    #     string='Related Purchase Order',
    #     help='Purchase order related to this invoice'
    # )
    
    # Add cost_center_id field for financial tracking
    # cost_center_id = fields.Many2one(
    #     'facilities.cost.center',
    #     string='Cost Center',
    #     help='Cost center for this invoice'
    # )
    
    # Add workorder_id field to link invoices to work orders
    workorder_id = fields.Many2one(
        'facilities.workorder',
        string='Work Order',
        help='Work order related to this invoice'
    )