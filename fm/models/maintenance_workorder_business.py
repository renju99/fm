# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class MaintenanceWorkOrderBusiness(models.Model):
    """Business logic for maintenance work orders"""
    _name = 'maintenance.workorder.business'
    _description = 'Maintenance Work Order Business Logic'

    @api.model
    def create_workorder_from_service_request(self, service_request_id, asset_id=None, **kwargs):
        """Create work order from service request"""
        service_request = self.env['facilities.service.request'].browse(service_request_id)
        
        if not service_request.exists():
            raise UserError(_('Service request not found.'))
        
        # Prepare work order values
        workorder_vals = {
            'service_request_id': service_request.id,
            'title': service_request.title,
            'description': service_request.description,
            'priority': service_request.priority,
            'facility_id': service_request.facility_id.id if service_request.facility_id else False,
            'building_id': service_request.building_id.id if service_request.building_id else False,
            'floor_id': service_request.floor_id.id if service_request.floor_id else False,
            'room_id': service_request.room_id.id if service_request.room_id else False,
            'requester_id': service_request.requester_id.id,
            'team_id': service_request.team_id.id if service_request.team_id else False,
            'sla_id': service_request.sla_id.id if service_request.sla_id else False,
        }
        
        # Add asset if provided
        if asset_id:
            workorder_vals['asset_id'] = asset_id
        
        # Add any additional values from kwargs
        workorder_vals.update(kwargs)
        
        # Create work order
        workorder = self.env['facilities.workorder'].create(workorder_vals)
        
        # Update service request
        service_request.write({
            'workorder_id': workorder.id,
            'state': 'in_progress'
        })
        
        # Post message
        workorder.message_post(
            body=_('Work order created from service request %s') % service_request.name,
            message_type='notification'
        )
        
        return workorder

    @api.model
    def assign_technician_to_workorder(self, workorder_id, technician_id, start_date=None):
        """Assign technician to work order"""
        workorder = self.env['facilities.workorder'].browse(workorder_id)
        technician = self.env['hr.employee'].browse(technician_id)
        
        if not workorder.exists():
            raise UserError(_('Work order not found.'))
        
        if not technician.exists():
            raise UserError(_('Technician not found.'))
        
        if not technician.is_technician:
            raise UserError(_('Selected employee is not a technician.'))
        
        # Create assignment
        assignment_vals = {
            'workorder_id': workorder.id,
            'technician_id': technician.id,
            'start_date': start_date or fields.Datetime.now(),
        }
        
        assignment = self.env['facilities.workorder.assignment'].create(assignment_vals)
        
        # Update work order
        workorder.write({
            'technician_id': technician.id,
            'state': 'assigned' if workorder.state == 'draft' else workorder.state
        })
        
        # Post message
        workorder.message_post(
            body=_('Technician %s assigned to work order') % technician.name,
            message_type='notification'
        )
        
        return assignment

    @api.model
    def calculate_workorder_costs(self, workorder_id):
        """Calculate total costs for work order"""
        workorder = self.env['facilities.workorder'].browse(workorder_id)
        
        if not workorder.exists():
            raise UserError(_('Work order not found.'))
        
        # Calculate labor costs from assignments
        labor_cost = sum(workorder.assignment_ids.mapped('labor_cost'))
        
        # Calculate parts costs
        parts_cost = sum(workorder.parts_used_ids.mapped('total_cost'))
        
        # Calculate total cost
        total_cost = labor_cost + parts_cost
        
        # Update work order
        workorder.write({
            'labor_cost': labor_cost,
            'parts_cost': parts_cost,
            'total_cost': total_cost
        })
        
        return {
            'labor_cost': labor_cost,
            'parts_cost': parts_cost,
            'total_cost': total_cost
        }

    @api.model
    def check_sla_compliance(self, workorder_id):
        """Check SLA compliance for work order"""
        workorder = self.env['facilities.workorder'].browse(workorder_id)
        
        if not workorder.exists() or not workorder.sla_id:
            return {'compliant': True, 'message': _('No SLA configured')}
        
        now = fields.Datetime.now()
        response_breached = False
        resolution_breached = False
        
        # Check response SLA
        if workorder.sla_response_deadline and now > workorder.sla_response_deadline:
            if not workorder.actual_start_date:
                response_breached = True
        
        # Check resolution SLA
        if workorder.sla_resolution_deadline and now > workorder.sla_resolution_deadline:
            if workorder.state != 'completed':
                resolution_breached = True
        
        if response_breached or resolution_breached:
            return {
                'compliant': False,
                'message': _('SLA breached'),
                'response_breached': response_breached,
                'resolution_breached': resolution_breached
            }
        
        return {'compliant': True, 'message': _('SLA compliant')}

    @api.model
    def escalate_workorder(self, workorder_id, escalation_level=1):
        """Escalate work order"""
        workorder = self.env['facilities.workorder'].browse(workorder_id)
        
        if not workorder.exists():
            raise UserError(_('Work order not found.'))
        
        # Get escalation recipients
        escalation_recipients = []
        if workorder.sla_id and workorder.sla_id.escalation_recipients:
            escalation_recipients = workorder.sla_id.escalation_recipients
        elif workorder.team_id and workorder.team_id.leader_id:
            escalation_recipients = [workorder.team_id.leader_id.user_id]
        
        if not escalation_recipients:
            raise UserError(_('No escalation recipients configured.'))
        
        # Create escalation record
        escalation_vals = {
            'workorder_id': workorder.id,
            'escalation_level': escalation_level,
            'escalated_to_id': escalation_recipients[0].id,
            'escalation_reason': _('Automatic escalation due to SLA breach')
        }
        
        escalation = self.env['maintenance.workorder.escalation'].create(escalation_vals)
        
        # Post message
        workorder.message_post(
            body=_('Work order escalated to level %d') % escalation_level,
            message_type='notification'
        )
        
        # Send notifications
        for recipient in escalation_recipients:
            self.env['mail.mail'].create({
                'subject': _('Work Order Escalation: %s') % workorder.name,
                'body_html': _('Work order %s has been escalated due to SLA breach.') % workorder.name,
                'email_to': recipient.email,
                'auto_delete': True
            })
        
        return escalation

    @api.model
    def generate_maintenance_report(self, date_from, date_to, facility_id=None):
        """Generate maintenance report for date range"""
        domain = [
            ('create_date', '>=', date_from),
            ('create_date', '<=', date_to)
        ]
        
        if facility_id:
            domain.append(('facility_id', '=', facility_id))
        
        workorders = self.env['facilities.workorder'].search(domain)
        
        # Calculate metrics
        total_workorders = len(workorders)
        completed_workorders = len(workorders.filtered(lambda w: w.state == 'completed'))
        on_time_completions = len(workorders.filtered(lambda w: w.state == 'completed' and w.sla_status == 'on_time'))
        sla_breaches = len(workorders.filtered(lambda w: w.sla_status == 'breached'))
        
        # Calculate averages
        avg_completion_time = 0
        if completed_workorders > 0:
            completed_with_duration = workorders.filtered(lambda w: w.state == 'completed' and w.actual_duration > 0)
            if completed_with_duration:
                avg_completion_time = sum(completed_with_duration.mapped('actual_duration')) / len(completed_with_duration)
        
        # Calculate costs
        total_labor_cost = sum(workorders.mapped('labor_cost'))
        total_parts_cost = sum(workorders.mapped('parts_cost'))
        total_cost = sum(workorders.mapped('total_cost'))
        
        return {
            'date_from': date_from,
            'date_to': date_to,
            'facility_id': facility_id,
            'total_workorders': total_workorders,
            'completed_workorders': completed_workorders,
            'on_time_completions': on_time_completions,
            'sla_breaches': sla_breaches,
            'completion_rate': (completed_workorders / total_workorders * 100) if total_workorders > 0 else 0,
            'sla_compliance_rate': (on_time_completions / completed_workorders * 100) if completed_workorders > 0 else 0,
            'avg_completion_time': avg_completion_time,
            'total_labor_cost': total_labor_cost,
            'total_parts_cost': total_parts_cost,
            'total_cost': total_cost
        }
