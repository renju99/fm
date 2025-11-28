# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class MaintenanceWorkOrderQuickCreateWizard(models.TransientModel):
    """Wizard for quick work order creation"""
    _name = 'facilities.workorder.quick.create.wizard'
    _description = 'Quick Create Work Order Wizard'

    title = fields.Char(string='Title', required=True, help='Brief description of the work to be performed')
    work_order_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection')
    ], string='Work Order Type', required=True, default='corrective')
    
    priority = fields.Selection([
        ('0', 'Very Low'), ('1', 'Low'), ('2', 'Normal'), ('3', 'High'), ('4', 'Critical')
    ], string='Priority', default='2', required=True)
    
    asset_id = fields.Many2one('facilities.asset', string='Asset', 
                              help='Select the asset that needs maintenance')
    technician_id = fields.Many2one('hr.employee', string='Technician',
                                  domain="[('is_technician', '=', True)]",
                                  help='Assign to a specific technician')
    facility_id = fields.Many2one('facilities.facility', string='Facility', required=True)
    building_id = fields.Many2one('facilities.building', string='Building')
    floor_id = fields.Many2one('facilities.floor', string='Floor')
    room_id = fields.Many2one('facilities.room', string='Room')
    
    description = fields.Html(string='Description', help='Detailed description of the work to be performed')
    estimated_duration = fields.Float(string='Estimated Duration (Hours)', default=1.0)
    start_date = fields.Date(string='Start Date', default=fields.Date.today)
    
    # Service request integration
    service_request_id = fields.Many2one('facilities.service.request', string='Service Request',
                                       help='Link to an existing service request')
    
    # Quick task creation
    quick_tasks = fields.Text(string='Quick Tasks', 
                             help='Enter tasks separated by new lines. Each line will become a task.')
    
    # Auto-assignment options
    auto_assign = fields.Boolean(string='Auto Assign', default=True,
                                help='Automatically assign to available technician')
    assign_to_team = fields.Many2one('maintenance.team', string='Assign to Team',
                                    help='Assign to a specific maintenance team')

    @api.onchange('facility_id')
    def _onchange_facility_id(self):
        """Update building options when facility changes"""
        if self.facility_id:
            return {
                'domain': {
                    'building_id': [('facility_id', '=', self.facility_id.id)]
                }
            }
        else:
            return {
                'domain': {
                    'building_id': []
                }
            }

    @api.onchange('building_id')
    def _onchange_building_id(self):
        """Update floor options when building changes"""
        if self.building_id:
            return {
                'domain': {
                    'floor_id': [('building_id', '=', self.building_id.id)]
                }
            }
        else:
            return {
                'domain': {
                    'floor_id': []
                }
            }

    @api.onchange('floor_id')
    def _onchange_floor_id(self):
        """Update room options when floor changes"""
        if self.floor_id:
            return {
                'domain': {
                    'room_id': [('floor_id', '=', self.floor_id.id)]
                }
            }
        else:
            return {
                'domain': {
                    'room_id': []
                }
            }

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        """Update location fields when asset is selected"""
        if self.asset_id:
            self.facility_id = self.asset_id.facility_id
            self.building_id = self.asset_id.building_id
            self.floor_id = self.asset_id.floor_id
            self.room_id = self.asset_id.room_id

    def action_create_workorder(self):
        """Create work order from wizard data"""
        self.ensure_one()
        
        # Validate required fields
        if not self.title:
            raise ValidationError(_('Title is required.'))
        
        if not self.facility_id:
            raise ValidationError(_('Facility is required.'))
        
        # Prepare work order values
        workorder_vals = {
            'title': self.title,
            'work_order_type': self.work_order_type,
            'priority': self.priority,
            'facility_id': self.facility_id.id,
            'building_id': self.building_id.id if self.building_id else False,
            'floor_id': self.floor_id.id if self.floor_id else False,
            'room_id': self.room_id.id if self.room_id else False,
            'description': self.description or '',
            'estimated_duration': self.estimated_duration,
            'start_date': self.start_date,
            'service_request_id': self.service_request_id.id if self.service_request_id else False,
        }
        
        # Add asset if selected
        if self.asset_id:
            workorder_vals['asset_id'] = self.asset_id.id
        
        # Auto-assign technician if requested
        if self.auto_assign and not self.technician_id:
            technician = self._find_available_technician()
            if technician:
                workorder_vals['technician_id'] = technician.id
        elif self.technician_id:
            workorder_vals['technician_id'] = self.technician_id.id
        
        # Assign to team if specified
        if self.assign_to_team:
            workorder_vals['team_id'] = self.assign_to_team.id
        
        # Create work order
        workorder = self.env['facilities.workorder'].create(workorder_vals)
        
        # Create quick tasks if provided
        if self.quick_tasks:
            self._create_quick_tasks(workorder)
        
        # Post message
        workorder.message_post(
            body=_('Work order created from quick create wizard'),
            message_type='notification'
        )
        
        # Return action to view the created work order
        return {
            'name': _('Work Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'form',
            'res_id': workorder.id,
            'target': 'current'
        }

    def _find_available_technician(self):
        """Find an available technician for assignment"""
        # Get technicians with low workload
        technicians = self.env['hr.employee'].search([
            ('is_technician', '=', True),
            ('active', '=', True)
        ])
        
        if not technicians:
            return False
        
        # Find technician with least active work orders
        min_workorders = float('inf')
        best_technician = False
        
        for technician in technicians:
            active_workorders = self.env['facilities.workorder'].search_count([
                ('technician_id', '=', technician.id),
                ('state', 'in', ['assigned', 'in_progress'])
            ])
            
            if active_workorders < min_workorders:
                min_workorders = active_workorders
                best_technician = technician
        
        return best_technician

    def _create_quick_tasks(self, workorder):
        """Create tasks from quick tasks text"""
        if not self.quick_tasks:
            return
        
        tasks = [task.strip() for task in self.quick_tasks.split('\n') if task.strip()]
        
        for i, task_name in enumerate(tasks):
            self.env['facilities.workorder.task'].create({
                'workorder_id': workorder.id,
                'name': task_name,
                'sequence': (i + 1) * 10,
                'is_checklist_item': True
            })

    def action_load_from_service_request(self):
        """Load data from selected service request"""
        self.ensure_one()
        
        if not self.service_request_id:
            raise UserError(_('Please select a service request first.'))
        
        service_request = self.service_request_id
        
        # Load data from service request
        self.title = service_request.title
        self.priority = service_request.priority
        self.facility_id = service_request.facility_id
        self.building_id = service_request.building_id
        self.floor_id = service_request.floor_id
        self.room_id = service_request.room_id
        self.description = service_request.description
        self.technician_id = service_request.assigned_to_id.employee_id if service_request.assigned_to_id else False
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Data Loaded'),
                'message': _('Data loaded from service request successfully.'),
                'type': 'success',
            }
        }

    def action_clear_form(self):
        """Clear all form fields"""
        self.ensure_one()
        
        self.write({
            'title': False,
            'work_order_type': 'corrective',
            'priority': '2',
            'asset_id': False,
            'technician_id': False,
            'facility_id': False,
            'building_id': False,
            'floor_id': False,
            'room_id': False,
            'description': False,
            'estimated_duration': 1.0,
            'start_date': fields.Date.today(),
            'service_request_id': False,
            'quick_tasks': False,
            'auto_assign': True,
            'assign_to_team': False
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Form Cleared'),
                'message': _('All form fields have been cleared.'),
                'type': 'info',
            }
        }
