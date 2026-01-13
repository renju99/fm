# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class FinancialBudget(models.Model):
    _name = 'facilities.financial.budget'
    _description = 'Financial Budget Management'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'facilities.multi.currency.mixin']
    _order = 'fiscal_year desc, name'

    name = fields.Char(
        string='Budget Name',
        required=True,
        tracking=True,
        help='Name of the budget plan'
    )
    
    code = fields.Char(
        string='Budget Code',
        required=True,
        tracking=True,
        help='Unique code for the budget'
    )
    
    fiscal_year = fields.Char(
        string='Fiscal Year',
        required=True,
        tracking=True,
        help='Fiscal year for this budget'
    )
    
    start_date = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
        help='Budget period start date'
    )
    
    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
        help='Budget period end date'
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True, string='Status')
    
    total_budget = fields.Monetary(
        string='Total Budget',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
        help='Total allocated budget amount'
    )
    
    total_allocated = fields.Monetary(
        string='Total Allocated',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
        help='Total amount allocated to cost centers'
    )
    
    total_spent = fields.Monetary(
        string='Total Spent',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
        help='Total amount spent from this budget'
    )
    
    remaining_budget = fields.Monetary(
        string='Remaining Budget',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
        help='Remaining budget amount'
    )
    
    utilization_percentage = fields.Float(
        string='Utilization %',
        compute='_compute_totals',
        store=True,
        help='Budget utilization percentage'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )
    
    cost_center_id = fields.Many2one(
        'facilities.cost.center',
        string='Primary Cost Center',
        help='Primary cost center for this budget'
    )
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        required=True,
        tracking=True,
        help='Analytic account for budget tracking and cost analysis'
    )
    
    budget_line_ids = fields.One2many(
        'facilities.budget.line',
        'budget_id',
        string='Budget Lines',
        help='Budget allocation lines'
    )
    
    expense_line_ids = fields.One2many(
        'facilities.budget.expense',
        'budget_id',
        string='Expenses',
        help='Expenses charged to this budget'
    )
    
    description = fields.Text(
        string='Description',
        help='Budget description and notes'
    )
    
    manager_id = fields.Many2one(
        'res.users',
        string='Budget Manager',
        required=True,
        default=lambda self: self.env.user,
        tracking=True
    )
    
    approval_required = fields.Boolean(
        string='Approval Required',
        default=True,
        help='Requires approval before activation'
    )
    
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        tracking=True
    )
    
    approved_date = fields.Datetime(
        string='Approval Date',
        readonly=True,
        tracking=True
    )
    
    # Multi-currency fields
    total_budget_company_currency = fields.Monetary(
        string='Total Budget (Company Currency)',
        currency_field='company_currency_id',
        compute='_compute_company_currency_totals',
        store=True,
        help='Total budget in company currency'
    )
    
    total_spent_company_currency = fields.Monetary(
        string='Total Spent (Company Currency)',
        currency_field='company_currency_id',
        compute='_compute_company_currency_totals',
        store=True,
        help='Total spent in company currency'
    )
    
    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Company Currency',
        readonly=True
    )
    
    @api.depends('budget_line_ids.allocated_amount', 'expense_line_ids.amount')
    def _compute_totals(self):
        for record in self:
            record.total_allocated = sum(record.budget_line_ids.mapped('allocated_amount'))
            record.total_spent = sum(record.expense_line_ids.mapped('amount'))
            record.total_budget = record.total_allocated
            record.remaining_budget = record.total_allocated - record.total_spent
            
            if record.total_allocated:
                record.utilization_percentage = (record.total_spent / record.total_allocated) * 100
            else:
                record.utilization_percentage = 0
    
    @api.depends('budget_line_ids.allocated_amount', 'expense_line_ids.amount', 'currency_id')
    def _compute_company_currency_totals(self):
        for budget in self:
            total_budget_company = 0
            total_spent_company = 0
            
            # Convert budget lines to company currency
            for line in budget.budget_line_ids:
                rate = budget._get_exchange_rate(
                    budget.currency_id,
                    budget.company_currency_id,
                    budget.start_date
                )
                total_budget_company += line.allocated_amount * rate
            
            # Convert expenses to company currency
            for expense in budget.expense_line_ids:
                rate = budget._get_exchange_rate(
                    budget.currency_id,
                    budget.company_currency_id,
                    expense.date
                )
                total_spent_company += expense.amount * rate
            
            budget.total_budget_company_currency = total_budget_company
            budget.total_spent_company_currency = total_spent_company
    
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date:
                if record.start_date >= record.end_date:
                    raise ValidationError(_('End date must be after start date.'))
    
    @api.constrains('code')
    def _check_unique_code(self):
        for record in self:
            existing = self.search([
                ('code', '=', record.code),
                ('id', '!=', record.id),
                ('company_id', '=', record.company_id.id)
            ])
            if existing:
                raise ValidationError(_('Budget code must be unique within the company.'))
    
    def action_confirm(self):
        self.write({'state': 'confirmed'})
        self.message_post(body=_('Budget confirmed'))
    
    def action_approve(self):
        if self.approval_required and not self.env.user.has_group('fm.group_facilities_manager'):
            raise UserError(_('Only facilities managers can approve budgets.'))
        
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approved_date': fields.Datetime.now()
        })
        self.message_post(body=_('Budget approved by %s') % self.env.user.name)
    
    def action_activate(self):
        if self.state != 'approved':
            raise UserError(_('Budget must be approved before activation.'))
        
        self.write({'state': 'active'})
        self.message_post(body=_('Budget activated'))
    
    def action_close(self):
        self.write({'state': 'closed'})
        self.message_post(body=_('Budget closed'))
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
        self.message_post(body=_('Budget cancelled'))
    
    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
        self.message_post(body=_('Budget reset to draft'))
    
    def action_view_budget_lines(self):
        """Action to view budget lines for this budget"""
        return {
            'name': _('Budget Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.line',
            'view_mode': 'list,form',
            'domain': [('budget_id', '=', self.id)],
            'context': {'default_budget_id': self.id}
        }
    
    def action_view_expenses(self):
        """Action to view expenses for this budget"""
        return {
            'name': _('Budget Expenses'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.expense',
            'view_mode': 'list,form',
            'domain': [('budget_id', '=', self.id)],
            'context': {'default_budget_id': self.id}
        }


class BudgetLine(models.Model):
    _name = 'facilities.budget.line'
    _description = 'Budget Line Item'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    
    budget_id = fields.Many2one(
        'facilities.financial.budget',
        string='Budget',
        required=True,
        ondelete='cascade'
    )
    
    cost_center_id = fields.Many2one(
        'facilities.cost.center',
        string='Cost Center',
        help='Cost center for this budget line'
    )
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        required=True,
        help='Analytic account for this budget line - primary budget tracking dimension'
    )
    
    category_id = fields.Many2one(
        'facilities.expense.category',
        string='Expense Category',
        required=True,
        help='Category of expenses for this line'
    )
    
    allocated_amount = fields.Monetary(
        string='Allocated Amount',
        currency_field='currency_id',
        required=True,
        help='Amount allocated for this line'
    )
    
    spent_amount = fields.Monetary(
        string='Spent Amount',
        currency_field='currency_id',
        compute='_compute_spent_amount',
        store=True,
        help='Amount spent from this line'
    )
    
    remaining_amount = fields.Monetary(
        string='Remaining Amount',
        currency_field='currency_id',
        compute='_compute_spent_amount',
        store=True,
        help='Remaining amount for this line'
    )
    
    utilization_percentage = fields.Float(
        string='Utilization %',
        compute='_compute_spent_amount',
        store=True,
        help='Utilization percentage for this line'
    )
    
    currency_id = fields.Many2one(
        related='budget_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    description = fields.Text(
        string='Description',
        help='Description for this budget line'
    )
    
    @api.depends('allocated_amount', 'budget_id.expense_line_ids.amount')
    def _compute_spent_amount(self):
        for line in self:
            expenses = line.budget_id.expense_line_ids.filtered(
                lambda e: e.analytic_account_id == line.analytic_account_id and 
                         e.category_id == line.category_id
            )
            line.spent_amount = sum(expenses.mapped('amount'))
            line.remaining_amount = line.allocated_amount - line.spent_amount
            
            if line.allocated_amount:
                line.utilization_percentage = (line.spent_amount / line.allocated_amount) * 100
            else:
                line.utilization_percentage = 0
    
    @api.onchange('cost_center_id')
    def _onchange_cost_center_id(self):
        """Automatically set analytic account from cost center"""
        if self.cost_center_id and self.cost_center_id.analytic_account_id:
            self.analytic_account_id = self.cost_center_id.analytic_account_id
        elif not self.cost_center_id:
            self.analytic_account_id = False


class BudgetExpense(models.Model):
    _name = 'facilities.budget.expense'
    _description = 'Budget Expense Entry'
    _order = 'date desc, id desc'
    _sql_constraints = [
        ('unique_workorder_category', 
         'UNIQUE(workorder_id, category_id)', 
         'Only one budget expense per work order per category is allowed.')
    ]

    budget_id = fields.Many2one(
        'facilities.financial.budget',
        string='Budget',
        required=True,
        ondelete='cascade'
    )
    
    cost_center_id = fields.Many2one(
        'facilities.cost.center',
        string='Cost Center',
        help='Cost center for this expense'
    )
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        required=True,
        help='Analytic account for this expense - primary budget tracking dimension'
    )
    
    category_id = fields.Many2one(
        'facilities.expense.category',
        string='Expense Category',
        required=True,
        help='Category of this expense'
    )
    
    date = fields.Date(
        string='Expense Date',
        required=True,
        default=fields.Date.today,
        help='Date of the expense'
    )
    
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        required=True,
        help='Expense amount'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='budget_id.currency_id',
        string='Currency',
        readonly=True,
        store=True
    )
    
    reference = fields.Char(
        string='Reference',
        help='Reference document or number'
    )
    
    description = fields.Text(
        string='Description',
        required=True,
        help='Expense description'
    )
    
    workorder_id = fields.Many2one(
        'facilities.workorder',
        string='Related Work Order',
        help='Work order related to this expense'
    )
    
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        domain=[('is_company', '=', True), ('supplier_rank', '>', 0)],
        help='Vendor for this expense'
    )
    
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        help='Related invoice'
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('approved', 'Approved'),
        ('paid', 'Paid')
    ], default='draft', string='Status')
    
    # Multi-currency fields
    original_currency_id = fields.Many2one(
        'res.currency',
        string='Original Currency',
        help='Original currency of the expense'
    )
    
    original_amount = fields.Monetary(
        string='Original Amount',
        currency_field='original_currency_id',
        help='Original amount in original currency'
    )
    
    amount_company_currency = fields.Monetary(
        string='Amount (Company Currency)',
        currency_field='company_currency_id',
        compute='_compute_company_currency_amount',
        store=True,
        help='Amount in company currency'
    )
    
    company_currency_id = fields.Many2one(
        related='budget_id.company_currency_id',
        string='Company Currency',
        readonly=True
    )
    
    @api.constrains('amount', 'budget_id', 'analytic_account_id', 'category_id')
    def _check_budget_availability(self):
        for expense in self:
            if expense.state in ['confirmed', 'approved', 'paid']:
                budget_line = expense.budget_id.budget_line_ids.filtered(
                    lambda l: l.analytic_account_id == expense.analytic_account_id and 
                             l.category_id == expense.category_id
                )
                if budget_line:
                    if expense.amount > budget_line.remaining_amount:
                        raise ValidationError(_(
                            'Expense amount exceeds available budget for %s - %s. '
                            'Available: %s, Requested: %s'
                        ) % (
                            expense.analytic_account_id.name,
                            expense.category_id.name,
                            budget_line.remaining_amount,
                            expense.amount
                        ))
    
    @api.constrains('amount')
    def _check_expense_amount(self):
        """Validate expense amounts."""
        for expense in self:
            if expense.amount and expense.amount <= 0:
                raise ValidationError(_("Expense amount must be greater than 0."))
            if expense.amount and expense.amount > 10000000:  # 10 million
                raise ValidationError(_("Expense amount seems unrealistic. Please verify this value."))
    
    @api.constrains('state', 'amount', 'budget_id')
    def _check_budget_line_allocation(self):
        """Ensure expenses are properly allocated to budget lines."""
        for expense in self:
            if expense.state in ['confirmed', 'approved', 'paid'] and expense.budget_id:
                if not expense.analytic_account_id:
                    raise ValidationError(_("Analytic account is required for budget-controlled expenses."))
                if not expense.category_id:
                    raise ValidationError(_("Category is required for budget-controlled expenses."))
    
    @api.constrains('date')
    def _check_expense_date_within_budget_period(self):
        """Ensure expense date falls within budget period."""
        for expense in self:
            if expense.date and expense.budget_id:
                if expense.date < expense.budget_id.start_date or expense.date > expense.budget_id.end_date:
                    raise ValidationError(_("Expense date must fall within the budget period (%s to %s).") % 
                                        (expense.budget_id.start_date, expense.budget_id.end_date))
    
    @api.constrains('budget_id', 'analytic_account_id', 'category_id')
    def _check_budget_line_exists(self):
        """Ensure a budget line exists for the expense allocation."""
        for expense in self:
            if expense.budget_id and expense.analytic_account_id and expense.category_id:
                budget_line = expense.budget_id.budget_line_ids.filtered(
                    lambda l: l.analytic_account_id == expense.analytic_account_id and 
                             l.category_id == expense.category_id
                )
                if not budget_line:
                    raise ValidationError(_("No budget line found for analytic account '%s' and category '%s' in budget '%s'.") % 
                                        (expense.analytic_account_id.name, expense.category_id.name, expense.budget_id.name))
    
    @api.depends('amount', 'currency_id', 'date')
    def _compute_company_currency_amount(self):
        mixin = self.env['facilities.multi.currency.mixin']
        for expense in self:
            if expense.currency_id and expense.budget_id.company_currency_id:
                rate = mixin._get_exchange_rate(
                    expense.currency_id,
                    expense.budget_id.company_currency_id,
                    expense.date
                )
                expense.amount_company_currency = expense.amount * rate
            else:
                expense.amount_company_currency = expense.amount
    
    @api.onchange('original_currency_id', 'original_amount', 'date')
    def _onchange_original_amount(self):
        """Convert original amount to budget currency"""
        mixin = self.env['facilities.multi.currency.mixin']
        if self.original_currency_id and self.original_amount and self.currency_id:
            if self.original_currency_id != self.currency_id:
                rate = mixin._get_exchange_rate(
                    self.original_currency_id,
                    self.currency_id,
                    self.date
                )
                self.amount = self.original_amount * rate
            else:
                self.amount = self.original_amount
    
    @api.onchange('cost_center_id')
    def _onchange_cost_center_id(self):
        """Automatically set analytic account from cost center"""
        if self.cost_center_id and self.cost_center_id.analytic_account_id:
            self.analytic_account_id = self.cost_center_id.analytic_account_id
        elif not self.cost_center_id:
            self.analytic_account_id = False