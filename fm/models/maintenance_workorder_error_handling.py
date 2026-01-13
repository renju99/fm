# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError, MissingError
import logging
import traceback
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class MaintenanceWorkOrderErrorHandling(models.Model):
    """Comprehensive error handling for maintenance work orders"""
    _name = 'maintenance.workorder.error.handling'
    _description = 'Maintenance Work Order Error Handling'
    _inherit = ['facilities.workorder.core']

    # Error tracking fields
    error_count = fields.Integer(string='Error Count', compute='_compute_error_count')
    last_error_date = fields.Datetime(string='Last Error Date', compute='_compute_last_error_date')
    error_log_ids = fields.One2many('maintenance.workorder.error.log', 'workorder_id', string='Error Logs')

    @api.depends('error_log_ids')
    def _compute_error_count(self):
        """Compute total error count"""
        for record in self:
            record.error_count = len(record.error_log_ids)

    @api.depends('error_log_ids.error_date')
    def _compute_last_error_date(self):
        """Compute last error date"""
        for record in self:
            if record.error_log_ids:
                record.last_error_date = max(record.error_log_ids.mapped('error_date'))
            else:
                record.last_error_date = False

    def _log_error(self, error_type, error_message, error_details=None, user_id=None):
        """Log an error for this work order"""
        try:
            self.env['maintenance.workorder.error.log'].create({
                'workorder_id': self.id,
                'error_type': error_type,
                'error_message': error_message,
                'error_details': error_details or '',
                'error_date': fields.Datetime.now(),
                'user_id': user_id or self.env.user.id,
                'resolved': False
            })
        except Exception as e:
            _logger.error(f"Failed to log error for work order {self.id}: {e}")

    def _handle_validation_error(self, error, context=None):
        """Handle validation errors gracefully"""
        try:
            error_message = str(error)
            self._log_error('validation', error_message, context)
            
            # Show user-friendly message
            raise UserError(_(
                'Validation Error: %s\n\n'
                'Please check the data and try again. '
                'If the problem persists, contact your system administrator.'
            ) % error_message)
            
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error handling validation error: {e}")
            raise UserError(_('An unexpected error occurred. Please try again.'))

    def _handle_user_error(self, error, context=None):
        """Handle user errors gracefully"""
        try:
            error_message = str(error)
            self._log_error('user', error_message, context)
            
            # Show user-friendly message
            raise UserError(_(
                'Operation Error: %s\n\n'
                'Please check your permissions and try again. '
                'If you need assistance, contact your system administrator.'
            ) % error_message)
            
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error handling user error: {e}")
            raise UserError(_('An unexpected error occurred. Please try again.'))

    def _handle_access_error(self, error, context=None):
        """Handle access errors gracefully"""
        try:
            error_message = str(error)
            self._log_error('access', error_message, context)
            
            # Show user-friendly message
            raise AccessError(_(
                'Access Denied: %s\n\n'
                'You do not have permission to perform this action. '
                'Please contact your system administrator for access.'
            ) % error_message)
            
        except AccessError:
            raise
        except Exception as e:
            _logger.error(f"Error handling access error: {e}")
            raise AccessError(_('Access denied. Please contact your system administrator.'))

    def _handle_missing_error(self, error, context=None):
        """Handle missing record errors gracefully"""
        try:
            error_message = str(error)
            self._log_error('missing', error_message, context)
            
            # Show user-friendly message
            raise MissingError(_(
                'Record Not Found: %s\n\n'
                'The requested record could not be found. '
                'It may have been deleted or you may not have access to it.'
            ) % error_message)
            
        except MissingError:
            raise
        except Exception as e:
            _logger.error(f"Error handling missing error: {e}")
            raise MissingError(_('Record not found. Please refresh and try again.'))

    def _handle_general_error(self, error, context=None):
        """Handle general errors gracefully"""
        try:
            error_message = str(error)
            error_details = traceback.format_exc()
            self._log_error('general', error_message, error_details, context)
            
            # Show user-friendly message
            raise UserError(_(
                'System Error: %s\n\n'
                'An unexpected error occurred. '
                'The error has been logged for investigation. '
                'Please try again or contact your system administrator.'
            ) % error_message)
            
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error handling general error: {e}")
            raise UserError(_('An unexpected error occurred. Please try again.'))

    def safe_action_start_progress(self):
        """Safely start work order progress with error handling"""
        try:
            return self.action_start_progress()
        except ValidationError as e:
            self._handle_validation_error(e, {'action': 'start_progress'})
        except UserError as e:
            self._handle_user_error(e, {'action': 'start_progress'})
        except AccessError as e:
            self._handle_access_error(e, {'action': 'start_progress'})
        except Exception as e:
            self._handle_general_error(e, {'action': 'start_progress'})

    def safe_action_complete(self):
        """Safely complete work order with error handling"""
        try:
            return self.action_complete()
        except ValidationError as e:
            self._handle_validation_error(e, {'action': 'complete'})
        except UserError as e:
            self._handle_user_error(e, {'action': 'complete'})
        except AccessError as e:
            self._handle_access_error(e, {'action': 'complete'})
        except Exception as e:
            self._handle_general_error(e, {'action': 'complete'})

    def safe_action_put_on_hold(self):
        """Safely put work order on hold with error handling"""
        try:
            return self.action_put_on_hold()
        except ValidationError as e:
            self._handle_validation_error(e, {'action': 'put_on_hold'})
        except UserError as e:
            self._handle_user_error(e, {'action': 'put_on_hold'})
        except AccessError as e:
            self._handle_access_error(e, {'action': 'put_on_hold'})
        except Exception as e:
            self._handle_general_error(e, {'action': 'put_on_hold'})

    def safe_action_resume_work(self):
        """Safely resume work order with error handling"""
        try:
            return self.action_resume_work()
        except ValidationError as e:
            self._handle_validation_error(e, {'action': 'resume_work'})
        except UserError as e:
            self._handle_user_error(e, {'action': 'resume_work'})
        except AccessError as e:
            self._handle_access_error(e, {'action': 'resume_work'})
        except Exception as e:
            self._handle_general_error(e, {'action': 'resume_work'})

    def safe_action_import_job_plan_tasks(self):
        """Safely import job plan tasks with error handling"""
        try:
            return self.action_import_job_plan_tasks()
        except ValidationError as e:
            self._handle_validation_error(e, {'action': 'import_job_plan_tasks'})
        except UserError as e:
            self._handle_user_error(e, {'action': 'import_job_plan_tasks'})
        except AccessError as e:
            self._handle_access_error(e, {'action': 'import_job_plan_tasks'})
        except Exception as e:
            self._handle_general_error(e, {'action': 'import_job_plan_tasks'})

    def safe_write(self, vals):
        """Safely write values with error handling"""
        try:
            return super().write(vals)
        except ValidationError as e:
            self._handle_validation_error(e, {'action': 'write', 'vals': vals})
        except UserError as e:
            self._handle_user_error(e, {'action': 'write', 'vals': vals})
        except AccessError as e:
            self._handle_access_error(e, {'action': 'write', 'vals': vals})
        except Exception as e:
            self._handle_general_error(e, {'action': 'write', 'vals': vals})

    def safe_create(self, vals):
        """Safely create work order with error handling"""
        try:
            return super().create(vals)
        except ValidationError as e:
            self._handle_validation_error(e, {'action': 'create', 'vals': vals})
        except UserError as e:
            self._handle_user_error(e, {'action': 'create', 'vals': vals})
        except AccessError as e:
            self._handle_access_error(e, {'action': 'create', 'vals': vals})
        except Exception as e:
            self._handle_general_error(e, {'action': 'create', 'vals': vals})

    def safe_unlink(self):
        """Safely delete work order with error handling"""
        try:
            return super().unlink()
        except ValidationError as e:
            self._handle_validation_error(e, {'action': 'unlink'})
        except UserError as e:
            self._handle_user_error(e, {'action': 'unlink'})
        except AccessError as e:
            self._handle_access_error(e, {'action': 'unlink'})
        except Exception as e:
            self._handle_general_error(e, {'action': 'unlink'})

    def _validate_workorder_data(self, vals):
        """Validate work order data before operations"""
        errors = []
        
        # Validate required fields
        if 'title' in vals and not vals['title']:
            errors.append(_('Title is required'))
        
        if 'work_order_type' in vals and vals['work_order_type'] == 'preventive' and not vals.get('schedule_id'):
            errors.append(_('Preventive work orders must have a maintenance schedule'))
        
        if 'work_order_type' in vals and vals['work_order_type'] == 'corrective' and not vals.get('asset_id'):
            errors.append(_('Corrective work orders must be associated with an asset'))
        
        # Validate dates
        if 'start_date' in vals and 'end_date' in vals:
            if vals['start_date'] and vals['end_date'] and vals['end_date'] < vals['start_date']:
                errors.append(_('End date cannot be earlier than start date'))
        
        # Validate priority
        if 'priority' in vals and vals['priority'] not in ['0', '1', '2', '3', '4']:
            errors.append(_('Invalid priority value'))
        
        # Validate estimated duration
        if 'estimated_duration' in vals and vals['estimated_duration'] and vals['estimated_duration'] < 0:
            errors.append(_('Estimated duration cannot be negative'))
        
        if errors:
            raise ValidationError('\n'.join(errors))

    def _check_permissions(self, action):
        """Check permissions for specific actions"""
        user = self.env.user
        
        # Check if user has maintenance permissions
        if not user.has_group('fm.group_facilities_user'):
            raise AccessError(_('You do not have permission to perform maintenance operations'))
        
        # Check specific action permissions
        if action in ['start_progress', 'complete', 'put_on_hold', 'resume_work']:
            if not user.has_group('fm.group_maintenance_technician'):
                raise AccessError(_('You do not have permission to perform this action'))
        
        if action in ['import_job_plan_tasks', 'create', 'unlink']:
            if not user.has_group('fm.group_facilities_manager'):
                raise AccessError(_('You do not have permission to perform this action'))

    def _handle_sla_errors(self, error, context=None):
        """Handle SLA-related errors"""
        try:
            error_message = str(error)
            self._log_error('sla', error_message, context)
            
            # Show user-friendly message
            raise UserError(_(
                'SLA Error: %s\n\n'
                'There was an issue with the Service Level Agreement. '
                'Please check the SLA configuration and try again.'
            ) % error_message)
            
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error handling SLA error: {e}")
            raise UserError(_('An SLA error occurred. Please try again.'))

    def _handle_assignment_errors(self, error, context=None):
        """Handle assignment-related errors"""
        try:
            error_message = str(error)
            self._log_error('assignment', error_message, context)
            
            # Show user-friendly message
            raise UserError(_(
                'Assignment Error: %s\n\n'
                'There was an issue with technician assignment. '
                'Please check the assignment and try again.'
            ) % error_message)
            
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error handling assignment error: {e}")
            raise UserError(_('An assignment error occurred. Please try again.'))

    def _handle_cost_errors(self, error, context=None):
        """Handle cost-related errors"""
        try:
            error_message = str(error)
            self._log_error('cost', error_message, context)
            
            # Show user-friendly message
            raise UserError(_(
                'Cost Error: %s\n\n'
                'There was an issue with cost calculation. '
                'Please check the cost data and try again.'
            ) % error_message)
            
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error handling cost error: {e}")
            raise UserError(_('A cost error occurred. Please try again.'))

    def action_view_error_logs(self):
        """View error logs for this work order"""
        self.ensure_one()
        return {
            'name': _('Error Logs - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.workorder.error.log',
            'view_mode': 'list,form',
            'domain': [('workorder_id', '=', self.id)],
            'context': {'default_workorder_id': self.id}
        }

    def action_clear_errors(self):
        """Clear resolved errors for this work order"""
        self.ensure_one()
        resolved_errors = self.error_log_ids.filtered(lambda e: e.resolved)
        resolved_errors.unlink()
        
        self.message_post(
            body=_('Cleared %d resolved errors') % len(resolved_errors),
            message_type='notification'
        )

    def action_resolve_all_errors(self):
        """Mark all errors as resolved"""
        self.ensure_one()
        unresolved_errors = self.error_log_ids.filtered(lambda e: not e.resolved)
        unresolved_errors.write({'resolved': True})
        
        self.message_post(
            body=_('Marked %d errors as resolved') % len(unresolved_errors),
            message_type='notification'
        )


class MaintenanceWorkOrderErrorLog(models.Model):
    """Error log for maintenance work orders"""
    _name = 'maintenance.workorder.error.log'
    _description = 'Maintenance Work Order Error Log'
    _order = 'error_date desc'

    workorder_id = fields.Many2one('facilities.workorder', string='Work Order', required=True, ondelete='cascade')
    error_type = fields.Selection([
        ('validation', 'Validation Error'),
        ('user', 'User Error'),
        ('access', 'Access Error'),
        ('missing', 'Missing Record'),
        ('sla', 'SLA Error'),
        ('assignment', 'Assignment Error'),
        ('cost', 'Cost Error'),
        ('general', 'General Error')
    ], string='Error Type', required=True)
    
    error_message = fields.Text(string='Error Message', required=True)
    error_details = fields.Text(string='Error Details')
    error_date = fields.Datetime(string='Error Date', default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='User', required=True)
    resolved = fields.Boolean(string='Resolved', default=False)
    resolution_date = fields.Datetime(string='Resolution Date')
    resolution_notes = fields.Text(string='Resolution Notes')

    def action_resolve(self):
        """Mark error as resolved"""
        for record in self:
            record.write({
                'resolved': True,
                'resolution_date': fields.Datetime.now()
            })

    def action_view_workorder(self):
        """View related work order"""
        self.ensure_one()
        return {
            'name': _('Work Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'form',
            'res_id': self.workorder_id.id,
            'target': 'current'
        }
