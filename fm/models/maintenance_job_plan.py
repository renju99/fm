from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MaintenanceJobPlan(models.Model):
    _name = 'maintenance.job.plan'
    _description = 'Maintenance Job Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Job Plan Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False, default=lambda self: _('New'))
    description = fields.Html(string='Description / Guidelines')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    asset_category_ids = fields.Many2many('facilities.asset.category', string='Applicable Asset Categories')
    section_ids = fields.One2many('maintenance.job.plan.section', 'job_plan_id', string='Sections', copy=True)

    # Computed field to get all tasks under this job plan via all sections
    task_ids = fields.One2many(
        'maintenance.job.plan.task',
        'job_plan_id',
        string='All Tasks',
        compute='_compute_task_ids',
        store=False,
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The code of the job plan must be unique!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('maintenance.job.plan') or _('New')
        return super().create(vals_list)

    @api.depends('section_ids.task_ids')
    def _compute_task_ids(self):
        for plan in self:
            plan.task_ids = plan.section_ids.mapped('task_ids')

    def toggle_active(self):
        """Toggle the active state of the job plan"""
        for plan in self:
            plan.active = not plan.active
            if plan.active:
                plan.message_post(body=_("Job plan activated"))
            else:
                plan.message_post(body=_("Job plan archived"))

    def unlink(self):
        """Prevent deletion if job plan is being used in maintenance schedules."""
        for plan in self:
            # Check if this job plan is used in any maintenance schedules
            maintenance_schedules = self.env['asset.maintenance.schedule'].search([
                ('job_plan_id', '=', plan.id)
            ])
            
            if maintenance_schedules:
                schedule_names = ', '.join(maintenance_schedules.mapped('name'))
                raise UserError(_("Cannot delete job plan '%s' because it is being used in the following maintenance schedules: %s") % 
                              (plan.name, schedule_names))
            
            # Check if this job plan is used in any work orders
            work_orders = self.env['facilities.workorder'].search([
                ('job_plan_id', '=', plan.id)
            ])
            
            if work_orders:
                work_order_names = ', '.join(work_orders.mapped('name'))
                raise UserError(_("Cannot delete job plan '%s' because it is being used in the following work orders: %s") % 
                              (plan.name, work_order_names))
        
        return super().unlink()

    def get_usage_info(self):
        """Get information about where this job plan is being used."""
        self.ensure_one()
        
        maintenance_schedules = self.env['asset.maintenance.schedule'].search([
            ('job_plan_id', '=', self.id)
        ])
        
        work_orders = self.env['facilities.workorder'].search([
            ('job_plan_id', '=', self.id)
        ])
        
        return {
            'maintenance_schedules': maintenance_schedules,
            'work_orders': work_orders,
            'total_schedules': len(maintenance_schedules),
            'total_work_orders': len(work_orders)
        }