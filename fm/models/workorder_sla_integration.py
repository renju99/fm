from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MaintenanceWorkOrder(models.Model):
    _inherit = 'facilities.workorder'

    # SLA Fields - Only define fields that don't exist in the main model
    # sla_id, sla_response_deadline, sla_resolution_deadline, sla_response_status, sla_resolution_status 
    # are already defined in the main maintenance_workorder.py file

    # Resource Utilization
    resource_utilization_ids = fields.One2many('maintenance.resource.utilization', 'workorder_id',
                                               string='Resource Utilization')
    total_resource_hours = fields.Float(string='Total Resource Hours',
                                        compute='_compute_resource_metrics', store=True)
    total_resource_cost = fields.Float(string='Total Resource Cost',
                                       compute='_compute_resource_metrics', store=True)
    resource_efficiency = fields.Float(string='Resource Efficiency (%)',
                                       compute='_compute_resource_metrics', store=True)

    # Enhanced assignment tracking
    assigned_technician_ids = fields.Many2many('hr.employee', 'workorder_technician_rel',
                                               'workorder_id', 'employee_id',
                                               string='Assigned Technicians',
                                               domain="[('is_technician', '=', True)]")

    @api.model_create_multi
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        workorders = super().create(vals_list)
        
        # Apply SLA to all created workorders
        for workorder in workorders:
            workorder._apply_sla()
        
        return workorders

    def write(self, vals):
        result = super().write(vals)
        # Reapply SLA if relevant fields change
        if any(field in vals for field in ['priority', 'asset_id', 'work_order_type']):
            for record in self:
                record._apply_sla()
        return result

    def _apply_sla(self):
        """Apply appropriate SLA to the work order based on facilities management business rules"""
        try:
            # Try to find SLA using the enhanced facilities.sla model first
            sla = self._find_enhanced_sla()
            if not sla:
                # Fallback to legacy workorder.sla model
                sla = self.env['facilities.workorder.sla'].find_matching_sla(self)
            
            if sla:
                current_time = fields.Datetime.now()
                
                # Use enhanced SLA calculation if available
                if hasattr(sla, 'calculate_business_hours_deadline'):
                    response_deadline = sla.calculate_business_hours_deadline(current_time, sla.response_time_hours)
                    resolution_deadline = sla.calculate_business_hours_deadline(current_time, sla.resolution_time_hours)
                else:
                    # Fallback to simple calculation
                    response_deadline = current_time + timedelta(hours=sla.response_time_hours)
                    resolution_deadline = current_time + timedelta(hours=sla.resolution_time_hours)
                
                self.write({
                    'sla_id': sla.id,
                    'sla_response_deadline': response_deadline,
                    'sla_resolution_deadline': resolution_deadline,
                })
        except Exception as e:
            _logger.warning(f"Failed to apply SLA to work order {self.name}: {str(e)}")
            # If SLA model doesn't exist yet, skip
            pass

    def _find_enhanced_sla(self):
        """Find SLA using enhanced facilities.sla model with business rules"""
        # Build domain based on work order characteristics
        domain = [('active', '=', True)]
        
        # Add asset criticality filter if available
        if hasattr(self, 'asset_id') and self.asset_id:
            if hasattr(self.asset_id, 'criticality_level'):
                domain.append(('asset_criticality', '=', self.asset_id.criticality_level))
        
        # Add maintenance type filter
        if hasattr(self, 'work_order_type') and self.work_order_type:
            # Map work order type to maintenance type
            type_mapping = {
                'preventive': 'preventive',
                'corrective': 'corrective',
                'predictive': 'predictive',
                'inspection': 'inspection'
            }
            maintenance_type = type_mapping.get(self.work_order_type, 'corrective')
            domain.append(('maintenance_type', '=', maintenance_type))
        
        # Add priority filter
        if hasattr(self, 'priority') and self.priority:
            domain.append(('priority_level', '=', str(self.priority)))
        
        # Add facility filter
        if hasattr(self, 'facility_id') and self.facility_id:
            domain.append(('facility_ids', 'in', [self.facility_id.id]))
        
        # Search for matching SLA, ordered by priority
        slas = self.env['facilities.sla'].search(domain, order='priority desc')
        
        if slas:
            return slas[0]  # Return highest priority match
        
        return False

    @api.depends('sla_response_deadline', 'sla_resolution_deadline', 'actual_start_date', 'actual_end_date', 'state')
    def _compute_sla_status(self):
        for record in self:
            if not record.sla_response_deadline:
                record.sla_response_status = 'on_time'
                record.sla_resolution_status = 'on_time'
                continue

            current_time = fields.Datetime.now()

            # Response SLA Status
            if record.actual_start_date:
                record.sla_response_status = 'on_time'
            else:
                time_remaining = (record.sla_response_deadline - current_time).total_seconds()
                total_time = (record.sla_response_deadline - record.create_date).total_seconds()
                percentage_used = ((total_time - time_remaining) / total_time) * 100 if total_time > 0 else 0

                if time_remaining <= 0:
                    record.sla_response_status = 'breached'
                elif percentage_used >= (record.sla_id.critical_threshold if record.sla_id else 95):
                    record.sla_response_status = 'critical'
                elif percentage_used >= (record.sla_id.warning_threshold if record.sla_id else 80):
                    record.sla_response_status = 'warning'
                else:
                    record.sla_response_status = 'on_time'

            # Resolution SLA Status
            if record.state == 'completed':
                record.sla_resolution_status = 'on_time'
            else:
                time_remaining = (record.sla_resolution_deadline - current_time).total_seconds()
                total_time = (record.sla_resolution_deadline - record.create_date).total_seconds()
                percentage_used = ((total_time - time_remaining) / total_time) * 100 if total_time > 0 else 0

                if time_remaining <= 0:
                    record.sla_resolution_status = 'breached'
                elif percentage_used >= (record.sla_id.critical_threshold if record.sla_id else 95):
                    record.sla_resolution_status = 'critical'
                elif percentage_used >= (record.sla_id.warning_threshold if record.sla_id else 80):
                    record.sla_resolution_status = 'warning'
                else:
                    record.sla_resolution_status = 'on_time'

    @api.depends('resource_utilization_ids.hours_logged', 'resource_utilization_ids.total_cost')
    def _compute_resource_metrics(self):
        for record in self:
            record.total_resource_hours = sum(record.resource_utilization_ids.mapped('hours_logged'))
            record.total_resource_cost = sum(record.resource_utilization_ids.mapped('total_cost'))

            # Calculate efficiency based on estimated vs actual hours
            estimated_duration = 0
            if record.end_date and record.start_date:
                estimated_duration = (record.end_date - record.start_date).total_seconds() / 3600.0

            if estimated_duration > 0 and record.total_resource_hours > 0:
                record.resource_efficiency = (estimated_duration / record.total_resource_hours) * 100
            else:
                record.resource_efficiency = 100.0

    def action_start_progress(self):
        """Override to track SLA response time and start resource utilization"""
        result = super().action_start_progress()

        # Create initial resource utilization records for assigned technicians
        for technician in self.assigned_technician_ids:
            self.env['maintenance.resource.utilization'].create({
                'workorder_id': self.id,
                'employee_id': technician.id,
                'start_time': fields.Datetime.now(),
                'utilization_type': 'work',
                'notes': f'Started work on {self.name}',
            })
        return result

    def action_complete(self):
        """Override to finalize resource utilization"""
        # Close any open resource utilization records
        open_utilizations = self.resource_utilization_ids.filtered(lambda r: not r.end_time)
        for util in open_utilizations:
            util.end_time = fields.Datetime.now()

        return super().action_complete()

    def action_start_time_tracking(self):
        """Start time tracking for assigned technicians"""
        self.ensure_one()
        if not self.assigned_technician_ids:
            raise UserError(_("Please assign technicians before starting time tracking."))

        # Create time tracking entries for assigned technicians
        for technician in self.assigned_technician_ids:
            existing_active = self.env['maintenance.resource.utilization'].search([
                ('employee_id', '=', technician.id),
                ('workorder_id', '=', self.id),
                ('is_active', '=', True)
            ])
            if not existing_active:
                self.env['maintenance.resource.utilization'].create({
                    'workorder_id': self.id,
                    'employee_id': technician.id,
                    'start_time': fields.Datetime.now(),
                    'utilization_type': 'work',
                    'notes': f'Manual time tracking started for {self.name}',
                })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Time Tracking Started'),
                'message': f'Time tracking started for {len(self.assigned_technician_ids)} technician(s)',
                'type': 'success',
            }
        }

    def action_stop_time_tracking(self):
        """Stop time tracking for all active entries"""
        self.ensure_one()
        active_entries = self.resource_utilization_ids.filtered(lambda r: r.is_active)
        stopped_count = 0
        for entry in active_entries:
            entry.action_stop_time_tracking()
            stopped_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Time Tracking Stopped'),
                'message': f'Stopped time tracking for {stopped_count} active entries',
                'type': 'success',
            }
        }

    def get_sla_progress(self):
        """Get SLA progress as percentage"""
        self.ensure_one()
        if not self.sla_response_deadline:
            return {'response': 0, 'resolution': 0}

        current_time = fields.Datetime.now()

        # Response progress
        total_response_time = (self.sla_response_deadline - self.create_date).total_seconds()
        elapsed_response_time = (current_time - self.create_date).total_seconds()
        response_progress = min(100,
                                (elapsed_response_time / total_response_time) * 100) if total_response_time > 0 else 0

        # Resolution progress
        total_resolution_time = (self.sla_resolution_deadline - self.create_date).total_seconds()
        elapsed_resolution_time = (current_time - self.create_date).total_seconds()
        resolution_progress = min(100, (
                    elapsed_resolution_time / total_resolution_time) * 100) if total_resolution_time > 0 else 0

        return {
            'response': response_progress,
            'resolution': resolution_progress
        }