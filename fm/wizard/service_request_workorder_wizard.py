# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ServiceRequestWorkorderWizard(models.TransientModel):
    _name = 'service.request.workorder.wizard'
    _description = 'Service Request to Work Order Conversion Wizard'

    service_request_id = fields.Many2one(
        'facilities.service.request',
        string='Service Request',
        required=True,
        readonly=True
    )
    
    # Asset Information (Optional - only for equipment-specific work)
    asset_id = fields.Many2one(
        'facilities.asset',
        string='Asset',
        help='Select only if work is for specific equipment/asset'
    )
    
    # Work Order Details
    description = fields.Html(
        string='Work Order Description',
        required=True,
        help='Detailed description of the work to be performed'
    )
    
    priority = fields.Selection([
        ('0', 'Very Low'),
        ('1', 'Low'),
        ('2', 'Normal'),
        ('3', 'High'),
        ('4', 'Very High'),
        ('5', 'Critical')
    ], string='Priority', required=True)
    
    work_order_type = fields.Selection([
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection')
    ], string='Work Order Type', default='corrective', required=True,
       help='Preventive work orders are automatically generated from maintenance schedules')
    
    maintenance_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection')
    ], string='Maintenance Type', default='corrective', required=True)
    
    # Assignment
    team_id = fields.Many2one(
        'maintenance.team',
        string='Maintenance Team'
    )
    
    technician_ids = fields.Many2many(
        'hr.employee',
        string='Assigned Technicians',
        domain=[('is_technician', '=', True)]
    )
    
    # SLA and Timing
    sla_id = fields.Many2one(
        'facilities.sla',
        string='SLA',
        required=True
    )
    
    estimated_duration = fields.Float(
        string='Estimated Duration (Hours)',
        default=2.0
    )
    
    # Location Information (Either asset OR location required)
    facility_id = fields.Many2one(
        'facilities.facility',
        string='Facility'
    )
    
    building_id = fields.Many2one(
        'facilities.building',
        string='Building',
        domain="[('facility_id', '=', facility_id)]"
    )
    
    floor_id = fields.Many2one(
        'facilities.floor',
        string='Floor',
        domain="[('building_id', '=', building_id)]"
    )
    
    room_id = fields.Many2one(
        'facilities.room',
        string='Room',
        domain="[('floor_id', '=', floor_id)]"
    )
    
    # Inspection Notes
    inspection_notes = fields.Html(
        string='Inspection Notes',
        help='Notes from the technician inspection'
    )
    
    # Job Plan
    job_plan_id = fields.Many2one(
        'maintenance.job.plan',
        string='Job Plan',
        help='Standard job plan to apply to this work order'
    )

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        """Update location fields when asset is selected"""
        if self.asset_id:
            # Update location from asset if not already set
            if not self.facility_id and self.asset_id.facility_id:
                self.facility_id = self.asset_id.facility_id
            if not self.building_id and self.asset_id.building_id:
                self.building_id = self.asset_id.building_id
            if not self.floor_id and self.asset_id.floor_id:
                self.floor_id = self.asset_id.floor_id
            if not self.room_id and self.asset_id.room_id:
                self.room_id = self.asset_id.room_id

    @api.onchange('work_order_type')
    def _onchange_work_order_type(self):
        """Sync maintenance type with work order type"""
        if self.work_order_type:
            self.maintenance_type = self.work_order_type

    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)
        
        # Set default SLA if not provided
        if 'sla_id' in fields_list and not res.get('sla_id'):
            default_sla = self.env['facilities.sla'].search([
                ('active', '=', True)
            ], limit=1)
            if default_sla:
                res['sla_id'] = default_sla.id
        
        return res

    def action_create_workorder(self):
        """Create the work order"""
        self.ensure_one()
        
        # Validate that either asset OR location is provided
        if not self.asset_id and not any([self.facility_id, self.building_id, self.floor_id, self.room_id]):
            raise UserError(_('Please select either an asset or specify a location (facility/building/floor/room) for the work order.'))
        
        # Prepare work order values
        workorder_vals = {
            'name': f'WO-{self.service_request_id.name}',
            'description': self.description,
            'priority': self.priority,
            'work_order_type': self.work_order_type,
            'maintenance_type': self.maintenance_type,
            'state': 'draft',
            'service_request_id': self.service_request_id.id,
            'sla_id': self.sla_id.id,
            'estimated_duration': self.estimated_duration,
        }
        
        # Add asset if selected
        if self.asset_id:
            workorder_vals['asset_id'] = self.asset_id.id
        
        # Add location fields for location-based work orders
        if self.facility_id:
            workorder_vals['work_location_facility_id'] = self.facility_id.id
        if self.building_id:
            workorder_vals['work_location_building_id'] = self.building_id.id
        if self.floor_id:
            workorder_vals['work_location_floor_id'] = self.floor_id.id
        if self.room_id:
            workorder_vals['work_location_room_id'] = self.room_id.id
        
        # Add team if specified
        if self.team_id:
            workorder_vals['team_id'] = self.team_id.id
        
        # Add job plan if specified
        if self.job_plan_id:
            workorder_vals['job_plan_id'] = self.job_plan_id.id
        
        # Create the work order
        workorder = self.env['facilities.workorder'].create(workorder_vals)
        
        # Assign technicians if specified
        if self.technician_ids:
            workorder.technician_ids = [(6, 0, self.technician_ids.ids)]
        
        # Update service request
        self.service_request_id.workorder_id = workorder.id
        
        # Add inspection notes to service request
        if self.inspection_notes:
            self.service_request_id.message_post(
                body=_('<h4>Inspection Notes:</h4>%s') % self.inspection_notes,
                subtype_xmlid='mail.mt_note'
            )
        
        # Post message about work order creation
        if self.asset_id:
            work_details = f'Asset: {self.asset_id.name}'
        else:
            location_parts = []
            if self.room_id:
                location_parts.append(f'Room: {self.room_id.name}')
            if self.floor_id:
                location_parts.append(f'Floor: {self.floor_id.name}')
            if self.building_id:
                location_parts.append(f'Building: {self.building_id.name}')
            if self.facility_id:
                location_parts.append(f'Facility: {self.facility_id.name}')
            work_details = f'Location: {" | ".join(location_parts)}'
        
        self.service_request_id.message_post(
            body=_('Work order %s created from service request after technician inspection.<br/>%s') % (
                workorder.name, work_details
            ),
            subtype_xmlid='mail.mt_note'
        )
        
        # Return action to view the created work order
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'res_id': workorder.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        """Cancel wizard"""
        return {'type': 'ir.actions.act_window_close'}
