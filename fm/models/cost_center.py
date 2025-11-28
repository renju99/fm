# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class CostCenter(models.Model):
    _name = 'facilities.cost.center'
    _description = 'Cost Center Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'complete_name'
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'

    name = fields.Char(
        string='Cost Center Name',
        required=True,
        tracking=True,
        help='Name of the cost center'
    )
    
    code = fields.Char(
        string='Cost Center Code',
        required=True,
        tracking=True,
        help='Unique code for the cost center'
    )
    
    complete_name = fields.Char(
        string='Complete Name',
        compute='_compute_complete_name',
        recursive=True,
        store=True,
        help='Complete hierarchical name'
    )
    
    parent_id = fields.Many2one(
        'facilities.cost.center',
        string='Parent Cost Center',
        index=True,
        ondelete='cascade',
        tracking=True,
        help='Parent cost center in hierarchy'
    )
    
    child_ids = fields.One2many(
        'facilities.cost.center',
        'parent_id',
        string='Child Cost Centers',
        help='Child cost centers'
    )
    
    parent_path = fields.Char(index=True)
    
    level = fields.Integer(
        string='Level',
        compute='_compute_level',
        store=True,
        help='Hierarchy level'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='Whether this cost center is active'
    )
    
    type = fields.Selection([
        ('department', 'Department'),
        ('project', 'Project'),
        ('facility', 'Facility'),
        ('building', 'Building'),
        ('floor', 'Floor'),
        ('room', 'Room'),
        ('asset', 'Asset'),
        ('service', 'Service'),
        ('other', 'Other')
    ], string='Type', required=True, default='department', tracking=True)
    
    description = fields.Text(
        string='Description',
        help='Cost center description'
    )
    
    manager_id = fields.Many2one(
        'res.users',
        string='Manager',
        tracking=True,
        help='Cost center manager'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        required=True,
        tracking=True,
        help='Linked analytic account for budget tracking and cost analysis'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Currency',
        readonly=True,
        store=True
    )
    
    # Budget and Financial Information
    budget_allocated = fields.Monetary(
        string='Budget Allocated',
        currency_field='currency_id',
        compute='_compute_financial_totals',
        store=True,
        help='Total budget allocated to this cost center'
    )
    
    budget_spent = fields.Monetary(
        string='Budget Spent',
        currency_field='currency_id',
        compute='_compute_financial_totals',
        store=True,
        help='Total budget spent by this cost center'
    )
    
    budget_remaining = fields.Monetary(
        string='Budget Remaining',
        currency_field='currency_id',
        compute='_compute_financial_totals',
        store=True,
        help='Remaining budget for this cost center'
    )
    
    budget_utilization = fields.Float(
        string='Budget Utilization %',
        compute='_compute_financial_totals',
        store=True,
        help='Budget utilization percentage'
    )
    
    # Multi-currency budget totals
    budget_allocated_company_currency = fields.Monetary(
        string='Budget Allocated (Company Currency)',
        currency_field='company_currency_id',
        compute='_compute_company_currency_totals',
        store=True,
        help='Budget allocated in company currency'
    )
    
    budget_spent_company_currency = fields.Monetary(
        string='Budget Spent (Company Currency)',
        currency_field='company_currency_id',
        compute='_compute_company_currency_totals',
        store=True,
        help='Budget spent in company currency'
    )
    
    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Company Currency',
        readonly=True
    )
    
    # Related Records
    facility_id = fields.Many2one(
        'facilities.facility',
        string='Related Facility',
        help='Related facility if applicable'
    )
    
    building_id = fields.Many2one(
        'facilities.building',
        string='Related Building',
        help='Related building if applicable'
    )
    
    floor_id = fields.Many2one(
        'facilities.floor',
        string='Related Floor',
        help='Related floor if applicable'
    )
    
    room_id = fields.Many2one(
        'facilities.room',
        string='Related Room',
        help='Related room if applicable'
    )
    
    asset_id = fields.Many2one(
        'facilities.asset',
        string='Related Asset',
        help='Related asset if applicable'
    )
    
    # One2many Relations
    budget_line_ids = fields.One2many(
        'facilities.budget.line',
        'cost_center_id',
        string='Budget Lines',
        help='Budget allocations for this cost center'
    )
    
    expense_ids = fields.One2many(
        'facilities.budget.expense',
        'cost_center_id',
        string='Expenses',
        help='Expenses charged to this cost center'
    )
    
    workorder_ids = fields.One2many(
        'facilities.workorder',
        'cost_center_id',
        string='Work Orders',
        help='Work orders assigned to this cost center'
    )
    
    # Computed Fields
    total_workorders = fields.Integer(
        string='Total Work Orders',
        compute='_compute_workorder_stats',
        help='Total number of work orders'
    )
    
    active_workorders = fields.Integer(
        string='Active Work Orders',
        compute='_compute_workorder_stats',
        help='Number of active work orders'
    )
    
    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for record in self:
            if record.parent_id:
                record.complete_name = '%s / %s' % (record.parent_id.complete_name, record.name)
            else:
                record.complete_name = record.name
    
    @api.depends('parent_id')
    def _compute_level(self):
        for record in self:
            level = 0
            parent = record.parent_id
            while parent:
                level += 1
                parent = parent.parent_id
            record.level = level
    
    @api.depends('budget_line_ids.allocated_amount', 'expense_ids.amount')
    def _compute_financial_totals(self):
        for record in self:
            record.budget_allocated = sum(record.budget_line_ids.mapped('allocated_amount'))
            record.budget_spent = sum(record.expense_ids.filtered(
                lambda e: e.state in ['confirmed', 'approved', 'paid']
            ).mapped('amount'))
            record.budget_remaining = record.budget_allocated - record.budget_spent
            
            if record.budget_allocated:
                record.budget_utilization = (record.budget_spent / record.budget_allocated) * 100
            else:
                record.budget_utilization = 0
    
    @api.depends('budget_line_ids.allocated_amount', 'expense_ids.amount')
    def _compute_company_currency_totals(self):
        for cost_center in self:
            total_allocated_company = 0
            total_spent_company = 0
            
            # Convert budget lines to company currency
            mixin = self.env['facilities.multi.currency.mixin']
            for line in cost_center.budget_line_ids:
                rate = mixin._get_exchange_rate(
                    line.currency_id,
                    cost_center.company_currency_id,
                    line.budget_id.start_date
                )
                total_allocated_company += line.allocated_amount * rate
            
            # Convert expenses to company currency
            for expense in cost_center.expense_ids.filtered(
                lambda e: e.state in ['confirmed', 'approved', 'paid']
            ):
                rate = mixin._get_exchange_rate(
                    expense.currency_id,
                    cost_center.company_currency_id,
                    expense.date
                )
                total_spent_company += expense.amount * rate
            
            cost_center.budget_allocated_company_currency = total_allocated_company
            cost_center.budget_spent_company_currency = total_spent_company
    
    @api.depends('workorder_ids')
    def _compute_workorder_stats(self):
        for record in self:
            record.total_workorders = len(record.workorder_ids)
            record.active_workorders = len(record.workorder_ids.filtered(
                lambda w: w.state in ['new', 'in_progress', 'pending']
            ))
    
    @api.constrains('parent_id')
    def _check_hierarchy(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive cost centers.'))
    
    @api.constrains('code')
    def _check_unique_code(self):
        for record in self:
            existing = self.search([
                ('code', '=', record.code),
                ('id', '!=', record.id),
                ('company_id', '=', record.company_id.id)
            ])
            if existing:
                raise ValidationError(_('Cost center code must be unique within the company.'))
    
    @api.constrains('analytic_account_id')
    def _check_unique_analytic_account(self):
        for record in self:
            existing = self.search([
                ('analytic_account_id', '=', record.analytic_account_id.id),
                ('id', '!=', record.id),
                ('company_id', '=', record.company_id.id)
            ])
            if existing:
                raise ValidationError(_('Each analytic account can only be linked to one cost center per company.'))
    
    def name_get(self):
        result = []
        for record in self:
            name = '[%s] %s' % (record.code, record.complete_name)
            result.append((record.id, name))
        return result
    
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', operator, name), ('complete_name', operator, name)]
        records = self.search(domain + args, limit=limit)
        return records.name_get()
    
    def action_view_budget_lines(self):
        """Action to view budget lines for this cost center"""
        return {
            'name': _('Budget Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.line',
            'view_mode': 'list,form',
            'domain': [('cost_center_id', '=', self.id)],
            'context': {'default_cost_center_id': self.id}
        }
    
    def action_view_expenses(self):
        """Action to view expenses for this cost center"""
        return {
            'name': _('Expenses'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.expense',
            'view_mode': 'list,form',
            'domain': [('cost_center_id', '=', self.id)],
            'context': {'default_cost_center_id': self.id}
        }
    
    def action_view_workorders(self):
        """Action to view work orders for this cost center"""
        return {
            'name': _('Work Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,form,kanban',
            'domain': [('cost_center_id', '=', self.id)],
            'context': {'default_cost_center_id': self.id}
        }


class ExpenseCategory(models.Model):
    _name = 'facilities.expense.category'
    _description = 'Expense Category'
    _order = 'name'

    name = fields.Char(
        string='Category Name',
        required=True,
        help='Name of the expense category'
    )
    
    code = fields.Char(
        string='Category Code',
        required=True,
        help='Unique code for the category'
    )
    
    description = fields.Text(
        string='Description',
        help='Category description'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this category is active'
    )
    
    parent_id = fields.Many2one(
        'facilities.expense.category',
        string='Parent Category',
        help='Parent category for hierarchy'
    )
    
    child_ids = fields.One2many(
        'facilities.expense.category',
        'parent_id',
        string='Sub Categories',
        help='Sub categories'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    # Related Records
    budget_line_ids = fields.One2many(
        'facilities.budget.line',
        'category_id',
        string='Budget Lines',
        help='Budget lines using this category'
    )
    
    expense_ids = fields.One2many(
        'facilities.budget.expense',
        'category_id',
        string='Expenses',
        help='Expenses using this category'
    )
    
    # Statistics
    total_budget = fields.Monetary(
        string='Total Budget',
        currency_field='currency_id',
        compute='_compute_totals',
        help='Total budget allocated for this category'
    )
    
    total_spent = fields.Monetary(
        string='Total Spent',
        currency_field='currency_id',
        compute='_compute_totals',
        help='Total amount spent in this category'
    )
    
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    @api.depends('budget_line_ids.allocated_amount', 'expense_ids.amount')
    def _compute_totals(self):
        for category in self:
            category.total_budget = sum(category.budget_line_ids.mapped('allocated_amount'))
            category.total_spent = sum(category.expense_ids.filtered(
                lambda e: e.state in ['confirmed', 'approved', 'paid']
            ).mapped('amount'))
    
    @api.constrains('parent_id')
    def _check_hierarchy(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive expense categories.'))
    
    @api.constrains('code')
    def _check_unique_code(self):
        for record in self:
            existing = self.search([
                ('code', '=', record.code),
                ('id', '!=', record.id),
                ('company_id', '=', record.company_id.id)
            ])
            if existing:
                raise ValidationError(_('Expense category code must be unique within the company.'))
    
    def name_get(self):
        result = []
        for record in self:
            name = '[%s] %s' % (record.code, record.name)
            result.append((record.id, name))
        return result
    
    def action_view_budget_lines(self):
        """View budget lines for this category"""
        return {
            'name': _('Budget Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.line',
            'view_mode': 'list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id}
        }
    
    def action_view_expenses(self):
        """View expenses for this category"""
        return {
            'name': _('Expenses'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.expense',
            'view_mode': 'list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id}
        }