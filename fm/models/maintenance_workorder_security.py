# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
import logging

_logger = logging.getLogger(__name__)


class MaintenanceWorkOrderSecurity(models.Model):
    """Enhanced security for maintenance work orders"""
    _name = 'maintenance.workorder.security'
    _description = 'Maintenance Work Order Security'
    _inherit = ['facilities.workorder.core']

    # Security fields
    access_level = fields.Selection([
        ('public', 'Public'),
        ('internal', 'Internal'),
        ('confidential', 'Confidential'),
        ('restricted', 'Restricted')
    ], string='Access Level', default='internal', tracking=True)
    
    security_clearance_required = fields.Boolean(string='Security Clearance Required', default=False)
    security_clearance_level = fields.Selection([
        ('basic', 'Basic'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('top_secret', 'Top Secret')
    ], string='Security Clearance Level')
    
    # Audit fields
    created_by_id = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user, readonly=True)
    last_modified_by_id = fields.Many2one('res.users', string='Last Modified By', readonly=True)
    last_modified_date = fields.Datetime(string='Last Modified Date', readonly=True)
    access_log_ids = fields.One2many('maintenance.workorder.access.log', 'workorder_id', string='Access Logs')
    
    # Permission fields
    can_view = fields.Boolean(string='Can View', compute='_compute_permissions')
    can_edit = fields.Boolean(string='Can Edit', compute='_compute_permissions')
    can_delete = fields.Boolean(string='Can Delete', compute='_compute_permissions')
    can_assign = fields.Boolean(string='Can Assign', compute='_compute_permissions')
    can_approve = fields.Boolean(string='Can Approve', compute='_compute_permissions')

    @api.depends('access_level', 'security_clearance_required', 'security_clearance_level')
    def _compute_permissions(self):
        """Compute user permissions based on security settings"""
        user = self.env.user
        
        for record in self:
            # Check basic access
            has_basic_access = user.has_group('fm.group_facilities_user')
            
            # Check access level
            has_access_level = self._check_access_level(user, record.access_level)
            
            # Check security clearance
            has_security_clearance = self._check_security_clearance(user, record)
            
            # Check specific permissions
            has_view_permission = user.has_group('fm.group_facilities_user')
            has_edit_permission = user.has_group('fm.group_maintenance_technician')
            has_delete_permission = user.has_group('fm.group_facilities_manager')
            has_assign_permission = user.has_group('fm.group_maintenance_technician')
            has_approve_permission = user.has_group('fm.group_facilities_manager')
            
            # Check if user is the creator or assigned technician
            is_creator = record.created_by_id.id == user.id
            is_assigned = record.technician_id.user_id.id == user.id if record.technician_id.user_id else False
            
            record.can_view = has_basic_access and has_access_level and has_security_clearance
            record.can_edit = (has_edit_permission or is_creator or is_assigned) and has_access_level and has_security_clearance
            record.can_delete = has_delete_permission and has_access_level and has_security_clearance
            record.can_assign = has_assign_permission and has_access_level and has_security_clearance
            record.can_approve = has_approve_permission and has_access_level and has_security_clearance

    def _check_access_level(self, user, access_level):
        """Check if user has required access level"""
        if access_level == 'public':
            return True
        elif access_level == 'internal':
            return user.has_group('base.group_user')
        elif access_level == 'confidential':
            return user.has_group('fm.group_facilities_manager')
        elif access_level == 'restricted':
            return user.has_group('base.group_system')
        return False

    def _check_security_clearance(self, user, record):
        """Check if user has required security clearance"""
        if not record.security_clearance_required:
            return True
        
        # Get user's security clearance level
        user_clearance = getattr(user, 'security_clearance_level', 'basic')
        
        # Define clearance hierarchy
        clearance_hierarchy = {
            'basic': 1,
            'intermediate': 2,
            'advanced': 3,
            'top_secret': 4
        }
        
        required_level = clearance_hierarchy.get(record.security_clearance_level, 1)
        user_level = clearance_hierarchy.get(user_clearance, 1)
        
        return user_level >= required_level

    def _log_access(self, action, details=None):
        """Log access to work order"""
        try:
            self.env['maintenance.workorder.access.log'].create({
                'workorder_id': self.id,
                'user_id': self.env.user.id,
                'action': action,
                'details': details or '',
                'access_date': fields.Datetime.now(),
                'ip_address': self.env.context.get('request_ip', 'unknown')
            })
        except Exception as e:
            _logger.warning(f"Failed to log access for work order {self.id}: {e}")

    def _check_security_before_action(self, action):
        """Check security before performing action"""
        if not self.can_view:
            raise AccessError(_('You do not have permission to view this work order.'))
        
        if action in ['edit', 'write', 'update'] and not self.can_edit:
            raise AccessError(_('You do not have permission to edit this work order.'))
        
        if action in ['delete', 'unlink'] and not self.can_delete:
            raise AccessError(_('You do not have permission to delete this work order.'))
        
        if action in ['assign', 'assign_technician'] and not self.can_assign:
            raise AccessError(_('You do not have permission to assign this work order.'))
        
        if action in ['approve', 'approve_onhold'] and not self.can_approve:
            raise AccessError(_('You do not have permission to approve this work order.'))

    def secure_read(self, fields=None, load='_classic_read'):
        """Secure read with access logging"""
        self._check_security_before_action('read')
        self._log_access('read', f"Fields: {fields}")
        return super().read(fields, load)

    def secure_write(self, vals):
        """Secure write with access logging"""
        self._check_security_before_action('edit')
        self._log_access('edit', f"Values: {vals}")
        
        # Update audit fields
        vals.update({
            'last_modified_by_id': self.env.user.id,
            'last_modified_date': fields.Datetime.now()
        })
        
        return super().write(vals)

    def secure_unlink(self):
        """Secure delete with access logging"""
        self._check_security_before_action('delete')
        self._log_access('delete')
        return super().unlink()

    def secure_action_start_progress(self):
        """Secure start progress with security checks"""
        self._check_security_before_action('edit')
        self._log_access('start_progress')
        return self.action_start_progress()

    def secure_action_complete(self):
        """Secure complete with security checks"""
        self._check_security_before_action('edit')
        self._log_access('complete')
        return self.action_complete()

    def secure_action_assign_technician(self, technician_id):
        """Secure assign technician with security checks"""
        self._check_security_before_action('assign')
        self._log_access('assign_technician', f"Technician: {technician_id}")
        return self._assign_technician(technician_id)

    def secure_action_approve_onhold(self):
        """Secure approve on-hold with security checks"""
        self._check_security_before_action('approve')
        self._log_access('approve_onhold')
        return self._approve_onhold()

    def _validate_security_constraints(self, vals):
        """Validate security constraints"""
        user = self.env.user
        
        # Check if user can modify security-sensitive fields
        security_fields = ['access_level', 'security_clearance_required', 'security_clearance_level']
        if any(field in vals for field in security_fields):
            if not user.has_group('base.group_system'):
                raise AccessError(_('Only system administrators can modify security settings.'))
        
        # Check if user can modify sensitive fields
        sensitive_fields = ['priority', 'state', 'approval_state']
        if any(field in vals for field in sensitive_fields):
            if not user.has_group('fm.group_facilities_manager'):
                raise AccessError(_('Only facility managers can modify sensitive fields.'))

    def _check_data_integrity(self, vals):
        """Check data integrity for security"""
        # Check for SQL injection attempts
        for field, value in vals.items():
            if isinstance(value, str):
                if any(keyword in value.lower() for keyword in ['drop', 'delete', 'insert', 'update', 'select']):
                    _logger.warning(f"Potential SQL injection attempt in field {field}: {value}")
                    raise ValidationError(_('Invalid data detected. Please check your input.'))

    def _encrypt_sensitive_data(self, vals):
        """Encrypt sensitive data before storing"""
        # This is a placeholder for encryption logic
        # In a real implementation, you would encrypt sensitive fields
        return vals

    def _decrypt_sensitive_data(self, record):
        """Decrypt sensitive data when reading"""
        # This is a placeholder for decryption logic
        # In a real implementation, you would decrypt sensitive fields
        return record

    def _check_audit_trail(self):
        """Check if audit trail is complete"""
        if not self.created_by_id:
            raise ValidationError(_('Audit trail incomplete: Created by field is missing.'))
        
        if not self.create_date:
            raise ValidationError(_('Audit trail incomplete: Create date is missing.'))

    def _validate_user_permissions(self, user_id):
        """Validate user permissions for specific actions"""
        user = self.env['res.users'].browse(user_id)
        
        if not user.exists():
            raise ValidationError(_('User does not exist.'))
        
        if not user.active:
            raise ValidationError(_('User is not active.'))
        
        if not user.has_group('fm.group_facilities_user'):
            raise ValidationError(_('User does not have maintenance permissions.'))

    def _check_workflow_security(self, new_state):
        """Check security for state transitions"""
        current_user = self.env.user
        
        # Check if user can perform state transition
        if new_state == 'completed' and not current_user.has_group('fm.group_maintenance_technician'):
            raise AccessError(_('Only technicians can complete work orders.'))
        
        if new_state == 'cancelled' and not current_user.has_group('fm.group_facilities_manager'):
            raise AccessError(_('Only managers can cancel work orders.'))

    def _check_field_security(self, field_name, value):
        """Check security for specific fields"""
        if field_name == 'total_cost' and value and value > 10000:
            if not self.env.user.has_group('fm.group_facilities_manager'):
                raise AccessError(_('Only managers can set costs above $10,000.'))
        
        if field_name == 'priority' and value in ['3', '4']:
            if not self.env.user.has_group('fm.group_facilities_manager'):
                raise AccessError(_('Only managers can set high priority work orders.'))

    def action_view_access_logs(self):
        """View access logs for this work order"""
        self.ensure_one()
        return {
            'name': _('Access Logs - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.workorder.access.log',
            'view_mode': 'list,form',
            'domain': [('workorder_id', '=', self.id)],
            'context': {'default_workorder_id': self.id}
        }

    def action_export_security_report(self):
        """Export security report for this work order"""
        self.ensure_one()
        
        if not self.env.user.has_group('fm.group_facilities_manager'):
            raise AccessError(_('Only managers can export security reports.'))
        
        # Generate security report
        report_data = {
            'workorder_id': self.id,
            'workorder_name': self.name,
            'access_level': self.access_level,
            'security_clearance_required': self.security_clearance_required,
            'created_by': self.created_by_id.name,
            'last_modified_by': self.last_modified_by_id.name if self.last_modified_by_id else 'N/A',
            'access_count': len(self.access_log_ids),
            'created_date': self.create_date,
            'last_modified_date': self.last_modified_date
        }
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Security Report'),
                'message': _('Security report generated successfully.'),
                'type': 'success',
            }
        }


