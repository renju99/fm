from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError

class MaintenanceWorkorderTaskExtension(models.Model):
    _inherit = 'facilities.workorder'

    show_tasks_to_complete_btn = fields.Boolean(
        compute="_compute_show_tasks_to_complete_btn",
        string="Show Tasks to Complete Button"
    )

    @api.depends('work_order_type')
    def _compute_show_tasks_to_complete_btn(self):
        for rec in self:
            rec.show_tasks_to_complete_btn = rec.work_order_type == 'preventive'

    def action_open_job_plan_tasks_mobile(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tasks to Complete'),
            'res_model': 'facilities.workorder.task',
            'view_mode': 'list,form',
            'domain': [('workorder_id', '=', self.id), ('is_done', '=', False)],
            'context': {'default_workorder_id': self.id},
            'target': 'current',
        }

class MaintenanceWorkorderTask(models.Model):
    _name = 'facilities.workorder.task'
    _description = 'Maintenance Work Order Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'section_id, sequence, id'

    workorder_id = fields.Many2one('facilities.workorder', string='Work Order', required=True, ondelete='cascade')
    workorder_status = fields.Selection(related='workorder_id.state', string='Work Order Status', store=True, readonly=True)
    section_id = fields.Many2one('facilities.workorder.section', string='Section', ondelete='cascade')
    name = fields.Char(string='Task Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    is_done = fields.Boolean(string='Completed', default=False)
    description = fields.Html(string='Instructions')
    notes = fields.Html(string='Technician Notes', help="Notes added by the technician during execution.")
    is_checklist_item = fields.Boolean(string='Checklist Item', default=True)
    before_image = fields.Binary(string="Before Image", attachment=True, help="Image of the asset/area before task execution.")
    before_image_filename = fields.Char(string="Before Image Filename")
    after_image = fields.Binary(string="After Image", attachment=True, help="Image of the asset/area after task execution.")
    after_image_filename = fields.Char(string="After Image Filename")
    duration = fields.Float(string='Estimated Duration (hours)')
    tools_materials = fields.Html(string='Tools/Materials Required')
    responsible_id = fields.Many2one('hr.employee', string='Responsible Personnel (Role)')
    product_id = fields.Many2one('product.product', string='Required Part')
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    frequency_type = fields.Selection(
        [
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
        ],
        string='Frequency Type',
        help="How often this task should be performed.",
    )

    # Removed constraints that prevented editing based on workorder state

    def toggle_task_completion(self):
        """Toggle the completion status of a task"""
        self.ensure_one()
        
        self.is_done = not self.is_done
        if self.is_done:
            self.message_post(body=_("Task marked as completed by %s") % self.env.user.name)
        else:
            self.message_post(body=_("Task marked as incomplete by %s") % self.env.user.name)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Task Updated'),
                'message': _('Task "%s" has been marked as %s') % (self.name, _('completed') if self.is_done else _('incomplete')),
                'type': 'success',
            }
        }

    def action_upload_before_image(self):
        """Action to upload before image"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Upload Before Image'),
            'res_model': 'facilities.workorder.task',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'default_before_image': True},
        }

    def action_upload_after_image(self):
        """Action to upload after image"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Upload After Image'),
            'res_model': 'facilities.workorder.task',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'default_after_image': True},
        }

    def action_open_mobile_task_form(self):
        """Open mobile task form for editing"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Task Details'),
            'res_model': 'facilities.workorder.task',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'view_id': self.env.ref('facilities_management.view_maintenance_workorder_task_mobile_form').id,
            'context': {'mobile_view': True},
        }

    def action_view_task_mobile(self):
        """Default action when clicking on task in mobile view"""
        return self.action_open_mobile_task_form()

    def action_row_click_mobile(self):
        """Action when clicking on the task row in mobile view"""
        return self.action_open_mobile_task_form()

    def unlink(self):
        """Prevent deletion of maintenance task checklists once linked to a workorder"""
        for record in self:
            if record.workorder_id and record.workorder_id.state not in ['draft', 'cancelled']:
                raise UserError(_("Cannot delete maintenance task checklist '%s' from workorder '%s' once it is linked and the workorder is not in draft or cancelled state. This ensures data integrity and prevents loss of important maintenance records.") % (record.name, record.workorder_id.name))
            elif record.workorder_id and record.workorder_id.state in ['draft', 'cancelled']:
                # Allow deletion only if workorder is in draft or cancelled state
                continue
            else:
                # Allow deletion if not linked to any workorder
                continue
        return super().unlink()