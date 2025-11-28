# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date
import logging

_logger = logging.getLogger(__name__)


class BudgetDashboard(models.Model):
    _name = 'facilities.budget.dashboard'
    _description = 'Budget vs Actual Dashboard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Dashboard Name',
        required=True,
        default='Budget Analysis',
        tracking=True
    )
    
    date_from = fields.Date(
        string='From Date',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1),
        tracking=True
    )
    
    date_to = fields.Date(
        string='To Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    
    cost_center_id = fields.Many2one(
        'facilities.cost.center',
        string='Cost Center',
        tracking=True,
        help='Filter by specific cost center'
    )
    
    budget_id = fields.Many2one(
        'facilities.financial.budget',
        string='Budget',
        tracking=True,
        help='Filter by specific budget'
    )
    
    category_id = fields.Many2one(
        'facilities.expense.category',
        string='Expense Category',
        tracking=True,
        help='Filter by specific expense category'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )
    
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    # KPI Fields
    total_budget = fields.Monetary(
        string='Total Budget',
        currency_field='currency_id',
        compute='_compute_kpis',
        store=True
    )
    
    total_actual = fields.Monetary(
        string='Total Actual',
        currency_field='currency_id',
        compute='_compute_kpis',
        store=True
    )
    
    total_variance = fields.Monetary(
        string='Total Variance',
        currency_field='currency_id',
        compute='_compute_kpis',
        store=True
    )
    
    variance_percentage = fields.Float(
        string='Variance %',
        compute='_compute_kpis',
        store=True
    )
    
    budget_utilization = fields.Float(
        string='Budget Utilization %',
        compute='_compute_kpis',
        store=True
    )
    
    over_budget_count = fields.Integer(
        string='Over Budget Items',
        compute='_compute_kpis',
        store=True
    )
    
    under_budget_count = fields.Integer(
        string='Under Budget Items',
        compute='_compute_kpis',
        store=True
    )
    
    @api.depends('date_from', 'date_to', 'cost_center_id', 'budget_id', 'category_id')
    def _compute_kpis(self):
        """Compute dashboard KPIs"""
        for record in self:
            try:
                metrics = record._get_dashboard_metrics()
                record.total_budget = metrics.get('total_budget', 0)
                record.total_actual = metrics.get('total_actual', 0)
                record.total_variance = metrics.get('total_variance', 0)
                record.variance_percentage = metrics.get('variance_percentage', 0)
                record.budget_utilization = metrics.get('budget_utilization', 0)
                record.over_budget_count = metrics.get('over_budget_count', 0)
                record.under_budget_count = metrics.get('under_budget_count', 0)
            except Exception as e:
                _logger.warning(f"Error computing KPIs: {e}")
                record.total_budget = 0
                record.total_actual = 0
                record.total_variance = 0
                record.variance_percentage = 0
                record.budget_utilization = 0
                record.over_budget_count = 0
                record.under_budget_count = 0
    
    def _get_dashboard_metrics(self):
        """Calculate dashboard metrics"""
        self.ensure_one()
        
        # Get budgets in the date range
        budget_domain = [
            ('start_date', '<=', self.date_to),
            ('end_date', '>=', self.date_from),
            ('state', '!=', 'cancelled')
        ]
        
        budgets = self.env['facilities.financial.budget'].search(budget_domain)
        
        # Get budget lines from those budgets
        line_domain = [('budget_id', 'in', budgets.ids)]
        
        if self.cost_center_id:
            line_domain.append(('cost_center_id', '=', self.cost_center_id.id))
        
        if self.category_id:
            line_domain.append(('category_id', '=', self.category_id.id))
        
        budget_lines = self.env['facilities.budget.line'].search(line_domain)
        
        # Calculate total budget from budget lines
        total_budget = sum(budget_lines.mapped('allocated_amount'))
        
        # Calculate ACTUAL from COMPLETED WORK ORDERS ONLY (finalized costs)
        workorder_domain = [
            ('state', '=', 'completed'),  # Only completed work orders
            '|', '|',
            '&', ('start_date', '>=', self.date_from), ('start_date', '<=', self.date_to),
            '&', ('actual_start_date', '>=', self.date_from), ('actual_start_date', '<=', self.date_to),
            '&', ('create_date', '>=', fields.Datetime.to_datetime(self.date_from)),
                 ('create_date', '<=', fields.Datetime.to_datetime(self.date_to))
        ]
        
        if self.cost_center_id:
            workorder_domain = ['&'] + workorder_domain + [('cost_center_id', '=', self.cost_center_id.id)]
        
        # Get completed work orders with costs
        workorders = self.env['facilities.workorder'].search(workorder_domain)
        
        # Sum ALL costs from COMPLETED work orders (labor + parts + materials + other costs)
        total_actual = sum(workorders.mapped('total_cost'))
        
        # Calculate variance and percentages
        total_variance = total_budget - total_actual
        variance_percentage = (total_variance / total_budget * 100) if total_budget > 0 else 0
        budget_utilization = (total_actual / total_budget * 100) if total_budget > 0 else 0
        
        # Count over/under budget items by comparing each budget line with corresponding work orders
        over_budget_count = 0
        under_budget_count = 0
        
        for line in budget_lines:
            # Get work orders for this cost center
            line_workorders = workorders.filtered(lambda w: w.cost_center_id == line.cost_center_id)
            actual_for_line = sum(line_workorders.mapped('total_cost'))
            
            if actual_for_line > line.allocated_amount:
                over_budget_count += 1
            elif actual_for_line < line.allocated_amount and actual_for_line > 0:
                under_budget_count += 1
        
        _logger.info(f"Budget Metrics - Budget: ${total_budget:,.2f}, Actual from {len(workorders)} completed work orders: ${total_actual:,.2f}, Variance: ${total_variance:,.2f}")
        
        return {
            'total_budget': total_budget,
            'total_actual': total_actual,
            'total_variance': total_variance,
            'variance_percentage': variance_percentage,
            'budget_utilization': budget_utilization,
            'over_budget_count': over_budget_count,
            'under_budget_count': under_budget_count
        }
    
    @api.model
    def get_dashboard_data_api(self, dashboard_id=None, filters=None):
        """API method for dashboard frontend"""
        filters = filters or {}
        
        # Calculate date range
        today = fields.Date.today()
        period_type = filters.get('period_type', 'month')
        
        if filters.get('date_from') and filters.get('date_to'):
            date_from = fields.Date.from_string(filters['date_from'])
            date_to = fields.Date.from_string(filters['date_to'])
        elif period_type == 'today':
            date_from = date_to = today
        elif period_type == 'week':
            date_from = today - timedelta(days=today.weekday())
            date_to = today
        elif period_type == 'month':
            date_from = today.replace(day=1)
            date_to = today
        elif period_type == 'quarter':
            quarter = (today.month - 1) // 3
            date_from = date(today.year, quarter * 3 + 1, 1)
            date_to = today
        elif period_type == 'year':
            date_from = date(today.year, 1, 1)
            date_to = today
        else:
            date_from = today.replace(day=1)
            date_to = today
        
        cost_center_id = filters.get('cost_center_id')
        category_id = filters.get('category_id')
        
        # Calculate metrics
        metrics = self._calculate_metrics(date_from, date_to, cost_center_id, category_id)
        
        # Build KPIs
        kpis = [
            {
                'name': _('Total Budget'),
                'value': f"${metrics['total_budget']:,.0f}",
                'icon': 'fa-money',
                'color': 'primary',
                'key': 'total_budget'
            },
            {
                'name': _('Total Spent'),
                'value': f"${metrics['total_actual']:,.0f}",
                'icon': 'fa-credit-card',
                'color': 'info',
                'key': 'total_actual'
            },
            {
                'name': _('Variance'),
                'value': f"${metrics['total_variance']:,.0f}",
                'icon': 'fa-line-chart',
                'color': 'success' if metrics['total_variance'] >= 0 else 'danger',
                'key': 'total_variance'
            },
            {
                'name': _('Budget Utilization'),
                'value': f"{metrics['budget_utilization']:.1f}%",
                'icon': 'fa-percent',
                'color': 'warning' if metrics['budget_utilization'] > 90 else 'success',
                'key': 'budget_utilization'
            },
            {
                'name': _('Over Budget Items'),
                'value': metrics['over_budget_count'],
                'icon': 'fa-exclamation-triangle',
                'color': 'danger',
                'key': 'over_budget_count'
            },
            {
                'name': _('Under Budget Items'),
                'value': metrics['under_budget_count'],
                'icon': 'fa-check-circle',
                'color': 'success',
                'key': 'under_budget_count'
            },
            {
                'name': _('Remaining Budget'),
                'value': f"${max(0, metrics['total_variance']):,.0f}",
                'icon': 'fa-piggy-bank',
                'color': 'info',
                'key': 'remaining_budget'
            },
            {
                'name': _('Avg Variance %'),
                'value': f"{metrics['variance_percentage']:.1f}%",
                'icon': 'fa-bar-chart',
                'color': 'primary',
                'key': 'variance_percentage'
            },
        ]
        
        # Build charts
        charts = self._build_budget_charts(date_from, date_to, cost_center_id, category_id)
        
        return {'kpis': kpis, 'charts': charts}
    
    @api.model
    def _calculate_metrics(self, date_from, date_to, cost_center_id=None, category_id=None):
        """Calculate budget metrics with actuals from work orders"""
        # Get budgets in the date range
        budget_domain = [
            ('start_date', '<=', date_to),
            ('end_date', '>=', date_from),
            ('state', '!=', 'cancelled')
        ]
        
        budgets = self.env['facilities.financial.budget'].search(budget_domain)
        
        # Get budget lines from those budgets
        line_domain = [('budget_id', 'in', budgets.ids)]
        
        if cost_center_id:
            line_domain.append(('cost_center_id', '=', cost_center_id))
        if category_id:
            line_domain.append(('category_id', '=', category_id))
        
        budget_lines = self.env['facilities.budget.line'].search(line_domain)
        
        # Calculate total budget from budget lines
        total_budget = sum(budget_lines.mapped('allocated_amount'))
        
        # Calculate ACTUAL from COMPLETED WORK ORDERS ONLY (finalized costs)
        workorder_domain = [
            ('state', '=', 'completed'),  # Only completed work orders for accurate actuals
            '|', '|',
            '&', ('start_date', '>=', date_from), ('start_date', '<=', date_to),
            '&', ('actual_start_date', '>=', date_from), ('actual_start_date', '<=', date_to),
            '&', ('create_date', '>=', fields.Datetime.to_datetime(date_from)),
                 ('create_date', '<=', fields.Datetime.to_datetime(date_to))
        ]
        
        if cost_center_id:
            workorder_domain = ['&'] + workorder_domain + [('cost_center_id', '=', cost_center_id)]
        
        # Get COMPLETED work orders with costs
        workorders = self.env['facilities.workorder'].search(workorder_domain)
        
        # Sum ALL costs from COMPLETED work orders (labor + parts + materials + other costs)
        total_actual = sum(workorders.mapped('total_cost'))
        
        # Calculate variance and utilization
        total_variance = total_budget - total_actual
        variance_percentage = (total_variance / total_budget * 100) if total_budget > 0 else 0
        budget_utilization = (total_actual / total_budget * 100) if total_budget > 0 else 0
        
        # Count over/under budget items by cost center
        over_budget_count = 0
        under_budget_count = 0
        
        for line in budget_lines:
            # Get work orders for this cost center
            line_workorders = workorders.filtered(lambda w: w.cost_center_id == line.cost_center_id)
            actual_for_line = sum(line_workorders.mapped('total_cost'))
            
            if actual_for_line > line.allocated_amount:
                over_budget_count += 1
            elif actual_for_line < line.allocated_amount and actual_for_line > 0:
                under_budget_count += 1
        
        _logger.info(f"Budget Metrics - Budget: ${total_budget:,.2f}, Actual from {len(workorders)} COMPLETED work orders: ${total_actual:,.2f}, Variance: ${total_variance:,.2f}")
        
        return {
            'total_budget': total_budget,
            'total_actual': total_actual,
            'total_variance': total_variance,
            'variance_percentage': variance_percentage,
            'budget_utilization': budget_utilization,
            'over_budget_count': over_budget_count,
            'under_budget_count': under_budget_count
        }
    
    def _build_budget_charts(self, date_from, date_to, cost_center_id=None, category_id=None):
        """Build chart data for dashboard with actuals from work orders"""
        # Get budgets in date range
        budget_domain = [
            ('start_date', '<=', date_to),
            ('end_date', '>=', date_from),
            ('state', '!=', 'cancelled')
        ]
        budgets = self.env['facilities.financial.budget'].search(budget_domain)
        
        # Get COMPLETED work orders in date range for actuals
        workorder_domain = [
            ('state', '=', 'completed'),  # Only completed work orders
            '|', '|',
            '&', ('start_date', '>=', date_from), ('start_date', '<=', date_to),
            '&', ('actual_start_date', '>=', date_from), ('actual_start_date', '<=', date_to),
            '&', ('create_date', '>=', fields.Datetime.to_datetime(date_from)),
                 ('create_date', '<=', fields.Datetime.to_datetime(date_to))
        ]
        
        if cost_center_id:
            workorder_domain = ['&'] + workorder_domain + [('cost_center_id', '=', cost_center_id)]
        
        all_workorders = self.env['facilities.workorder'].search(workorder_domain)
        
        # Build chart by cost center (more relevant than category for work orders)
        cost_centers = self.env['facilities.cost.center'].search([])
        cc_budget = []
        cc_actual = []
        cc_labels = []
        
        for cc in cost_centers[:10]:  # Limit to top 10
            line_domain = [
                ('budget_id', 'in', budgets.ids),
                ('cost_center_id', '=', cc.id)
            ]
            if category_id:
                line_domain.append(('category_id', '=', category_id))
            
            budget_lines = self.env['facilities.budget.line'].search(line_domain)
            
            # Budget allocated
            budget_amt = sum(budget_lines.mapped('allocated_amount'))
            
            # Actual from work orders for this cost center
            cc_workorders = all_workorders.filtered(lambda w: w.cost_center_id == cc)
            actual_amt = sum(cc_workorders.mapped('total_cost'))
            
            if budget_amt > 0 or actual_amt > 0:
                cc_labels.append(cc.name)
                cc_budget.append(budget_amt)
                cc_actual.append(actual_amt)
        
        return [
            {
                'type': 'bar',
                'title': _('Budget vs Actual by Cost Center'),
                'labels': cc_labels,
                'datasets': [
                    {
                        'label': 'Budgeted',
                        'data': cc_budget,
                        'backgroundColor': 'rgba(54, 162, 235, 0.7)',
                        'borderColor': 'rgba(54, 162, 235, 1)',
                        'borderWidth': 1
                    },
                    {
                        'label': 'Actual (Completed Work Orders)',
                        'data': cc_actual,
                        'backgroundColor': 'rgba(255, 99, 132, 0.7)',
                        'borderColor': 'rgba(255, 99, 132, 1)',
                        'borderWidth': 1
                    }
                ]
            }
        ]
    
    # Drilldown Actions
    def action_drilldown_total_budget(self, date_from=None, date_to=None, cost_center_id=None, category_id=None):
        """Drilldown to budget lines"""
        _logger.info(f"Budget Lines Drilldown - date_from: {date_from}, date_to: {date_to}")
        
        domain = []
        
        # Filter by budget date range
        if date_from and date_to:
            try:
                if isinstance(date_from, str):
                    date_from = fields.Date.from_string(date_from)
                if isinstance(date_to, str):
                    date_to = fields.Date.from_string(date_to)
                
                # Get budgets in date range
                budgets = self.env['facilities.financial.budget'].search([
                    ('start_date', '<=', date_to),
                    ('end_date', '>=', date_from),
                    ('state', '!=', 'cancelled')
                ])
                domain = [('budget_id', 'in', budgets.ids)]
            except Exception as e:
                _logger.warning(f"Error with dates: {e}")
                domain = []
        
        if cost_center_id:
            if domain:
                domain.append(('cost_center_id', '=', cost_center_id))
            else:
                domain = [('cost_center_id', '=', cost_center_id)]
        
        if category_id:
            if domain:
                domain.append(('category_id', '=', category_id))
            else:
                domain = [('category_id', '=', category_id)]
        
        count = self.env['facilities.budget.line'].search_count(domain)
        _logger.info(f"Drilldown will show {count} budget lines")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Budget Lines ({count} records)',
            'res_model': 'facilities.budget.line',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'target': 'current',
            'context': {}
        }
    
    def action_drilldown_total_actual(self, date_from=None, date_to=None, cost_center_id=None, category_id=None):
        """Drilldown to actual expenses from COMPLETED work orders"""
        _logger.info(f"Actual Expenses (Completed Work Orders) Drilldown - date_from: {date_from}, date_to: {date_to}")
        
        domain = [('state', '=', 'completed')]  # Only completed work orders for actuals
        
        # Build flexible date filter for work orders
        if date_from and date_to:
            try:
                if isinstance(date_from, str):
                    date_from = fields.Date.from_string(date_from)
                if isinstance(date_to, str):
                    date_to = fields.Date.from_string(date_to)
                
                date_domain = [
                    '|', '|',
                    '&', ('start_date', '>=', date_from), ('start_date', '<=', date_to),
                    '&', ('actual_start_date', '>=', date_from), ('actual_start_date', '<=', date_to),
                    '&', ('create_date', '>=', fields.Datetime.to_datetime(date_from)),
                         ('create_date', '<=', fields.Datetime.to_datetime(date_to))
                ]
                domain = ['&'] + domain + date_domain
            except Exception as e:
                _logger.warning(f"Error with dates: {e}")
        
        if cost_center_id:
            domain = ['&'] + domain + [('cost_center_id', '=', cost_center_id)]
        
        # Get completed work orders count
        count = self.env['facilities.workorder'].search_count(domain)
        
        # Also get total cost for display
        workorders = self.env['facilities.workorder'].search(domain)
        total_cost = sum(workorders.mapped('total_cost'))
        labor_cost = sum(workorders.mapped('labor_cost'))
        parts_cost = sum(workorders.mapped('parts_cost'))
        
        _logger.info(f"Drilldown will show {count} COMPLETED work orders - Total: ${total_cost:,.2f}, Labor: ${labor_cost:,.2f}, Parts: ${parts_cost:,.2f}")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Completed Work Orders ({count} records, ${total_cost:,.0f})',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,pivot,graph,form',
            'views': [(False, 'list'), (False, 'pivot'), (False, 'graph'), (False, 'form')],
            'domain': domain,
            'target': 'current',
            'context': {
                'pivot_measures': ['total_cost', 'labor_cost', 'parts_cost'],
                'group_by': ['cost_center_id'],
            }
        }
    
    def action_drilldown_over_budget(self, date_from=None, date_to=None, cost_center_id=None, category_id=None):
        """Drilldown to over-budget items (cost centers)"""
        _logger.info(f"Over Budget Items Drilldown - date_from: {date_from}, date_to: {date_to}")
        
        # Get budgets in date range
        budgets_domain = []
        if date_from and date_to:
            try:
                if isinstance(date_from, str):
                    date_from = fields.Date.from_string(date_from)
                if isinstance(date_to, str):
                    date_to = fields.Date.from_string(date_to)
                
                budgets = self.env['facilities.financial.budget'].search([
                    ('start_date', '<=', date_to),
                    ('end_date', '>=', date_from),
                    ('state', '!=', 'cancelled')
                ])
                budgets_domain = [('budget_id', 'in', budgets.ids)]
            except Exception as e:
                _logger.warning(f"Error with dates: {e}")
                budgets_domain = []
        
        if cost_center_id:
            if budgets_domain:
                budgets_domain.append(('cost_center_id', '=', cost_center_id))
            else:
                budgets_domain = [('cost_center_id', '=', cost_center_id)]
        
        if category_id:
            if budgets_domain:
                budgets_domain.append(('category_id', '=', category_id))
            else:
                budgets_domain = [('category_id', '=', category_id)]
        
        # Get COMPLETED work orders for actual calculation
        wo_domain = [('state', '=', 'completed')]  # Only completed work orders
        
        if date_from and date_to:
            date_filter = [
                '|', '|',
                '&', ('start_date', '>=', date_from), ('start_date', '<=', date_to),
                '&', ('actual_start_date', '>=', date_from), ('actual_start_date', '<=', date_to),
                '&', ('create_date', '>=', fields.Datetime.to_datetime(date_from)),
                     ('create_date', '<=', fields.Datetime.to_datetime(date_to))
            ]
            wo_domain = ['&'] + wo_domain + date_filter
        
        if cost_center_id:
            wo_domain = ['&'] + wo_domain + [('cost_center_id', '=', cost_center_id)]
        
        workorders = self.env['facilities.workorder'].search(wo_domain)
        
        # Get all budget lines and check which are over budget
        all_lines = self.env['facilities.budget.line'].search(budgets_domain)
        over_budget_lines = []
        
        for line in all_lines:
            # Calculate actual from work orders for this cost center
            line_workorders = workorders.filtered(lambda w: w.cost_center_id == line.cost_center_id)
            actual_for_line = sum(line_workorders.mapped('total_cost'))
            
            if actual_for_line > line.allocated_amount:
                over_budget_lines.append(line.id)
        
        count = len(over_budget_lines)
        _logger.info(f"Drilldown will show {count} over-budget cost centers")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Over Budget Cost Centers ({count} records)',
            'res_model': 'facilities.budget.line',
            'view_mode': 'list,pivot,form',
            'views': [(False, 'list'), (False, 'pivot'), (False, 'form')],
            'domain': [('id', 'in', over_budget_lines)] if over_budget_lines else [('id', '=', False)],
            'target': 'current',
            'context': {}
        }

