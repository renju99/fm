# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class MaintenanceWorkOrderPerformance(models.Model):
    """Performance optimizations for maintenance work orders"""
    _name = 'maintenance.workorder.performance'
    _description = 'Maintenance Work Order Performance Optimizations'
    _inherit = ['facilities.workorder.core']

    # Optimized computed fields with better performance
    @api.depends('assignment_ids.work_hours', 'assignment_ids.status')
    def _compute_total_assignment_hours_optimized(self):
        """Optimized computation of total assignment hours"""
        for record in self:
            # Use SQL for better performance on large datasets
            self.env.cr.execute("""
                SELECT COALESCE(SUM(work_hours), 0)
                FROM facilities_workorder_assignment
                WHERE workorder_id = %s AND status = 'completed'
            """, (record.id,))
            result = self.env.cr.fetchone()
            record.total_assignment_hours = result[0] if result else 0.0

    @api.depends('assignment_ids.labor_cost', 'assignment_ids.status')
    def _compute_total_assignment_labor_cost_optimized(self):
        """Optimized computation of total assignment labor cost"""
        for record in self:
            # Use SQL for better performance
            self.env.cr.execute("""
                SELECT COALESCE(SUM(labor_cost), 0)
                FROM facilities_workorder_assignment
                WHERE workorder_id = %s AND status = 'completed'
            """, (record.id,))
            result = self.env.cr.fetchone()
            record.total_assignment_labor_cost = result[0] if result else 0.0

    @api.depends('task_ids.is_done', 'task_ids.workorder_id')
    def _compute_all_tasks_completed_optimized(self):
        """Optimized computation of task completion status"""
        for record in self:
            if not record.task_ids:
                record.all_tasks_completed = True
                continue
            
            # Use SQL for better performance
            self.env.cr.execute("""
                SELECT COUNT(*) as total, SUM(CASE WHEN is_done = true THEN 1 ELSE 0 END) as completed
                FROM facilities_workorder_task
                WHERE workorder_id = %s
            """, (record.id,))
            result = self.env.cr.fetchone()
            
            if result and result[0] > 0:
                record.all_tasks_completed = (result[1] == result[0])
            else:
                record.all_tasks_completed = True

    @api.depends('state', 'sla_response_deadline', 'sla_resolution_deadline', 'actual_start_date', 'actual_end_date')
    def _compute_sla_status_optimized(self):
        """Optimized SLA status computation"""
        now = fields.Datetime.now()
        
        for record in self:
            if not record.sla_id:
                record.sla_status = 'on_time'
                continue
            
            response_breached = False
            resolution_breached = False
            
            # Check response SLA
            if record.sla_response_deadline and now > record.sla_response_deadline:
                if not record.actual_start_date:
                    response_breached = True
            
            # Check resolution SLA
            if record.sla_resolution_deadline and now > record.sla_resolution_deadline:
                if record.state != 'completed':
                    resolution_breached = True
            
            if response_breached or resolution_breached:
                record.sla_status = 'breached'
            else:
                # Check if at risk (80% of time elapsed)
                if record.sla_response_deadline:
                    total_time = record.sla_response_deadline - record.create_date
                    elapsed_time = now - record.create_date
                    if total_time.total_seconds() > 0:
                        percentage = (elapsed_time.total_seconds() / total_time.total_seconds()) * 100
                        if percentage >= 80:
                            record.sla_status = 'at_risk'
                        else:
                            record.sla_status = 'on_time'
                    else:
                        record.sla_status = 'on_time'
                else:
                    record.sla_status = 'on_time'

    def _get_performance_metrics(self, domain=None):
        """Get performance metrics for work orders efficiently"""
        if domain is None:
            domain = []
        
        # Use SQL for better performance on large datasets
        self.env.cr.execute("""
            SELECT 
                COUNT(*) as total_workorders,
                COUNT(CASE WHEN state = 'completed' THEN 1 END) as completed_workorders,
                COUNT(CASE WHEN sla_status = 'on_time' THEN 1 END) as on_time_workorders,
                COUNT(CASE WHEN sla_status = 'breached' THEN 1 END) as breached_workorders,
                AVG(actual_duration) as avg_completion_time,
                SUM(labor_cost) as total_labor_cost,
                SUM(parts_cost) as total_parts_cost,
                SUM(total_cost) as total_cost
            FROM facilities_workorder
            WHERE %s
        """, (domain,))
        
        result = self.env.cr.fetchone()
        return {
            'total_workorders': result[0] or 0,
            'completed_workorders': result[1] or 0,
            'on_time_workorders': result[2] or 0,
            'breached_workorders': result[3] or 0,
            'avg_completion_time': result[4] or 0.0,
            'total_labor_cost': result[5] or 0.0,
            'total_parts_cost': result[6] or 0.0,
            'total_cost': result[7] or 0.0
        }

    def _get_technician_performance(self, technician_id, date_from=None, date_to=None):
        """Get technician performance metrics efficiently"""
        domain = [('technician_id', '=', technician_id)]
        
        if date_from:
            domain.append(('create_date', '>=', date_from))
        if date_to:
            domain.append(('create_date', '<=', date_to))
        
        # Use SQL for better performance
        self.env.cr.execute("""
            SELECT 
                COUNT(*) as total_workorders,
                COUNT(CASE WHEN state = 'completed' THEN 1 END) as completed_workorders,
                AVG(actual_duration) as avg_completion_time,
                COUNT(CASE WHEN first_time_fix = true THEN 1 END) as first_time_fixes,
                SUM(total_cost) as total_cost
            FROM facilities_workorder
            WHERE technician_id = %s
            AND create_date >= %s
            AND create_date <= %s
        """, (technician_id, date_from or '1900-01-01', date_to or '2100-12-31'))
        
        result = self.env.cr.fetchone()
        
        if result and result[0] > 0:
            first_time_fix_rate = (result[3] / result[0]) * 100 if result[0] > 0 else 0
            completion_rate = (result[1] / result[0]) * 100 if result[0] > 0 else 0
        else:
            first_time_fix_rate = 0
            completion_rate = 0
        
        return {
            'total_workorders': result[0] or 0,
            'completed_workorders': result[1] or 0,
            'avg_completion_time': result[2] or 0.0,
            'first_time_fixes': result[3] or 0,
            'first_time_fix_rate': first_time_fix_rate,
            'completion_rate': completion_rate,
            'total_cost': result[4] or 0.0
        }

    def _get_asset_performance(self, asset_id, date_from=None, date_to=None):
        """Get asset performance metrics efficiently"""
        domain = [('asset_id', '=', asset_id)]
        
        if date_from:
            domain.append(('create_date', '>=', date_from))
        if date_to:
            domain.append(('create_date', '<=', date_to))
        
        # Use SQL for better performance
        self.env.cr.execute("""
            SELECT 
                COUNT(*) as total_workorders,
                COUNT(CASE WHEN state = 'completed' THEN 1 END) as completed_workorders,
                AVG(actual_duration) as avg_repair_time,
                COUNT(CASE WHEN work_order_type = 'preventive' THEN 1 END) as preventive_workorders,
                COUNT(CASE WHEN work_order_type = 'corrective' THEN 1 END) as corrective_workorders,
                SUM(total_cost) as total_maintenance_cost
            FROM facilities_workorder
            WHERE asset_id = %s
            AND create_date >= %s
            AND create_date <= %s
        """, (asset_id, date_from or '1900-01-01', date_to or '2100-12-31'))
        
        result = self.env.cr.fetchone()
        
        return {
            'total_workorders': result[0] or 0,
            'completed_workorders': result[1] or 0,
            'avg_repair_time': result[2] or 0.0,
            'preventive_workorders': result[3] or 0,
            'corrective_workorders': result[4] or 0,
            'total_maintenance_cost': result[5] or 0.0
        }

    def _batch_update_sla_status(self, workorder_ids):
        """Batch update SLA status for multiple work orders"""
        if not workorder_ids:
            return
        
        # Use SQL for better performance
        self.env.cr.execute("""
            UPDATE facilities_workorder
            SET sla_status = CASE
                WHEN sla_response_deadline IS NOT NULL AND NOW() > sla_response_deadline 
                     AND actual_start_date IS NULL THEN 'breached'
                WHEN sla_resolution_deadline IS NOT NULL AND NOW() > sla_resolution_deadline 
                     AND state != 'completed' THEN 'breached'
                WHEN sla_response_deadline IS NOT NULL AND 
                     (NOW() - create_date)::interval / (sla_response_deadline - create_date)::interval >= 0.8 
                     AND actual_start_date IS NULL THEN 'at_risk'
                ELSE 'on_time'
            END
            WHERE id = ANY(%s)
        """, (workorder_ids,))
        
        self.env.cr.commit()

    def _batch_calculate_costs(self, workorder_ids):
        """Batch calculate costs for multiple work orders"""
        if not workorder_ids:
            return
        
        # Use SQL for better performance
        self.env.cr.execute("""
            UPDATE facilities_workorder
            SET 
                labor_cost = (
                    SELECT COALESCE(SUM(labor_cost), 0)
                    FROM facilities_workorder_assignment
                    WHERE workorder_id = facilities_workorder.id
                ),
                parts_cost = (
                    SELECT COALESCE(SUM(total_cost), 0)
                    FROM facilities_workorder_part_line
                    WHERE workorder_id = facilities_workorder.id
                )
            WHERE id = ANY(%s)
        """, (workorder_ids,))
        
        # Update total cost
        self.env.cr.execute("""
            UPDATE facilities_workorder
            SET total_cost = labor_cost + parts_cost
            WHERE id = ANY(%s)
        """, (workorder_ids,))
        
        self.env.cr.commit()

    def _get_workload_distribution(self, team_id=None, date_from=None, date_to=None):
        """Get workload distribution efficiently"""
        domain = []
        
        if team_id:
            domain.append(('team_id', '=', team_id))
        if date_from:
            domain.append(('create_date', '>=', date_from))
        if date_to:
            domain.append(('create_date', '<=', date_to))
        
        # Use SQL for better performance
        self.env.cr.execute("""
            SELECT 
                state,
                COUNT(*) as count,
                AVG(actual_duration) as avg_duration,
                SUM(total_cost) as total_cost
            FROM facilities_workorder
            WHERE %s
            GROUP BY state
            ORDER BY state
        """, (domain,))
        
        results = self.env.cr.fetchall()
        
        distribution = {}
        for result in results:
            distribution[result[0]] = {
                'count': result[1],
                'avg_duration': result[2] or 0.0,
                'total_cost': result[3] or 0.0
            }
        
        return distribution

    def _optimize_database_queries(self):
        """Optimize database queries by adding missing indexes"""
        # Add indexes for frequently queried fields
        indexes_to_create = [
            ('facilities_workorder', 'state'),
            ('facilities_workorder', 'priority'),
            ('facilities_workorder', 'technician_id'),
            ('facilities_workorder', 'team_id'),
            ('facilities_workorder', 'asset_id'),
            ('facilities_workorder', 'facility_id'),
            ('facilities_workorder', 'create_date'),
            ('facilities_workorder', 'sla_status'),
            ('facilities_workorder_assignment', 'workorder_id'),
            ('facilities_workorder_assignment', 'technician_id'),
            ('facilities_workorder_assignment', 'status'),
            ('facilities_workorder_task', 'workorder_id'),
            ('facilities_workorder_task', 'is_done'),
            ('facilities_service_request', 'state'),
            ('facilities_service_request', 'requester_id'),
            ('facilities_service_request', 'facility_id'),
        ]
        
        for table, field in indexes_to_create:
            try:
                self.env.cr.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_{field} 
                    ON {table} ({field})
                """)
            except Exception as e:
                _logger.warning(f"Could not create index for {table}.{field}: {e}")
        
        self.env.cr.commit()
