# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
import json
import logging

_logger = logging.getLogger(__name__)


class MaintenanceAnalyticsDashboard(models.TransientModel):
    """
    Unified Maintenance Analytics Dashboard
    Serves data for multiple dashboard views:
    - KPI Dashboard
    - Technician Performance
    - Resource Utilization  
    - Maintenance Performance
    """
    _name = 'maintenance.analytics.dashboard'
    _description = 'Maintenance Analytics Dashboard'
    
    @api.model
    def get_kpi_dashboard_data(self, filters=None):
        """Get data for general Maintenance KPI Dashboard"""
        date_from, date_to, facility_id = self._parse_filters(filters)
        
        # Get work order metrics
        domain = [('start_date', '>=', date_from), ('start_date', '<=', date_to)]
        if facility_id:
            domain.append(('work_location_facility_id', '=', facility_id))
        
        workorders = self.env['facilities.workorder'].search(domain)
        
        kpis = [
            {'name': _('Total Work Orders'), 'value': len(workorders), 'icon': 'fa-tasks', 'color': 'primary'},
            {'name': _('Assigned'), 'value': len(workorders.filtered(lambda w: w.state == 'assigned')), 'icon': 'fa-clipboard', 'color': 'info'},
            {'name': _('In Progress'), 'value': len(workorders.filtered(lambda w: w.state == 'in_progress')), 'icon': 'fa-cog', 'color': 'warning'},
            {'name': _('Completed'), 'value': len(workorders.filtered(lambda w: w.state == 'completed')), 'icon': 'fa-check-circle', 'color': 'success'},
            {'name': _('Overdue'), 'value': len(workorders.filtered(lambda w: w.start_date < fields.Date.today() and w.state not in ['completed', 'cancelled'])), 
             'icon': 'fa-exclamation-triangle', 'color': 'danger'},
            {'name': _('On Hold'), 'value': len(workorders.filtered(lambda w: w.state == 'on_hold')), 'icon': 'fa-pause', 'color': 'secondary'},
            {'name': _('Preventive'), 'value': len(workorders.filtered(lambda w: w.maintenance_type == 'preventive')), 'icon': 'fa-calendar-check-o', 'color': 'success'},
            {'name': _('Corrective'), 'value': len(workorders.filtered(lambda w: w.maintenance_type == 'corrective')), 'icon': 'fa-wrench', 'color': 'warning'},
            {'name': _('Total Cost'), 'value': f"${sum(workorders.mapped('labor_cost')) + sum(workorders.mapped('parts_cost')):,.0f}", 'icon': 'fa-dollar', 'color': 'danger'},
            {'name': _('Labor Cost'), 'value': f"${sum(workorders.mapped('labor_cost')):,.0f}", 'icon': 'fa-users', 'color': 'info'},
            {'name': _('Parts Cost'), 'value': f"${sum(workorders.mapped('parts_cost')):,.0f}", 'icon': 'fa-cog', 'color': 'warning'},
            {'name': _('Avg Duration'), 'value': f"{self._calc_avg_duration(workorders):.1f}h", 'icon': 'fa-clock-o', 'color': 'info'},
        ]
        
        charts = [
            self._get_wo_status_chart(workorders),
            self._get_maintenance_type_chart(workorders),
            self._get_priority_chart(workorders),
            self._get_cost_trend_chart(date_from, date_to, facility_id),
        ]
        
        return {'kpis': kpis, 'charts': charts}
    
    @api.model
    def get_technician_performance_data(self, filters=None):
        """Get data for Technician Performance Dashboard"""
        date_from, date_to, facility_id = self._parse_filters(filters)
        
        domain = [('start_date', '>=', date_from), ('start_date', '<=', date_to)]
        if facility_id:
            domain.append(('work_location_facility_id', '=', facility_id))
        
        workorders = self.env['facilities.workorder'].search(domain)
        
        # Group by technician
        tech_stats = {}
        for wo in workorders:
            if wo.technician_id:
                tech_name = wo.technician_id.name
                if tech_name not in tech_stats:
                    tech_stats[tech_name] = {'total': 0, 'completed': 0, 'pending': 0, 'cost': 0}
                tech_stats[tech_name]['total'] += 1
                if wo.state == 'completed':
                    tech_stats[tech_name]['completed'] += 1
                else:
                    tech_stats[tech_name]['pending'] += 1
                tech_stats[tech_name]['cost'] += (wo.labor_cost or 0)
        
        total_techs = len(tech_stats)
        total_wos = len(workorders)
        avg_per_tech = total_wos / total_techs if total_techs > 0 else 0
        
        kpis = [
            {'name': _('Total Technicians'), 'value': total_techs, 'icon': 'fa-users', 'color': 'primary'},
            {'name': _('Total Work Orders'), 'value': total_wos, 'icon': 'fa-tasks', 'color': 'info'},
            {'name': _('Avg WO per Technician'), 'value': f"{avg_per_tech:.1f}", 'icon': 'fa-user', 'color': 'success'},
            {'name': _('Total Labor Cost'), 'value': f"${sum(workorders.mapped('labor_cost')):,.0f}", 'icon': 'fa-dollar', 'color': 'warning'},
            {'name': _('Completed WOs'), 'value': len(workorders.filtered(lambda w: w.state == 'completed')), 'icon': 'fa-check', 'color': 'success'},
            {'name': _('Pending WOs'), 'value': len(workorders.filtered(lambda w: w.state not in ['completed', 'cancelled'])), 'icon': 'fa-hourglass-half', 'color': 'warning'},
        ]
        
        # Charts
        sorted_techs = sorted(tech_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:10]
        
        charts = [
            {
                'type': 'bar',
                'title': _('Work Orders by Technician'),
                'labels': [t[0] for t in sorted_techs],
                'datasets': [{
                    'label': _('Work Orders'),
                    'data': [t[1]['total'] for t in sorted_techs],
                    'backgroundColor': 'rgba(75, 192, 192, 0.7)',
                    'borderColor': 'rgba(75, 192, 192, 1)',
                    'borderWidth': 1
                }]
            },
            {
                'type': 'bar',
                'title': _('Completion Rate by Technician'),
                'labels': [t[0] for t in sorted_techs],
                'datasets': [{
                    'label': _('Completion %'),
                    'data': [(t[1]['completed'] / t[1]['total'] * 100) if t[1]['total'] > 0 else 0 for t in sorted_techs],
                    'backgroundColor': 'rgba(54, 162, 235, 0.7)',
                    'borderColor': 'rgba(54, 162, 235, 1)',
                    'borderWidth': 1
                }]
            },
        ]
        
        return {'kpis': kpis, 'charts': charts}
    
    @api.model
    def get_resource_utilization_data(self, filters=None):
        """Get data for Resource Utilization Dashboard"""
        date_from, date_to, facility_id = self._parse_filters(filters)
        
        domain = [('start_date', '>=', date_from), ('start_date', '<=', date_to)]
        if facility_id:
            domain.append(('work_location_facility_id', '=', facility_id))
        
        workorders = self.env['facilities.workorder'].search(domain)
        teams = self.env['maintenance.team'].search([])
        
        total_hours = sum(workorders.mapped('estimated_duration'))
        total_techs = len(self.env['hr.employee'].search([('id', 'in', workorders.mapped('technician_id').ids)]))
        
        kpis = [
            {'name': _('Total Teams'), 'value': len(teams), 'icon': 'fa-users', 'color': 'primary'},
            {'name': _('Active Technicians'), 'value': total_techs, 'icon': 'fa-user', 'color': 'info'},
            {'name': _('Total Hours Planned'), 'value': f"{total_hours:.1f}h", 'icon': 'fa-clock-o', 'color': 'success'},
            {'name': _('Avg Hours per WO'), 'value': f"{total_hours/len(workorders) if workorders else 0:.1f}h", 'icon': 'fa-tachometer', 'color': 'warning'},
            {'name': _('Resource Utilization'), 'value': f"{min(total_hours/total_techs/8*100 if total_techs else 0, 100):.1f}%", 'icon': 'fa-pie-chart', 'color': 'info'},
            {'name': _('Teams with Work'), 'value': len(workorders.mapped('maintenance_team_id')), 'icon': 'fa-users', 'color': 'success'},
        ]
        
        charts = [
            {
                'type': 'doughnut',
                'title': _('Work Distribution by Team'),
                'labels': [team.name for team in teams[:5]],
                'datasets': [{
                    'data': [len(workorders.filtered(lambda w: w.maintenance_team_id == team)) for team in teams[:5]],
                    'backgroundColor': [f'rgba({54+i*40}, {162-i*20}, {235-i*30}, 0.7)' for i in range(5)]
                }]
            },
        ]
        
        return {'kpis': kpis, 'charts': charts}
    
    @api.model
    def get_maintenance_performance_data(self, filters=None):
        """Get data for Maintenance Performance Dashboard"""
        date_from, date_to, facility_id = self._parse_filters(filters)
        
        domain = [('start_date', '>=', date_from), ('start_date', '<=', date_to)]
        if facility_id:
            domain.append(('work_location_facility_id', '=', facility_id))
        
        workorders = self.env['facilities.workorder'].search(domain)
        completed = workorders.filtered(lambda w: w.state == 'completed')
        
        completion_rate = len(completed) / len(workorders) * 100 if workorders else 0
        
        kpis = [
            {'name': _('Completion Rate'), 'value': f"{completion_rate:.1f}%", 'icon': 'fa-percent', 
             'color': 'success' if completion_rate >= 80 else 'warning'},
            {'name': _('First Time Fix'), 'value': len(workorders.filtered(lambda w: w.first_time_fix)), 'icon': 'fa-check-square', 'color': 'success'},
            {'name': _('Preventive %'), 'value': f"{len(workorders.filtered(lambda w: w.maintenance_type == 'preventive'))/len(workorders)*100 if workorders else 0:.1f}%", 
             'icon': 'fa-shield', 'color': 'info'},
            {'name': _('Corrective %'), 'value': f"{len(workorders.filtered(lambda w: w.maintenance_type == 'corrective'))/len(workorders)*100 if workorders else 0:.1f}%", 
             'icon': 'fa-wrench', 'color': 'warning'},
            {'name': _('Total Cost'), 'value': f"${sum(workorders.mapped('labor_cost')) + sum(workorders.mapped('parts_cost')):,.0f}", 'icon': 'fa-money', 'color': 'danger'},
            {'name': _('Cost per WO'), 'value': f"${(sum(workorders.mapped('labor_cost')) + sum(workorders.mapped('parts_cost')))/len(workorders) if workorders else 0:.0f}", 
             'icon': 'fa-calculator', 'color': 'info'},
        ]
        
        charts = [
            self._get_wo_status_chart(workorders),
            self._get_maintenance_type_chart(workorders),
        ]
        
        return {'kpis': kpis, 'charts': charts}
    
    def _parse_filters(self, filters):
        """Parse and calculate date range from filters"""
        today = fields.Date.today()
        period_type = filters.get('period_type', 'month') if filters else 'month'
        
        if filters and filters.get('date_from') and filters.get('date_to'):
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
        
        facility_id = filters.get('facility_id') if filters else None
        
        return date_from, date_to, facility_id
    
    def _calc_avg_duration(self, workorders):
        """Calculate average duration for completed work orders"""
        completed = workorders.filtered(lambda w: w.state == 'completed' and w.actual_start_date and w.actual_end_date)
        if not completed:
            return 0.0
        total_hours = sum((wo.actual_end_date - wo.actual_start_date).total_seconds() / 3600 for wo in completed)
        return total_hours / len(completed)
    
    def _get_wo_status_chart(self, workorders):
        """Work order status chart"""
        return {
            'type': 'doughnut',
            'title': _('Work Order Status'),
            'labels': [_('Assigned'), _('In Progress'), _('Completed'), _('On Hold'), _('Cancelled')],
            'datasets': [{
                'data': [
                    len(workorders.filtered(lambda w: w.state == 'assigned')),
                    len(workorders.filtered(lambda w: w.state == 'in_progress')),
                    len(workorders.filtered(lambda w: w.state == 'completed')),
                    len(workorders.filtered(lambda w: w.state == 'on_hold')),
                    len(workorders.filtered(lambda w: w.state == 'cancelled')),
                ],
                'backgroundColor': [
                    'rgba(54, 162, 235, 0.7)',
                    'rgba(255, 206, 86, 0.7)',
                    'rgba(75, 192, 192, 0.7)',
                    'rgba(108, 117, 125, 0.7)',
                    'rgba(220, 53, 69, 0.7)'
                ]
            }]
        }
    
    def _get_maintenance_type_chart(self, workorders):
        """Maintenance type chart"""
        return {
            'type': 'pie',
            'title': _('Maintenance Type'),
            'labels': [_('Preventive'), _('Corrective'), _('Predictive')],
            'datasets': [{
                'data': [
                    len(workorders.filtered(lambda w: w.maintenance_type == 'preventive')),
                    len(workorders.filtered(lambda w: w.maintenance_type == 'corrective')),
                    len(workorders.filtered(lambda w: w.maintenance_type == 'predictive')),
                ],
                'backgroundColor': [
                    'rgba(75, 192, 192, 0.7)',
                    'rgba(255, 206, 86, 0.7)',
                    'rgba(153, 102, 255, 0.7)'
                ]
            }]
        }
    
    def _get_priority_chart(self, workorders):
        """Priority distribution chart"""
        priority_counts = {'0': 0, '1': 0, '2': 0, '3': 0, '4': 0}
        for wo in workorders:
            priority = wo.priority or '0'
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        return {
            'type': 'bar',
            'title': _('Work Orders by Priority'),
            'labels': [_('Very Low'), _('Low'), _('Normal'), _('High'), _('Critical')],
            'datasets': [{
                'label': _('Work Orders'),
                'data': list(priority_counts.values()),
                'backgroundColor': [
                    'rgba(108, 117, 125, 0.7)',
                    'rgba(13, 202, 240, 0.7)',
                    'rgba(13, 110, 253, 0.7)',
                    'rgba(255, 193, 7, 0.7)',
                    'rgba(220, 53, 69, 0.7)',
                ],
                'borderWidth': 1
            }]
        }
    
    def _get_cost_trend_chart(self, date_from, date_to, facility_id):
        """Cost trend chart"""
        labels = []
        cost_data = []
        
        # Get last 6 months
        for i in range(5, -1, -1):
            month_date = fields.Date.today() - timedelta(days=30 * i)
            month_start = month_date.replace(day=1)
            if month_date.month == 12:
                month_end = month_date.replace(day=31)
            else:
                next_month = month_date.replace(month=month_date.month + 1, day=1)
                month_end = next_month - timedelta(days=1)
            
            labels.append(month_date.strftime('%b %Y'))
            
            domain = [('start_date', '>=', month_start), ('start_date', '<=', month_end)]
            if facility_id:
                domain.append(('work_location_facility_id', '=', facility_id))
            
            wos = self.env['facilities.workorder'].search(domain)
            cost_data.append(sum(wos.mapped('labor_cost')) + sum(wos.mapped('parts_cost')))
        
        return {
            'type': 'line',
            'title': _('Maintenance Cost Trend (6 Months)'),
            'labels': labels,
            'datasets': [{
                'label': _('Total Cost ($)'),
                'data': cost_data,
                'borderColor': 'rgba(13, 110, 253, 1)',
                'backgroundColor': 'rgba(13, 110, 253, 0.1)',
                'fill': True,
                'tension': 0.4
            }]
        }

