# models/room.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import qrcode
import base64
from io import BytesIO
import json
import logging

_logger = logging.getLogger(__name__)

class FacilityRoomType(models.Model):
    _name = 'facilities.room.type'
    _description = 'Room Type'
    _order = 'sequence, name'

    name = fields.Char(string='Type Name', required=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

class FacilityRoom(models.Model):
    _name = 'facilities.room'
    _description = 'Facility Room'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Room Name/Number', required=True)
    code = fields.Char(string='Room Code', required=True, copy=False, readonly=True, default='New')
    floor_id = fields.Many2one('facilities.floor', string='Floor', required=True, ondelete='restrict', help="The floor this room is located on.")
    building_id = fields.Many2one('facilities.building', related='floor_id.building_id', string='Building', store=True, readonly=True, help="The building this room indirectly belongs to.")
    facility_id = fields.Many2one('facilities.facility', related='floor_id.building_id.facility_id', string='Facility', store=True, readonly=True, help="The facility this room indirectly belongs to.")
    manager_id = fields.Many2one('hr.employee', string='Room Manager')
    active = fields.Boolean(string='Active', default=True)

    # Room Specific Fields
    room_type = fields.Selection([
        ('office', 'Office'),
        ('meeting_room', 'Meeting Room'),
        ('restroom', 'Restroom'),
        ('kitchen', 'Kitchen'),
        ('storage', 'Storage'),
        ('utility', 'Utility Room'),
        ('classroom', 'Classroom'),
        ('laboratory', 'Laboratory'),
        ('other', 'Other'),
    ], string='Room Type', default='office')
    capacity = fields.Integer(string='Capacity', help="Maximum occupancy of the room.")
    hourly_rate = fields.Float(string='Hourly Rate', digits=(10, 2), help="Hourly rate for booking this room")
    area_sqm = fields.Float(string='Area (sqm)', digits=(10, 2))
    usage = fields.Html(string='Current Usage/Purpose')
    notes = fields.Html(string='Notes')

    # QR Code Fields
    qr_code_data = fields.Text(string='QR Code Data', readonly=True, help="JSON data encoded in the QR code")
    qr_code_image = fields.Binary(string='QR Code Image', readonly=True, help="Generated QR code image")
    qr_code_url = fields.Char(string='QR Code URL', readonly=True, help="URL for service request creation via QR code")
    qr_code_generated = fields.Boolean(string='QR Code Generated', default=False, help="Indicates if QR code has been generated for this room")

    # Many2many example if rooms have specific equipment categories
    # equipment_category_ids = fields.Many2many('maintenance.equipment.category', string='Equipment Categories')

    @api.model_create_multi
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('facilities.room') or 'New'
        
        return super(FacilityRoom, self).create(vals_list)

    @api.constrains('floor_id')
    def _check_floor_id(self):
        for rec in self:
            if not rec.floor_id:
                raise fields.ValidationError("A room must be linked to a Floor.")
    
    @api.constrains('area_sqm')
    def _check_room_area(self):
        """Validate room area is reasonable and doesn't exceed floor area."""
        for room in self:
            if room.area_sqm and room.area_sqm <= 0:
                raise ValidationError(_("Room area must be greater than 0."))
            
            # Check against floor area if available
            if room.area_sqm and room.floor_id.area_sqm:
                if room.area_sqm > room.floor_id.area_sqm:
                    raise ValidationError(_("Room area (%.2f sqm) cannot exceed floor area (%.2f sqm).") % 
                                        (room.area_sqm, room.floor_id.area_sqm))
    
    @api.constrains('capacity')
    def _check_room_capacity(self):
        """Validate room capacity is reasonable."""
        for room in self:
            if room.capacity and room.capacity <= 0:
                raise ValidationError(_("Room capacity must be greater than 0."))
            if room.capacity and room.capacity > 10000:
                raise ValidationError(_("Room capacity seems unrealistic. Please verify this value."))
    
    @api.constrains('code')
    def _check_room_code_unique(self):
        """Ensure room codes are unique within the same floor."""
        for room in self:
            if room.code and room.code != 'New':
                existing = self.search([
                    ('code', '=', room.code),
                    ('floor_id', '=', room.floor_id.id),
                    ('id', '!=', room.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("Room code '%s' already exists on floor '%s'.") % (room.code, room.floor_id.name))
    
    @api.constrains('name')
    def _check_room_name_unique(self):
        """Ensure room names are unique within the same floor."""
        for room in self:
            if room.name:
                existing = self.search([
                    ('name', '=', room.name),
                    ('floor_id', '=', room.floor_id.id),
                    ('id', '!=', room.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("Room name '%s' already exists on floor '%s'.") % (room.name, room.floor_id.name))

    def action_generate_qr_code(self):
        """Generate QR code for the room with service request creation URL"""
        for room in self:
            try:
                # Prepare QR code data
                qr_data = {
                    'room_id': room.id,
                    'room_name': room.name,
                    'room_code': room.code,
                    'floor_id': room.floor_id.id,
                    'floor_name': room.floor_id.name,
                    'building_id': room.building_id.id,
                    'building_name': room.building_id.name,
                    'facility_id': room.facility_id.id,
                    'facility_name': room.facility_id.name,
                    'timestamp': fields.Datetime.now().isoformat(),
                    'action': 'create_service_request'
                }
                
                # Create service request URL
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                service_request_url = f"{base_url}/my/service-request/create?room_id={room.id}"
                
                # Generate QR code
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(service_request_url)
                qr.make(fit=True)
                
                # Create QR code image
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Convert to base64
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                qr_code_image = base64.b64encode(buffer.getvalue())
                
                # Update room record
                room.write({
                    'qr_code_data': json.dumps(qr_data),
                    'qr_code_image': qr_code_image,
                    'qr_code_url': service_request_url,
                    'qr_code_generated': True
                })
                
                room.message_post(
                    body=_('QR code generated successfully for service request creation.'),
                    subject=_('QR Code Generated')
                )
                
            except Exception as e:
                _logger.error(f"Error generating QR code for room {room.name}: {str(e)}")
                raise ValidationError(_("Error generating QR code: %s") % str(e))
        
        return True

    def action_regenerate_qr_code(self):
        """Regenerate QR code for the room"""
        for room in self:
            room.action_generate_qr_code()
        
        return True

    def action_download_qr_code(self):
        """Download QR code image"""
        self.ensure_one()
        if not self.qr_code_image:
            raise ValidationError(_("No QR code available. Please generate QR code first."))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=facilities.room&id={self.id}&field=qr_code_image&filename_field=name&download=true',
            'target': 'new',
        }

    def action_view_qr_code(self):
        """View QR code in a popup window"""
        self.ensure_one()
        if not self.qr_code_image:
            raise ValidationError(_("No QR code available. Please generate QR code first."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('QR Code - %s') % self.name,
            'res_model': 'facilities.room',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('fm.view_room_qr_code_form').id,
            'target': 'new',
            'context': {'show_qr_code': True}
        }

    @api.model
    def get_room_data_from_qr(self, room_id):
        """Get room data for service request creation from QR code"""
        room = self.browse(room_id)
        if not room.exists():
            return False
        
        return {
            'room_id': room.id,
            'room_name': room.name,
            'room_code': room.code,
            'floor_id': room.floor_id.id,
            'floor_name': room.floor_id.name,
            'building_id': room.building_id.id,
            'building_name': room.building_id.name,
            'facility_id': room.facility_id.id,
            'facility_name': room.facility_id.name,
        }