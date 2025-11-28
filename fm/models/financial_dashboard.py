# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import logging

_logger = logging.getLogger(__name__)


class FinancialDashboard(models.Model):
    _name = 'facilities.financial.dashboard'
    _description = 'Financial Dashboard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Dashboard Name',
        required=True,
        help='Name of the financial dashboard'
    )
    
    description = fields.Text(
        string='Description',
        help='Dashboard description'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this dashboard is active'
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
    
    # Dashboard Configuration
    period_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom Period')
    ], string='Period Type', default='monthly', required=True)
    
    start_date = fields.Date(
        string='Start Date',
        default=lambda self: fields.Date.today().replace(day=1),
        help='Dashboard period start date'
    )
    
    end_date = fields.Date(
        string='End Date',
        default=lambda self: fields.Date.today(),
        help='Dashboard period end date'
    )
    
    cost_center_ids = fields.Many2many(
        'facilities.cost.center',
        string='Cost Centers',
        help='Cost centers to include in dashboard'
    )
    
    category_ids = fields.Many2many(
        'facilities.expense.category',
        string='Expense Categories',
        help='Expense categories to include in dashboard'
    )
    
    # KPI Fields
    total_budget = fields.Monetary(
        string='Total Budget',
        currency_field='currency_id',
        compute='_compute_kpis',
        help='Total budget for the period'
    )
    
    total_spent = fields.Monetary(
        string='Total Spent',
        currency_field='currency_id',
        compute='_compute_kpis',
        help='Total amount spent in the period'
    )
    
    total_remaining = fields.Monetary(
        string='Total Remaining',
        currency_field='currency_id',
        compute='_compute_kpis',
        help='Total remaining budget'
    )
    
    budget_utilization = fields.Float(
        string='Budget Utilization %',
        compute='_compute_kpis',
        help='Overall budget utilization percentage'
    )
    
    variance_amount = fields.Monetary(
        string='Variance Amount',
        currency_field='currency_id',
        compute='_compute_kpis',
        help='Budget variance amount'
    )
    
    variance_percentage = fields.Float(
        string='Variance %',
        compute='_compute_kpis',
        help='Budget variance percentage'
    )
    
    # Chart Data
    budget_vs_actual_chart = fields.Text(
        string='Budget vs Actual Chart Data',
        compute='_compute_chart_data',
        help='JSON data for budget vs actual chart'
    )
    
    cost_center_breakdown_chart = fields.Text(
        string='Cost Center Breakdown Chart Data',
        compute='_compute_chart_data',
        help='JSON data for cost center breakdown chart'
    )
    
    category_breakdown_chart = fields.Text(
        string='Category Breakdown Chart Data',
        compute='_compute_chart_data',
        help='JSON data for category breakdown chart'
    )
    
    trend_analysis_chart = fields.Text(
        string='Trend Analysis Chart Data',
        compute='_compute_chart_data',
        help='JSON data for trend analysis chart'
    )
    
    @api.depends('start_date', 'end_date', 'cost_center_ids', 'category_ids')
    def _compute_kpis(self):
        for dashboard in self:
            domain = [
                ('date', '>=', dashboard.start_date),
                ('date', '<=', dashboard.end_date),
                ('state', 'in', ['confirmed', 'approved', 'paid'])
            ]
            
            if dashboard.cost_center_ids:
                domain.append(('cost_center_id', 'in', dashboard.cost_center_ids.ids))
            
            if dashboard.category_ids:
                domain.append(('category_id', 'in', dashboard.category_ids.ids))
            
            expenses = self.env['facilities.budget.expense'].search(domain)
            dashboard.total_spent = sum(expenses.mapped('amount'))
            
            # Get budget lines for the same criteria
            budget_domain = []
            if dashboard.cost_center_ids:
                budget_domain.append(('cost_center_id', 'in', dashboard.cost_center_ids.ids))
            if dashboard.category_ids:
                budget_domain.append(('category_id', 'in', dashboard.category_ids.ids))
            
            budget_lines = self.env['facilities.budget.line'].search(budget_domain)
            dashboard.total_budget = sum(budget_lines.mapped('allocated_amount'))
            dashboard.total_remaining = dashboard.total_budget - dashboard.total_spent
            
            if dashboard.total_budget:
                dashboard.budget_utilization = (dashboard.total_spent / dashboard.total_budget) * 100
                dashboard.variance_percentage = ((dashboard.total_spent - dashboard.total_budget) / dashboard.total_budget) * 100
            else:
                dashboard.budget_utilization = 0
                dashboard.variance_percentage = 0
            
            dashboard.variance_amount = dashboard.total_spent - dashboard.total_budget
    
    @api.depends('start_date', 'end_date', 'cost_center_ids', 'category_ids')
    def _compute_chart_data(self):
        for dashboard in self:
            # Budget vs Actual Chart
            budget_vs_actual_data = dashboard._get_budget_vs_actual_data()
            dashboard.budget_vs_actual_chart = json.dumps(budget_vs_actual_data)
            
            # Cost Center Breakdown Chart
            cost_center_data = dashboard._get_cost_center_breakdown_data()
            dashboard.cost_center_breakdown_chart = json.dumps(cost_center_data)
            
            # Category Breakdown Chart
            category_data = dashboard._get_category_breakdown_data()
            dashboard.category_breakdown_chart = json.dumps(category_data)
            
            # Trend Analysis Chart
            trend_data = dashboard._get_trend_analysis_data()
            dashboard.trend_analysis_chart = json.dumps(trend_data)
    
    def _get_budget_vs_actual_data(self):
        """Get budget vs actual comparison data"""
        data = {
            'labels': [],
            'datasets': [
                {
                    'label': 'Budget',
                    'data': [],
                    'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                    'borderColor': 'rgba(54, 162, 235, 1)',
                    'borderWidth': 1
                },
                {
                    'label': 'Actual',
                    'data': [],
                    'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                    'borderColor': 'rgba(255, 99, 132, 1)',
                    'borderWidth': 1
                }
            ]
        }
        
        # Group by cost center or category based on dashboard configuration
        if self.cost_center_ids:
            for cost_center in self.cost_center_ids:
                data['labels'].append(cost_center.name)
                
                # Get budget for this cost center
                budget_lines = self.env['facilities.budget.line'].search([
                    ('cost_center_id', '=', cost_center.id)
                ])
                budget_amount = sum(budget_lines.mapped('allocated_amount'))
                
                # Get actual expenses
                expense_domain = [
                    ('cost_center_id', '=', cost_center.id),
                    ('date', '>=', self.start_date),
                    ('date', '<=', self.end_date),
                    ('state', 'in', ['confirmed', 'approved', 'paid'])
                ]
                expenses = self.env['facilities.budget.expense'].search(expense_domain)
                actual_amount = sum(expenses.mapped('amount'))
                
                data['datasets'][0]['data'].append(budget_amount)
                data['datasets'][1]['data'].append(actual_amount)
        
        return data
    
    def _get_cost_center_breakdown_data(self):
        """Get cost center breakdown pie chart data"""
        data = {
            'labels': [],
            'datasets': [{
                'data': [],
                'backgroundColor': [
                    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
                    '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
                ]
            }]
        }
        
        cost_centers = self.cost_center_ids or self.env['facilities.cost.center'].search([])
        
        for cost_center in cost_centers:
            expense_domain = [
                ('cost_center_id', '=', cost_center.id),
                ('date', '>=', self.start_date),
                ('date', '<=', self.end_date),
                ('state', 'in', ['confirmed', 'approved', 'paid'])
            ]
            expenses = self.env['facilities.budget.expense'].search(expense_domain)
            total_amount = sum(expenses.mapped('amount'))
            
            if total_amount > 0:
                data['labels'].append(cost_center.name)
                data['datasets'][0]['data'].append(total_amount)
        
        return data
    
    def _get_category_breakdown_data(self):
        """Get expense category breakdown pie chart data"""
        data = {
            'labels': [],
            'datasets': [{
                'data': [],
                'backgroundColor': [
                    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
                    '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
                ]
            }]
        }
        
        categories = self.category_ids or self.env['facilities.expense.category'].search([])
        
        for category in categories:
            expense_domain = [
                ('category_id', '=', category.id),
                ('date', '>=', self.start_date),
                ('date', '<=', self.end_date),
                ('state', 'in', ['confirmed', 'approved', 'paid'])
            ]
            expenses = self.env['facilities.budget.expense'].search(expense_domain)
            total_amount = sum(expenses.mapped('amount'))
            
            if total_amount > 0:
                data['labels'].append(category.name)
                data['datasets'][0]['data'].append(total_amount)
        
        return data
    
    def _get_trend_analysis_data(self):
        """Get trend analysis line chart data"""
        data = {
            'labels': [],
            'datasets': [
                {
                    'label': 'Monthly Expenses',
                    'data': [],
                    'borderColor': 'rgba(75, 192, 192, 1)',
                    'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                    'fill': True
                },
                {
                    'label': 'Monthly Budget',
                    'data': [],
                    'borderColor': 'rgba(54, 162, 235, 1)',
                    'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                    'fill': False
                }
            ]
        }
        
        # Generate monthly data for the last 12 months
        current_date = fields.Date.today()
        for i in range(12):
            month_start = (current_date - relativedelta(months=i)).replace(day=1)
            month_end = month_start + relativedelta(months=1) - timedelta(days=1)
            
            month_label = month_start.strftime('%b %Y')
            data['labels'].insert(0, month_label)
            
            # Get expenses for this month
            expense_domain = [
                ('date', '>=', month_start),
                ('date', '<=', month_end),
                ('state', 'in', ['confirmed', 'approved', 'paid'])
            ]
            if self.cost_center_ids:
                expense_domain.append(('cost_center_id', 'in', self.cost_center_ids.ids))
            if self.category_ids:
                expense_domain.append(('category_id', 'in', self.category_ids.ids))
            
            expenses = self.env['facilities.budget.expense'].search(expense_domain)
            monthly_expense = sum(expenses.mapped('amount'))
            
            # Get budget for this month (assuming monthly budget allocation)
            budget_domain = []
            if self.cost_center_ids:
                budget_domain.append(('cost_center_id', 'in', self.cost_center_ids.ids))
            if self.category_ids:
                budget_domain.append(('category_id', 'in', self.category_ids.ids))
            
            budget_lines = self.env['facilities.budget.line'].search(budget_domain)
            monthly_budget = sum(budget_lines.mapped('allocated_amount')) / 12  # Assuming yearly budget
            
            data['datasets'][0]['data'].insert(0, monthly_expense)
            data['datasets'][1]['data'].insert(0, monthly_budget)
        
        return data
    
    def action_refresh_dashboard(self):
        """Manually refresh dashboard data"""
        self._compute_kpis()
        self._compute_chart_data()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def action_view_expenses(self):
        """View expenses for this dashboard period"""
        domain = [
            ('date', '>=', self.start_date),
            ('date', '<=', self.end_date)
        ]
        
        if self.cost_center_ids:
            domain.append(('cost_center_id', 'in', self.cost_center_ids.ids))
        
        if self.category_ids:
            domain.append(('category_id', 'in', self.category_ids.ids))
        
        return {
            'name': _('Dashboard Expenses'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.expense',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'default_date': fields.Date.today()}
        }
    
    def action_view_budgets(self):
        """View budgets for this dashboard"""
        domain = []
        
        if self.cost_center_ids:
            domain.append(('cost_center_id', 'in', self.cost_center_ids.ids))
        
        if self.category_ids:
            domain.append(('category_id', 'in', self.category_ids.ids))
        
        return {
            'name': _('Dashboard Budget Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.budget.line',
            'view_mode': 'list,form',
            'domain': domain
        }
