from odoo import models, fields, api

class MaintenanceWorkorderSection(models.Model):
    _name = 'facilities.workorder.section'
    _description = 'Work Order Section'
    _order = 'sequence, id'

    name = fields.Char(string='Section Name', required=True, readonly=True)
    sequence = fields.Integer(string='Sequence', default=10, readonly=True)
    workorder_id = fields.Many2one('facilities.workorder', string='Work Order', required=True, ondelete='cascade')
    task_ids = fields.One2many('facilities.workorder.task', 'section_id', string='Tasks')
    
    # Computed fields for task counts
    task_count = fields.Integer(
        string='Total Tasks',
        compute='_compute_task_counts',
        store=True,
        help='Total number of tasks in this section'
    )
    
    completed_task_count = fields.Integer(
        string='Completed Tasks',
        compute='_compute_task_counts',
        store=True,
        help='Number of completed tasks in this section'
    )
    
    completion_percentage = fields.Float(
        string='Completion %',
        compute='_compute_task_counts',
        store=True,
        help='Percentage of completed tasks in this section'
    )
    
    @api.depends('task_ids', 'task_ids.is_done')
    def _compute_task_counts(self):
        """Compute task counts and completion percentage for the section."""
        for rec in self:
            total_tasks = len(rec.task_ids)
            completed_tasks = len([t for t in rec.task_ids if t.is_done])
            
            rec.task_count = total_tasks
            rec.completed_task_count = completed_tasks
            rec.completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0