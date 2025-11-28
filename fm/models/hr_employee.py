from odoo import models, fields, api
from datetime import timedelta

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    employee_number = fields.Char(
        string='Employee Number',
        help="Unique employee identification number"
    )
    is_technician = fields.Boolean(
        string='Is Technician',
        default=False,
        help="Check if this employee is a maintenance technician"
    )
    mttr_hours = fields.Float(
        string='Mean Time to Repair (Hours)',
        compute='_compute_kpi_metrics',
        store=False
    )
    first_time_fix_rate = fields.Float(
        string='First-Time Fix Rate (%)',
        compute='_compute_kpi_metrics',
        store=False
    )
    workload_open = fields.Integer(
        string='Open Work Orders',
        compute='_compute_kpi_metrics',
        store=False
    )
    workload_closed_30d = fields.Integer(
        string='Closed Work Orders (30d)',
        compute='_compute_kpi_metrics',
        store=False
    )
    hourly_cost = fields.Monetary(
        string='Hourly Cost',
        currency_field='currency_id',
        default=50.0,
        help="Cost per hour for this employee"
    )

    current_workload = fields.Float(
        string='Current Workload (%)',
        compute='_compute_current_workload',
        help="Current workload percentage based on active work orders"
    )

    def _compute_kpi_metrics(self):
        WorkOrder = self.env['facilities.workorder']
        for tech in self:
            # Done work orders
            domain_done = [
                ('technician_id', '=', tech.id),
                ('status', '=', 'done'),
                ('actual_start_date', '!=', False),
                ('actual_end_date', '!=', False),
            ]
            wos_done = WorkOrder.search(domain_done)
            mttr_list = []
            first_time_fixes = 0
            for wo in wos_done:
                if wo.actual_start_date and wo.actual_end_date:
                    mttr = (wo.actual_end_date - wo.actual_start_date).total_seconds() / 3600.0
                    mttr_list.append(mttr)
                    if getattr(wo, 'first_time_fix', False):
                        first_time_fixes += 1
            tech.mttr_hours = round(sum(mttr_list) / len(mttr_list), 2) if mttr_list else 0.0
            tech.first_time_fix_rate = round((first_time_fixes / len(wos_done)) * 100, 1) if wos_done else 0.0
            tech.workload_open = WorkOrder.search_count([('technician_id', '=', tech.id), ('status', '!=', 'done')])
            last_30d = fields.Datetime.now() - timedelta(days=30)
            tech.workload_closed_30d = WorkOrder.search_count([
                ('technician_id', '=', tech.id),
                ('status', '=', 'done'),
                ('actual_end_date', '>=', last_30d)
            ])

    def _compute_current_workload(self):
        for employee in self:
            if 'facilities.workorder' in self.env:
                try:
                    active_workorders = self.env['facilities.workorder'].search([
                        ('assigned_technician_ids', 'in', employee.id),
                        ('status', 'in', ['draft', 'in_progress'])
                    ])
                    employee.current_workload = min(100.0, len(active_workorders) * 20.0)
                except Exception:
                    employee.current_workload = 0.0
            else:
                employee.current_workload = 0.0