class MaintenanceWorkOrderAccessLog(models.Model):
    """Access log for maintenance work orders"""
    _name = 'maintenance.workorder.access.log'
    _description = 'Maintenance Work Order Access Log'
    _order = 'access_date desc'

    workorder_id = fields.Many2one('facilities.workorder', string='Work Order', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='User', required=True)
    action = fields.Selection([
        ('read', 'Read'),
        ('edit', 'Edit'),
        ('delete', 'Delete'),
        ('assign', 'Assign'),
        ('approve', 'Approve'),
        ('start_progress', 'Start Progress'),
        ('complete', 'Complete'),
        ('put_on_hold', 'Put on Hold'),
        ('resume', 'Resume')
    ], string='Action', required=True)
    
    details = fields.Text(string='Details')
    access_date = fields.Datetime(string='Access Date', default=fields.Datetime.now)
    ip_address = fields.Char(string='IP Address')
    
    # Security fields
    security_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Security Level', compute='_compute_security_level', store=True)

    @api.depends('action', 'workorder_id.access_level')
    def _compute_security_level(self):
        """Compute security level based on action and work order access level"""
        for record in self:
            if record.action in ['delete', 'approve']:
                record.security_level = 'critical'
            elif record.action in ['edit', 'assign']:
                record.security_level = 'high'
            elif record.action in ['start_progress', 'complete', 'put_on_hold', 'resume']:
                record.security_level = 'medium'
            else:
                record.security_level = 'low'

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
