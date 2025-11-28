# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class BudgetVsActualReport(models.Model):
    _name = 'facilities.budget.vs.actual.report'
    _description = 'Budget vs Actual Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc'

    name = fields.Char(
        string='Report Name',
        required=True,
        default='Budget vs Actual Report',
        help='Name of the report'
    )
    
    date_from = fields.Date(
        string='From Date',
        required=True,
        default=fields.Date.today,
        help='Start date for the report period'
    )
    
    date_to = fields.Date(
        string='To Date',
        required=True,
        default=fields.Date.today,
        help='End date for the report period'
    )
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        help='Filter by specific analytic account (cost center)'
    )
    
    cost_center_id = fields.Many2one(
        'facilities.cost.center',
        string='Cost Center',
        help='Filter by specific cost center'
    )
    
    budget_id = fields.Many2one(
        'facilities.financial.budget',
        string='Budget',
        help='Filter by specific budget'
    )
    
    category_id = fields.Many2one(
        'facilities.expense.category',
        string='Expense Category',
        help='Filter by specific expense category'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
    ], default='draft', string='Status')
    
    # Report Lines
    report_line_ids = fields.One2many(
        'facilities.budget.vs.actual.report.line',
        'report_id',
        string='Report Lines',
        help='Detailed report lines'
    )
    
    # Summary Fields - Computed from report lines
    total_budget_allocated = fields.Monetary(
        string='Total Budget Allocated',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
        help='Total budget allocated for the period'
    )
    
    total_actual_spent = fields.Monetary(
        string='Total Actual Spent',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
        help='Total actual amount spent for the period'
    )
    
    total_variance = fields.Monetary(
        string='Total Variance',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
        help='Total variance (Budget - Actual)'
    )
    
    variance_percentage = fields.Float(
        string='Variance %',
        compute='_compute_totals',
        store=True,
        help='Variance percentage'
    )
    
    utilization_percentage = fields.Float(
        string='Budget Utilization %',
        compute='_compute_utilization_percentage',
        store=False,
        help='Budget utilization percentage'
    )
    
    @api.depends('report_line_ids.budget_allocated', 'report_line_ids.actual_spent')
    def _compute_totals(self):
        for report in self:
            report.total_budget_allocated = sum(report.report_line_ids.mapped('budget_allocated'))
            report.total_actual_spent = sum(report.report_line_ids.mapped('actual_spent'))
            report.total_variance = report.total_budget_allocated - report.total_actual_spent
            
            # Debug logging
            _logger.info(f"Budget vs Actual Report {report.id} - Budget: {report.total_budget_allocated}, Actual: {report.total_actual_spent}")
            
            if report.total_budget_allocated:
                # Variance percentage: (variance / budget) - store as decimal (0-1 range)
                report.variance_percentage = report.total_variance / report.total_budget_allocated
                
                # Debug logging
                _logger.info(f"Calculated - Variance %: {report.variance_percentage}")
            else:
                report.variance_percentage = 0
    
    @api.depends('total_budget_allocated', 'total_actual_spent')
    def _compute_utilization_percentage(self):
        for report in self:
            if report.total_budget_allocated:
                # Utilization percentage: (actual_spent / budget) - store as decimal (0-1 range)
                report.utilization_percentage = report.total_actual_spent / report.total_budget_allocated
            else:
                report.utilization_percentage = 0
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to:
                if record.date_from > record.date_to:
                    raise ValidationError(_('End date must be after start date.'))
    
    def action_generate_report(self):
        """Generate the budget vs actual report"""
        self.ensure_one()
        
        # Clear existing lines
        self.report_line_ids.unlink()
        
        # Build domain for budget lines - be more flexible with budget states
        budget_domain = [
            ('budget_id.start_date', '<=', self.date_to),
            ('budget_id.end_date', '>=', self.date_from),
            ('budget_id.state', 'in', ['draft', 'confirmed', 'approved', 'active']),  # Include draft state too
        ]
        
        if self.analytic_account_id:
            budget_domain.append(('analytic_account_id', '=', self.analytic_account_id.id))
        if self.cost_center_id:
            budget_domain.append(('cost_center_id', '=', self.cost_center_id.id))
        if self.budget_id:
            budget_domain.append(('budget_id', '=', self.budget_id.id))
        if self.category_id:
            budget_domain.append(('category_id', '=', self.category_id.id))
        
        budget_lines = self.env['facilities.budget.line'].search(budget_domain)
        
        # If no budget lines found with date restrictions, try without date restrictions
        if not budget_lines:
            _logger.warning("No budget lines found with date restrictions, trying without date restrictions")
            budget_domain_no_date = [('budget_id.state', 'in', ['draft', 'confirmed', 'approved', 'active'])]
            
            if self.analytic_account_id:
                budget_domain_no_date.append(('analytic_account_id', '=', self.analytic_account_id.id))
            if self.cost_center_id:
                budget_domain_no_date.append(('cost_center_id', '=', self.cost_center_id.id))
            if self.budget_id:
                budget_domain_no_date.append(('budget_id', '=', self.budget_id.id))
            if self.category_id:
                budget_domain_no_date.append(('category_id', '=', self.category_id.id))
            
            budget_lines = self.env['facilities.budget.line'].search(budget_domain_no_date)
            _logger.info(f"Found {len(budget_lines)} budget lines without date restrictions")
        
        # Debug: Log what we found
        _logger.info(f"Found {len(budget_lines)} budget lines for report generation")
        for line in budget_lines:
            _logger.info(f"Budget line: {line.budget_id.name} - {line.analytic_account_id.name} - {line.category_id.name} - {line.allocated_amount}")
        
        # Group by analytic account and category
        report_data = {}
        
        for budget_line in budget_lines:
            key = (budget_line.analytic_account_id.id, budget_line.category_id.id)
            
            if key not in report_data:
                report_data[key] = {
                    'analytic_account_id': budget_line.analytic_account_id.id,
                    'cost_center_id': budget_line.cost_center_id.id if budget_line.cost_center_id else False,
                    'category_id': budget_line.category_id.id,
                    'budget_allocated': 0,
                    'actual_spent': 0,
                }
            
            report_data[key]['budget_allocated'] += budget_line.allocated_amount
        
        # Get actual expenses for the period
        expense_domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', 'in', ['confirmed', 'approved', 'paid']),
        ]
        
        if self.analytic_account_id:
            expense_domain.append(('analytic_account_id', '=', self.analytic_account_id.id))
        if self.cost_center_id:
            expense_domain.append(('cost_center_id', '=', self.cost_center_id.id))
        if self.budget_id:
            expense_domain.append(('budget_id', '=', self.budget_id.id))
        if self.category_id:
            expense_domain.append(('category_id', '=', self.category_id.id))
        
        expenses = self.env['facilities.budget.expense'].search(expense_domain)
        
        # If no expenses found with date restrictions, try without date restrictions
        if not expenses:
            _logger.warning("No expenses found with date restrictions, trying without date restrictions")
            expense_domain_no_date = [('state', 'in', ['confirmed', 'approved', 'paid'])]
            
            if self.analytic_account_id:
                expense_domain_no_date.append(('analytic_account_id', '=', self.analytic_account_id.id))
            if self.cost_center_id:
                expense_domain_no_date.append(('cost_center_id', '=', self.cost_center_id.id))
            if self.budget_id:
                expense_domain_no_date.append(('budget_id', '=', self.budget_id.id))
            if self.category_id:
                expense_domain_no_date.append(('category_id', '=', self.category_id.id))
            
            expenses = self.env['facilities.budget.expense'].search(expense_domain_no_date)
            _logger.info(f"Found {len(expenses)} expenses without date restrictions")
        
        # Debug: Log what we found
        _logger.info(f"Found {len(expenses)} expenses for report generation")
        for expense in expenses:
            _logger.info(f"Expense: {expense.analytic_account_id.name} - {expense.category_id.name} - {expense.amount} - {expense.state}")
        
        for expense in expenses:
            key = (expense.analytic_account_id.id, expense.category_id.id)
            
            if key not in report_data:
                report_data[key] = {
                    'analytic_account_id': expense.analytic_account_id.id,
                    'cost_center_id': expense.cost_center_id.id if expense.cost_center_id else False,
                    'category_id': expense.category_id.id,
                    'budget_allocated': 0,
                    'actual_spent': 0,
                }
            
            report_data[key]['actual_spent'] += expense.amount
        
        # Debug: Log report data
        _logger.info(f"Report data keys: {list(report_data.keys())}")
        for key, data in report_data.items():
            _logger.info(f"Report data for key {key}: {data}")
        
        # Debug: Log totals before creating lines
        total_budget = sum(data['budget_allocated'] for data in report_data.values())
        total_actual = sum(data['actual_spent'] for data in report_data.values())
        _logger.info(f"Total budget before lines: {total_budget}, Total actual before lines: {total_actual}")
        
        # Create report lines
        report_line_count = 0
        for key, data in report_data.items():
            variance = data['budget_allocated'] - data['actual_spent']
            # Variance percentage: (variance / budget) - store as decimal (0-1 range)
            variance_percentage = (variance / data['budget_allocated']) if data['budget_allocated'] else 0
            # Utilization percentage: (actual_spent / budget) - store as decimal (0-1 range)
            utilization_percentage = (data['actual_spent'] / data['budget_allocated']) if data['budget_allocated'] else 0
            
            # Determine status indicator
            if data['budget_allocated'] == 0:
                if data['actual_spent'] > 0:
                    status = 'no_budget'
                else:
                    status = 'no_spending'
            elif data['actual_spent'] == 0:
                status = 'no_spending'
            elif abs(variance_percentage) <= 5:  # Within 5% tolerance
                status = 'on_budget'
            elif variance_percentage > 0:
                status = 'under_budget'
            else:
                status = 'over_budget'
            
            try:
                report_line = self.env['facilities.budget.vs.actual.report.line'].create({
                    'report_id': self.id,
                    'analytic_account_id': data['analytic_account_id'],
                    'cost_center_id': data['cost_center_id'],
                    'category_id': data['category_id'],
                    'budget_allocated': data['budget_allocated'],
                    'actual_spent': data['actual_spent'],
                    'variance': variance,
                    'variance_percentage': variance_percentage,
                    'utilization_percentage': utilization_percentage,
                    'status_indicator': status,
                })
                report_line_count += 1
                _logger.info(f"Created report line: {report_line.id}")
            except Exception as e:
                _logger.error(f"Error creating report line: {e}")
                _logger.error(f"Data: {data}")
        
        _logger.info(f"Created {report_line_count} report lines")
        
        # If no report lines were created, create a placeholder to show what's happening
        if report_line_count == 0:
            _logger.warning("No report lines created. This might indicate:")
            _logger.warning("1. No budget lines found for the criteria")
            _logger.warning("2. No expenses found for the criteria")
            _logger.warning("3. Budget lines and expenses don't have matching analytic accounts/categories")
            
            # Create a placeholder line to show the issue (only if we have required fields)
            if self.analytic_account_id and self.category_id:
                try:
                    self.env['facilities.budget.vs.actual.report.line'].create({
                        'report_id': self.id,
                        'analytic_account_id': self.analytic_account_id.id,
                        'cost_center_id': self.cost_center_id.id if self.cost_center_id else False,
                        'category_id': self.category_id.id,
                        'budget_allocated': 0,
                        'actual_spent': 0,
                        'variance': 0,
                        'variance_percentage': 0,
                        'utilization_percentage': 0,
                        'status_indicator': 'no_spending',
                    })
                    _logger.info("Created placeholder report line")
                except Exception as e:
                    _logger.error(f"Error creating placeholder report line: {e}")
            else:
                _logger.warning("Cannot create placeholder report line - missing required analytic_account_id or category_id")
        
        self.write({'state': 'generated'})
        
        # Force recalculation of totals
        self._compute_totals()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def action_view_workorders(self):
        """View work orders contributing to actual costs"""
        domain = []
        
        if self.analytic_account_id:
            domain.append(('analytic_account_id', '=', self.analytic_account_id.id))
        if self.cost_center_id:
            domain.append(('cost_center_id', '=', self.cost_center_id.id))
        
        # Add date filter for work orders completed in the period
        domain.extend([
            ('actual_end_date', '>=', self.date_from),
            ('actual_end_date', '<=', self.date_to),
            ('state', '=', 'done'),
        ])
        
        return {
            'name': _('Related Work Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,form,kanban',
            'domain': domain,
            'context': {'default_analytic_account_id': self.analytic_account_id.id}
        }
    
    def action_export_excel(self):
        """Export budget vs actual report to Excel"""
        self.ensure_one()
        
        # This would typically use a report action or custom export logic
        # For now, we'll create a simple action that could be extended
        return {
            'name': _('Export to Excel'),
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def action_send_email(self):
        """Send budget vs actual report via email"""
        self.ensure_one()
        
        template = self.env.ref('facilities_management.email_template_budget_vs_actual_report', False)
        if template:
            template.send_mail(self.id, force_send=True)
        else:
            # Fallback to basic email composition
            return {
                'name': _('Send Email'),
                'type': 'ir.actions.act_window',
                'res_model': 'mail.compose.message',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_model': 'facilities.budget.vs.actual.report',
                    'default_res_id': self.id,
                    'default_subject': _('Budget vs Actual Report: %s') % self.name,
                }
            }
    
    def action_duplicate_report(self):
        """Duplicate this report with new dates"""
        self.ensure_one()
        
        new_report = self.copy({
            'name': _('%s (Copy)') % self.name,
            'state': 'draft',
            'report_line_ids': False,
        })
        
        return {
            'name': _('Budget vs Actual Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.vs.actual.report',
            'res_id': new_report.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_compare_with_previous_period(self):
        """Compare with previous period of same duration"""
        self.ensure_one()
        
        # Calculate previous period dates
        period_days = (self.date_to - self.date_from).days + 1
        prev_date_to = self.date_from - timedelta(days=1)
        prev_date_from = prev_date_to - timedelta(days=period_days - 1)
        
        # Create comparison report
        comparison_report = self.env['facilities.budget.vs.actual.report'].create({
            'name': _('Comparison: %s vs Previous Period') % self.name,
            'date_from': prev_date_from,
            'date_to': prev_date_to,
            'analytic_account_id': self.analytic_account_id.id,
            'cost_center_id': self.cost_center_id.id,
            'budget_id': self.budget_id.id,
            'category_id': self.category_id.id,
        })
        
        # Generate the comparison report
        comparison_report.action_generate_report()
        
        return {
            'name': _('Previous Period Comparison'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.vs.actual.report',
            'res_id': comparison_report.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    


class BudgetVsActualReportLine(models.Model):
    _name = 'facilities.budget.vs.actual.report.line'
    _description = 'Budget vs Actual Report Line'
    _order = 'analytic_account_id, category_id'

    report_id = fields.Many2one(
        'facilities.budget.vs.actual.report',
        string='Report',
        required=True,
        ondelete='cascade'
    )
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        required=True,
        help='Analytic account (cost center) for this line'
    )
    
    cost_center_id = fields.Many2one(
        'facilities.cost.center',
        string='Cost Center',
        help='Cost center for this line'
    )
    
    category_id = fields.Many2one(
        'facilities.expense.category',
        string='Expense Category',
        required=True,
        help='Expense category for this line'
    )
    
    budget_allocated = fields.Monetary(
        string='Budget Allocated',
        currency_field='currency_id',
        required=True,
        help='Budget allocated for this analytic account and category'
    )
    
    actual_spent = fields.Monetary(
        string='Actual Spent',
        currency_field='currency_id',
        required=True,
        help='Actual amount spent for this analytic account and category'
    )
    
    variance = fields.Monetary(
        string='Variance',
        currency_field='currency_id',
        compute='_compute_variance',
        store=True,
        help='Variance (Budget - Actual)'
    )
    
    variance_percentage = fields.Float(
        string='Variance %',
        compute='_compute_variance',
        store=True,
        help='Variance percentage'
    )
    
    utilization_percentage = fields.Float(
        string='Utilization %',
        compute='_compute_utilization_percentage',
        store=False,
        help='Budget utilization percentage'
    )
    
    currency_id = fields.Many2one(
        related='report_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    # Status indicators
    status_indicator = fields.Selection([
        ('under_budget', 'Under Budget'),
        ('on_budget', 'On Budget'),
        ('over_budget', 'Over Budget'),
        ('no_budget', 'No Budget'),
        ('no_spending', 'No Spending'),
    ], string='Status', compute='_compute_status_indicator', store=True)
    
    @api.depends('budget_allocated', 'actual_spent')
    def _compute_variance(self):
        for line in self:
            line.variance = line.budget_allocated - line.actual_spent
            
            if line.budget_allocated:
                # Variance percentage: (variance / budget) - store as decimal (0-1 range)
                line.variance_percentage = line.variance / line.budget_allocated
                # Utilization percentage: (actual_spent / budget) - store as decimal (0-1 range)
                line.utilization_percentage = line.actual_spent / line.budget_allocated
            else:
                line.variance_percentage = 0
                line.utilization_percentage = 0
    
    @api.depends('budget_allocated', 'actual_spent', 'variance_percentage')
    def _compute_status_indicator(self):
        for line in self:
            if line.budget_allocated == 0:
                if line.actual_spent > 0:
                    line.status_indicator = 'no_budget'
                else:
                    line.status_indicator = 'no_spending'
            elif line.actual_spent == 0:
                line.status_indicator = 'no_spending'
            elif abs(line.variance_percentage) <= 5:  # Within 5% tolerance
                line.status_indicator = 'on_budget'
            elif line.variance_percentage > 0:
                line.status_indicator = 'under_budget'
            else:
                line.status_indicator = 'over_budget'
    
    def action_view_budget_lines(self):
        """View budget lines for this analytic account and category"""
        return {
            'name': _('Budget Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.line',
            'view_mode': 'list,form',
            'domain': [
                ('analytic_account_id', '=', self.analytic_account_id.id),
                ('category_id', '=', self.category_id.id),
            ],
        }
    
    def action_view_expenses(self):
        """View expenses for this analytic account and category"""
        return {
            'name': _('Expenses'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.expense',
            'view_mode': 'list,form',
            'domain': [
                ('analytic_account_id', '=', self.analytic_account_id.id),
                ('category_id', '=', self.category_id.id),
                ('date', '>=', self.report_id.date_from),
                ('date', '<=', self.report_id.date_to),
                ('state', 'in', ['confirmed', 'approved', 'paid']),
            ],
        }
    
    def action_view_workorders(self):
        """View work orders contributing to expenses for this line"""
        expense_ids = self.env['facilities.budget.expense'].search([
            ('analytic_account_id', '=', self.analytic_account_id.id),
            ('category_id', '=', self.category_id.id),
            ('date', '>=', self.report_id.date_from),
            ('date', '<=', self.report_id.date_to),
            ('state', 'in', ['confirmed', 'approved', 'paid']),
            ('workorder_id', '!=', False),
        ]).mapped('workorder_id')
        
        return {
            'name': _('Related Work Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,form,kanban',
            'domain': [('id', 'in', expense_ids.ids)],
        }
