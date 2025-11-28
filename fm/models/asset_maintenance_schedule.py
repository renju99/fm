# models/asset_maintenance_schedule.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
from datetime import datetime, date, timedelta
import logging

_logger = logging.getLogger(__name__)

class AssetMaintenanceSchedule(models.Model):
    _name = 'asset.maintenance.schedule'
    _description = 'Asset Maintenance Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Schedule Name', required=True, tracking=True)
    
    # Schedule Type - Asset-based or Location-based
    schedule_type = fields.Selection([
        ('asset', 'Asset-based'),
        ('location', 'Location-based'),
    ], string='Schedule Type', default='asset', required=True, tracking=True)
    
    # Asset-based scheduling
    asset_id = fields.Many2one('facilities.asset', string='Asset', tracking=True, ondelete='restrict',
                               help="Required for asset-based schedules")
    
    # Location-based scheduling
    facility_id = fields.Many2one('facilities.facility', string='Facility', tracking=True)
    building_id = fields.Many2one('facilities.building', string='Building', tracking=True)
    floor_id = fields.Many2one('facilities.floor', string='Floor', tracking=True)
    room_id = fields.Many2one('facilities.room', string='Room', tracking=True)
    
    maintenance_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection'),
    ], string='Maintenance Type', required=True, default='preventive', tracking=True)

    interval_number = fields.Integer(string='Repeat Every', default=1, required=True, tracking=True)
    interval_type = fields.Selection([
        ('daily', 'Day(s)'),
        ('weekly', 'Week(s)'),
        ('monthly', 'Month(s)'),
        ('quarterly', 'Quarter(s)'),
        ('yearly', 'Year(s)'),
    ], string='Recurrence', default='monthly', required=True, tracking=True)

    last_maintenance_date = fields.Date(string='Last Maintenance Date', tracking=True)
    next_maintenance_date = fields.Date(string='Next Scheduled Date', compute='_compute_next_maintenance_date', store=True, tracking=True, readonly=False)
    notes = fields.Html(string='Notes')

    active = fields.Boolean(string='Active', default=True, tracking=True)

    status = fields.Selection([
        ('draft', 'Draft'),
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='planned', tracking=True)

    job_plan_id = fields.Many2one('maintenance.job.plan', string='Job Plan',
                                  domain="[('active', '=', True)]",
                                  tracking=True,
                                  help="Select a Job Plan to automatically populate tasks for this maintenance schedule. "
                                       "Note: Job plans are only available for preventive maintenance schedules.")

    workorder_ids = fields.One2many('facilities.workorder', 'schedule_id', string='Generated Work Orders')
    workorder_count = fields.Integer(compute='_compute_workorder_count', string='Work Orders')

    _sql_constraints = [
        ('asset_type_unique_per_asset', 'unique(asset_id, maintenance_type, active)', 'A schedule of this type already exists for this active asset!'),
        ('job_plan_preventive_only', 'check(maintenance_type = \'preventive\' OR job_plan_id IS NULL)', 'Job plans can only be assigned to preventive maintenance schedules!'),
        ('asset_or_location_required', 'check((schedule_type = \'asset\' AND asset_id IS NOT NULL) OR (schedule_type = \'location\' AND (facility_id IS NOT NULL OR building_id IS NOT NULL OR floor_id IS NOT NULL OR room_id IS NOT NULL)))', 'Either asset must be selected for asset-based schedules or at least one location must be selected for location-based schedules!'),
    ]

    @api.onchange('schedule_type')
    def _onchange_schedule_type(self):
        """Clear fields when schedule type changes."""
        if self.schedule_type == 'asset':
            # Clear location fields for asset-based schedules
            self.facility_id = False
            self.building_id = False
            self.floor_id = False
            self.room_id = False
        elif self.schedule_type == 'location':
            # Clear asset field for location-based schedules
            self.asset_id = False

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        """Auto-fill location fields from asset when asset is selected."""
        if self.asset_id and self.schedule_type == 'asset':
            self.facility_id = self.asset_id.facility_id
            self.building_id = self.asset_id.building_id
            self.floor_id = self.asset_id.floor_id
            self.room_id = self.asset_id.room_id

    @api.onchange('room_id')
    def _onchange_room_id(self):
        """Auto-fill parent location fields from room."""
        if self.room_id and self.schedule_type == 'location':
            if self.room_id.floor_id:
                self.floor_id = self.room_id.floor_id
                if self.room_id.floor_id.building_id:
                    self.building_id = self.room_id.floor_id.building_id
                    if self.room_id.floor_id.building_id.facility_id:
                        self.facility_id = self.room_id.floor_id.building_id.facility_id

    @api.onchange('floor_id')
    def _onchange_floor_id(self):
        """Auto-fill parent location fields from floor."""
        if self.floor_id and self.schedule_type == 'location':
            if self.floor_id.building_id:
                self.building_id = self.floor_id.building_id
                if self.floor_id.building_id.facility_id:
                    self.facility_id = self.floor_id.building_id.facility_id

    @api.onchange('building_id')
    def _onchange_building_id(self):
        """Auto-fill parent location fields from building."""
        if self.building_id and self.schedule_type == 'location':
            if self.building_id.facility_id:
                self.facility_id = self.building_id.facility_id

    @api.constrains('maintenance_type', 'job_plan_id')
    def _check_job_plan_preventive_only(self):
        """Ensure job plans are only assigned to preventive maintenance schedules."""
        for record in self:
            if record.job_plan_id and record.maintenance_type != 'preventive':
                raise UserError(_("Job plans can only be assigned to preventive maintenance schedules. "
                                "Current maintenance type: %s") % record.maintenance_type)

    @api.constrains('schedule_type', 'asset_id', 'facility_id', 'building_id', 'floor_id', 'room_id')
    def _check_schedule_requirements(self):
        """Validate that required fields are filled based on schedule type."""
        for record in self:
            if record.schedule_type == 'asset' and not record.asset_id:
                raise UserError(_("Asset is required for asset-based schedules."))
            elif record.schedule_type == 'location':
                if not any([record.facility_id, record.building_id, record.floor_id, record.room_id]):
                    raise UserError(_("At least one location (Facility, Building, Floor, or Room) is required for location-based schedules."))

    @api.onchange('maintenance_type')
    def _onchange_maintenance_type(self):
        """Clear job plan when maintenance type changes from preventive to something else."""
        if self.maintenance_type != 'preventive':
            if self.job_plan_id:
                self.job_plan_id = False
                return {
                    'warning': {
                        'title': _('Job Plan Cleared'),
                        'message': _('Job plan has been cleared because this is not a preventive maintenance schedule. '
                                    'All associated job plan tasks will be lost.')
                    }
                }
        else:
            # If changing to preventive, show info about job plan availability (only for existing records)
            if not self.job_plan_id and self.id:
                return {
                    'warning': {
                        'title': _('Job Plan Available'),
                        'message': _('You can now assign a job plan to this preventive maintenance schedule.')
                    }
                }

    @api.onchange('job_plan_id')
    def _onchange_job_plan_id(self):
        """Validate that job plan can only be assigned to preventive maintenance."""
        if self.job_plan_id and self.maintenance_type != 'preventive':
            self.job_plan_id = False
            return {
                'warning': {
                    'title': _('Invalid Selection'),
                    'message': _('Job plans can only be assigned to preventive maintenance schedules.')
                }
            }

    @api.depends('last_maintenance_date', 'interval_number', 'interval_type')
    def _compute_next_maintenance_date(self):
        for rec in self:
            if rec.last_maintenance_date and rec.interval_number > 0:
                current_date = rec.last_maintenance_date
                if rec.interval_type == 'daily':
                    rec.next_maintenance_date = current_date + relativedelta(days=rec.interval_number)
                elif rec.interval_type == 'weekly':
                    rec.next_maintenance_date = current_date + relativedelta(weeks=rec.interval_number)
                elif rec.interval_type == 'monthly':
                    rec.next_maintenance_date = current_date + relativedelta(months=rec.interval_number)
                elif rec.interval_type == 'quarterly':
                    rec.next_maintenance_date = current_date + relativedelta(months=rec.interval_number * 3)
                elif rec.interval_type == 'yearly':
                    rec.next_maintenance_date = current_date + relativedelta(years=rec.interval_number)
                else:
                    rec.next_maintenance_date = False
            else:
                rec.next_maintenance_date = False

    @api.depends('workorder_ids')
    def _compute_workorder_count(self):
        for rec in self:
            rec.workorder_count = len(rec.workorder_ids)

    def _generate_preventive_workorders(self):
        """
        Cron job method to automatically generate preventive maintenance work orders
        for schedules that are due.
        """
        today = date.today()
        
        # Find all active preventive maintenance schedules that are due
        due_schedules = self.search([
            ('active', '=', True),
            ('maintenance_type', '=', 'preventive'),
            ('next_maintenance_date', '<=', today),
            ('status', 'in', ['planned', 'done'])
        ])
        
        generated_count = 0
        for schedule in due_schedules:
            try:
                # Generate work orders based on schedule type
                if schedule.schedule_type == 'asset':
                    work_order = self._create_workorder_with_tasks(schedule)
                    if work_order:
                        generated_count += 1
                        schedule.message_post(
                            body=_("Automatically generated work order %s with %s tasks from job plan.") % 
                            (work_order.name, len(work_order.workorder_task_ids))
                        )
                elif schedule.schedule_type == 'location':
                    work_orders = self._create_location_based_workorders(schedule)
                    if work_orders:
                        generated_count += len(work_orders)
                        schedule.message_post(
                            body=_("Automatically generated %s work orders for location-based schedule.") % 
                            len(work_orders)
                        )
            except Exception as e:
                schedule.message_post(
                    body=_("Failed to generate work order: %s") % str(e)
                )
        
        return generated_count

    def _create_location_based_workorders(self, schedule):
        """
        Create work orders for all assets in the specified location(s).
        """
        if not schedule.active:
            raise UserError(_("Cannot generate work orders for an inactive schedule."))
        if not schedule.next_maintenance_date:
            raise UserError(_("Next maintenance date is not set for the schedule: %s.") % schedule.name)

        # Find all assets in the specified location(s)
        domain = [('active', '=', True), ('state', '=', 'active')]
        
        if schedule.room_id:
            domain.append(('room_id', '=', schedule.room_id.id))
        elif schedule.floor_id:
            domain.append(('floor_id', '=', schedule.floor_id.id))
        elif schedule.building_id:
            domain.append(('building_id', '=', schedule.building_id.id))
        elif schedule.facility_id:
            domain.append(('facility_id', '=', schedule.facility_id.id))
        
        assets = self.env['facilities.asset'].search(domain)
        
        if not assets:
            raise UserError(_("No active assets found in the specified location(s)."))
        
        work_orders = []
        for asset in assets:
            # Check for duplicate work orders
            existing_workorder = self._check_duplicate_workorder(schedule, asset)
            if existing_workorder:
                # Skip if duplicate exists and no overwrite option
                continue
            
            # Create work order for this asset
            work_order = self._create_workorder_with_tasks(schedule, asset)
            if work_order:
                work_orders.append(work_order)
        
        return work_orders

    def action_generate_workorders_manual(self):
        """
        Manual action to generate work orders with overwrite option.
        """
        self.ensure_one()
        
        if self.schedule_type == 'asset':
            # Check for existing work order
            existing_workorder = self._check_duplicate_workorder(self, self.asset_id)
            if existing_workorder:
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Overwrite Existing Work Order?',
                    'res_model': 'asset.maintenance.schedule.overwrite.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_schedule_id': self.id,
                        'default_existing_workorder_id': existing_workorder.id,
                        'default_asset_id': self.asset_id.id,
                    }
                }
            else:
                # Create new work order
                work_order = self._create_workorder_with_tasks(self)
                if work_order:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': 'Generated Work Order',
                        'res_model': 'facilities.workorder',
                        'view_mode': 'form',
                        'res_id': work_order.id,
                        'target': 'current',
                    }
        elif self.schedule_type == 'location':
            # Generate work orders for all assets in location
            work_orders = self._create_location_based_workorders(self)
            if work_orders:
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Generated Work Orders',
                    'res_model': 'facilities.workorder',
                    'view_mode': 'list,form',
                    'domain': [('id', 'in', [wo.id for wo in work_orders])],
                    'target': 'current',
                }
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'No Work Orders Generated',
                'message': 'No work orders were generated. Check if assets exist in the specified location.',
                'type': 'warning'
            }
        }

    def _check_duplicate_workorder(self, schedule, asset):
        """
        Check if a work order already exists for this schedule and asset.
        """
        existing_workorder = self.env['facilities.workorder'].search([
            ('schedule_id', '=', schedule.id),
            ('asset_id', '=', asset.id),
            ('work_order_type', '=', 'preventive'),
            ('state', 'in', ['draft', 'assigned', 'in_progress'])
        ], limit=1)
        
        return existing_workorder

    def _create_workorder_with_tasks(self, schedule, asset=None, target_date=None):
        """
        Create a work order and copy tasks from the associated job plan.
        """
        if not schedule.active:
            raise UserError(_("Cannot generate a work order for an inactive schedule."))
        
        # Use target_date if provided, otherwise use next_maintenance_date
        scheduled_date = target_date or schedule.next_maintenance_date
        if not scheduled_date:
            raise UserError(_("Next maintenance date is not set for the schedule: %s.") % schedule.name)

        # Validate that job plan can only be used for preventive maintenance
        if schedule.job_plan_id and schedule.maintenance_type != 'preventive':
            raise UserError(_("Cannot create work order: Job plans can only be used with preventive maintenance schedules."))

        # Determine the asset for the work order
        target_asset = asset or schedule.asset_id
        if not target_asset:
            raise UserError(_("No asset specified for work order creation."))

        # For calendar display, set end date to the same day as start date
        # This shows the work order falls on that specific day
        end_date = scheduled_date
        
        # Calculate estimated duration for work order record (not for calendar display)
        if schedule.job_plan_id and schedule.job_plan_id.task_ids:
            estimated_duration = sum(schedule.job_plan_id.task_ids.mapped('duration')) or 8.0
        else:
            estimated_duration = 8.0  # 8 hours default
        
        # Debug logging
        _logger.info(f"Creating work order: start_date={scheduled_date}, end_date={end_date}, estimated_duration={estimated_duration}")
        
        # Create the work order
        work_order_vals = {
            'name': _('New'),
            'asset_id': target_asset.id,
            'schedule_id': schedule.id,
            'work_order_type': schedule.maintenance_type,
            'maintenance_type': schedule.maintenance_type,
            'start_date': scheduled_date,
            'end_date': end_date,
            'estimated_duration': estimated_duration,
            'job_plan_id': schedule.job_plan_id.id if schedule.job_plan_id else False,
            'description': _('Preventive maintenance work order generated from schedule: %s') % schedule.name,
            'standard_operating_procedure': schedule.job_plan_id.description if schedule.job_plan_id else '',
            'reported_by': False,  # Not applicable for planned work orders
        }
        work_order = self.env['facilities.workorder'].create(work_order_vals)

        # Copy tasks from job plan if available
        if schedule.job_plan_id:
            self._copy_job_plan_tasks_to_workorder(schedule.job_plan_id, work_order)

        # Update the last maintenance date and compute the next maintenance date
        schedule.last_maintenance_date = schedule.next_maintenance_date
        schedule._compute_next_maintenance_date()

        return work_order

    def _copy_job_plan_tasks_to_workorder(self, job_plan, work_order):
        """
        Copy tasks from job plan sections to work order sections and tasks.
        """
        for job_section in job_plan.section_ids:
            # Create work order section
            work_section_vals = {
                'name': job_section.name,
                'sequence': job_section.sequence,
                'workorder_id': work_order.id,
            }
            work_section = self.env['facilities.workorder.section'].create(work_section_vals)
            
            # Copy tasks from job plan section to work order section
            for job_task in job_section.task_ids:
                work_task_vals = {
                    'workorder_id': work_order.id,
                    'section_id': work_section.id,
                    'name': job_task.name,
                    'sequence': job_task.sequence,
                    'description': job_task.description,
                    'is_checklist_item': job_task.is_checklist_item,
                    'duration': job_task.duration,
                    'tools_materials': job_task.tools_materials,
                    'responsible_id': job_task.responsible_id.id if job_task.responsible_id else False,
                    'product_id': job_task.product_id.id if job_task.product_id else False,
                    'quantity': job_task.quantity,
                    'uom_id': job_task.uom_id.id if job_task.uom_id else False,
                    'frequency_type': job_task.frequency_type,
                }
                self.env['facilities.workorder.task'].create(work_task_vals)

    def action_generate_work_order(self):
        """Generates a work order for the maintenance schedule with tasks from job plan."""
        for schedule in self:
            work_order = self._create_workorder_with_tasks(schedule)
            schedule.message_post(body=_("Work order %s has been generated with %s tasks.") % 
                               (work_order.name, len(work_order.workorder_task_ids)))

    def toggle_active(self):
        """Toggle the active state of the maintenance schedule"""
        for schedule in self:
            schedule.active = not schedule.active
            if schedule.active:
                schedule.message_post(body=_("Maintenance schedule activated"))
            else:
                schedule.message_post(body=_("Maintenance schedule deactivated"))

    def can_assign_job_plan(self, job_plan_id):
        """Check if a job plan can be assigned to this maintenance schedule."""
        self.ensure_one()
        
        if not job_plan_id:
            return True
        
        if self.maintenance_type != 'preventive':
            return False, _("Job plans can only be assigned to preventive maintenance schedules.")
        
        # Check if job plan is active
        job_plan = self.env['maintenance.job.plan'].browse(job_plan_id)
        if not job_plan.active:
            return False, _("The selected job plan is not active.")
        
        return True, _("Job plan can be assigned.")

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to validate job plan assignment."""
        # Validate job plan assignment before creation
        for vals in vals_list:
            if vals.get('job_plan_id') and vals.get('maintenance_type') != 'preventive':
                raise UserError(_("Cannot create maintenance schedule: Job plans can only be assigned to preventive maintenance schedules."))
        
        return super().create(vals_list)

    def write(self, vals):
        """Override write to validate job plan assignment."""
        # Validate job plan assignment before writing
        if 'job_plan_id' in vals or 'maintenance_type' in vals:
            for record in self:
                new_maintenance_type = vals.get('maintenance_type', record.maintenance_type)
                new_job_plan_id = vals.get('job_plan_id', record.job_plan_id)
                
                if new_job_plan_id and new_maintenance_type != 'preventive':
                    raise UserError(_("Cannot update maintenance schedule: Job plans can only be assigned to preventive maintenance schedules."))
        
        return super().write(vals)

    @api.model
    def send_maintenance_reminder(self):
        """Cron helper: notify responsible users about due maintenance schedules.
        This matches a server action expecting model.send_maintenance_reminder()."""
        today = fields.Date.today()
        due_soon = self.search([
            ('active', '=', True),
            ('next_maintenance_date', '!=', False),
            ('next_maintenance_date', '<=', today + relativedelta(days=3)),
            ('status', 'in', ['planned', 'in_progress'])
        ])
        for rec in due_soon:
            user_id = rec.asset_id.responsible_id.id or self.env.user.id
            try:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user_id,
                    note=_('Maintenance due on %s for asset %s') % (rec.next_maintenance_date, rec.asset_id.display_name)
                )
            except Exception:
                pass
        return len(due_soon)

    def action_generate_workorders_with_lead_days(self, lead_days=30, overwrite_existing=False):
        """
        Generate work orders with specified lead days from current date.
        """
        self.ensure_one()
        
        from datetime import datetime, timedelta
        
        # Calculate the date range
        today = datetime.now().date()
        end_date = today + timedelta(days=lead_days)
        
        # Generate work orders for the specified date range
        generated_workorders = []
        
        if self.schedule_type == 'asset':
            # Asset-based generation
            if not self.asset_id:
                raise UserError(_("Asset is required for asset-based schedules."))
            
            # Generate work orders based on recurrence pattern
            work_orders = self._generate_recurring_workorders(
                self, self.asset_id, today, end_date, overwrite_existing
            )
            generated_workorders.extend(work_orders)
        
        elif self.schedule_type == 'location':
            # Location-based generation
            if not any([self.facility_id, self.building_id, self.floor_id, self.room_id]):
                raise UserError(_("At least one location is required for location-based schedules."))
            
            # Find assets in the specified location
            assets = self._find_assets_in_location()
            if not assets:
                raise UserError(_("No assets found in the specified location."))
            
            for asset in assets:
                # Generate work orders for this asset based on recurrence pattern
                work_orders = self._generate_recurring_workorders(
                    self, asset, today, end_date, overwrite_existing
                )
                generated_workorders.extend(work_orders)
        
        # Return result
        if generated_workorders:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Generated Work Orders ({len(generated_workorders)} created)',
                'res_model': 'facilities.workorder',
                'view_mode': 'list,form',
                'domain': [('id', 'in', [wo.id for wo in generated_workorders])],
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Work Orders Generated',
                    'message': 'No work orders were generated. All assets may already have work orders in the specified date range.',
                    'type': 'warning'
                }
            }

    def _check_duplicate_workorder_in_range(self, schedule, asset, start_date, end_date):
        """
        Check if a work order already exists for this schedule and asset within the date range.
        """
        existing_workorder = self.env['facilities.workorder'].search([
            ('schedule_id', '=', schedule.id),
            ('asset_id', '=', asset.id),
            ('work_order_type', '=', 'preventive'),
            ('start_date', '>=', start_date),
            ('start_date', '<=', end_date),
            ('state', '!=', 'cancelled')
        ], limit=1)
        return existing_workorder

    def _find_assets_in_location(self):
        """
        Find all assets in the specified location.
        """
        domain = []
        
        if self.room_id:
            domain.append(('room_id', '=', self.room_id.id))
        elif self.floor_id:
            domain.append(('floor_id', '=', self.floor_id.id))
        elif self.building_id:
            domain.append(('building_id', '=', self.building_id.id))
        elif self.facility_id:
            domain.append(('facility_id', '=', self.facility_id.id))
        
        domain.append(('active', '=', True))
        
        return self.env['facilities.asset'].search(domain)

    def _generate_recurring_workorders(self, schedule, asset, start_date, end_date, overwrite_existing=False):
        """
        Generate multiple work orders based on the schedule's recurrence pattern.
        """
        from datetime import datetime, timedelta
        
        generated_workorders = []
        current_date = start_date
        
        # Calculate the interval based on schedule settings
        interval_days = self._get_interval_days(schedule.interval_number, schedule.interval_type)
        
        while current_date <= end_date:
            # Check if work order already exists for this date
            if not overwrite_existing:
                existing_workorder = self._check_duplicate_workorder_in_range(
                    schedule, asset, current_date, current_date
                )
                if existing_workorder:
                    # Skip this date and move to next
                    current_date += timedelta(days=interval_days)
                    continue
            
            # Create work order for this date
            work_order = self._create_workorder_with_tasks(schedule, asset=asset, target_date=current_date)
            if work_order:
                generated_workorders.append(work_order)
            
            # Move to next date based on interval
            current_date += timedelta(days=interval_days)
        
        return generated_workorders

    def _get_interval_days(self, interval_number, interval_type):
        """
        Convert interval number and type to days.
        """
        if interval_type == 'daily':
            return interval_number
        elif interval_type == 'weekly':
            return interval_number * 7
        elif interval_type == 'monthly':
            return interval_number * 30  # Approximate
        elif interval_type == 'quarterly':
            return interval_number * 90  # Approximate
        elif interval_type == 'yearly':
            return interval_number * 365  # Approximate
        else:
            return interval_number  # Default to daily

    def action_generate_workorder_wizard(self):
        """
        Open the generate work order wizard.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generate Work Orders',
            'res_model': 'generate.workorder.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_schedule_id': self.id,
            }
        }
    
    @api.constrains('interval_number')
    def _check_interval_number(self):
        """Validate interval number is reasonable."""
        for schedule in self:
            if schedule.interval_number and schedule.interval_number <= 0:
                raise ValidationError(_("Interval number must be greater than 0."))
            if schedule.interval_number and schedule.interval_number > 1000:
                raise ValidationError(_("Interval number seems unrealistic. Please verify this value."))
    
    @api.constrains('next_maintenance_date')
    def _check_next_maintenance_date(self):
        """Validate next maintenance date is not in the past (with some tolerance)."""
        from datetime import date, timedelta
        for schedule in self:
            if schedule.next_maintenance_date and schedule.status == 'active':
                # Allow some tolerance for scheduling (7 days in the past)
                min_date = date.today() - timedelta(days=7)
                if schedule.next_maintenance_date < min_date:
                    raise ValidationError(_("Next maintenance date cannot be more than 7 days in the past for active schedules."))
    
    @api.constrains('schedule_type', 'asset_id', 'facility_id')
    def _check_schedule_asset_facility_match(self):
        """Ensure asset belongs to the specified facility for asset schedules."""
        for schedule in self:
            if schedule.schedule_type == 'asset' and schedule.asset_id and schedule.facility_id:
                if schedule.asset_id.facility_id != schedule.facility_id:
                    raise ValidationError(_("Asset '%s' does not belong to facility '%s'. Please select the correct facility.") % 
                                        (schedule.asset_id.name, schedule.facility_id.name))
    
    @api.constrains('status', 'asset_id')
    def _check_active_schedule_limit(self):
        """Prevent multiple active schedules of the same type for the same asset."""
        for schedule in self:
            if schedule.status == 'active' and schedule.schedule_type == 'asset' and schedule.asset_id:
                existing_active = self.search([
                    ('asset_id', '=', schedule.asset_id.id),
                    ('maintenance_type', '=', schedule.maintenance_type),
                    ('status', '=', 'active'),
                    ('id', '!=', schedule.id)
                ], limit=1)
                if existing_active:
                    raise ValidationError(_("Asset '%s' already has an active %s maintenance schedule. Please deactivate the existing schedule first.") % 
                                        (schedule.asset_id.name, schedule.maintenance_type))