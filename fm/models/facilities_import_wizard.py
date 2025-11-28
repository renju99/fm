# models/facilities_import_wizard.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
import base64
import csv
import io
from datetime import datetime

_logger = logging.getLogger(__name__)


class FacilitiesImportWizard(models.TransientModel):
    _name = 'facilities.import.wizard'
    _description = 'Facilities Import/Export Wizard'

    # Import Configuration
    import_type = fields.Selection([
        ('facilities', 'Facilities'),
        ('buildings', 'Buildings'),
        ('floors', 'Floors'),
        ('rooms', 'Rooms'),
        ('assets', 'Assets')
    ], string='Import Type', required=True, default='facilities')
    
    import_file = fields.Binary(string='Import File', required=True)
    import_filename = fields.Char(string='Filename')
    file_type = fields.Selection([
        ('csv', 'CSV'),
        ('xlsx', 'Excel')
    ], string='File Type', default='csv', required=True)
    
    # Import Options
    update_existing = fields.Boolean(string='Update Existing Records', default=False,
                                   help="Update existing records instead of creating new ones")
    skip_errors = fields.Boolean(string='Skip Errors', default=False,
                               help="Continue importing even if some records have errors")
    batch_size = fields.Integer(string='Batch Size', default=100,
                              help="Number of records to process in each batch")
    
    # Mapping Configuration
    field_mapping = fields.Json(string='Field Mapping', help="JSON mapping of file columns to model fields")
    
    # Import Results
    total_records = fields.Integer(string='Total Records', default=0)
    imported_records = fields.Integer(string='Imported Records', default=0)
    updated_records = fields.Integer(string='Updated Records', default=0)
    error_records = fields.Integer(string='Error Records', default=0)
    import_log = fields.Html(string='Import Log', readonly=True)
    
    # Export Configuration
    export_type = fields.Selection([
        ('facilities', 'Facilities'),
        ('buildings', 'Buildings'),
        ('floors', 'Floors'),
        ('rooms', 'Rooms'),
        ('assets', 'Assets')
    ], string='Export Type', default='facilities')
    
    export_format = fields.Selection([
        ('csv', 'CSV'),
        ('xlsx', 'Excel')
    ], string='Export Format', default='csv')
    
    export_filters = fields.Html(string='Export Filters', 
                               help="Domain filters in JSON format for export")
    
    # Facility-specific fields for import
    facility_ids = fields.Many2many('facilities.facility', string='Facilities to Export')
    
    def action_import_data(self):
        """Import data from uploaded file"""
        self.ensure_one()
        
        if not self.import_file:
            raise UserError(_("Please upload a file to import."))
        
        try:
            # Decode the file
            file_content = base64.b64decode(self.import_file)
            
            if self.file_type == 'csv':
                return self._import_csv(file_content)
            elif self.file_type == 'xlsx':
                return self._import_excel(file_content)
            else:
                raise UserError(_("Unsupported file type."))
                
        except Exception as e:
            raise UserError(_("Error importing file: %s") % str(e))
    
    def _import_csv(self, file_content):
        """Import data from CSV file"""
        try:
            # Decode CSV content
            csv_content = file_content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            
            records = list(csv_reader)
            self.total_records = len(records)
            
            # Process records in batches
            imported = 0
            updated = 0
            errors = 0
            log_messages = []
            
            for i, record in enumerate(records):
                try:
                    if self.import_type == 'facilities':
                        result = self._import_facility(record)
                    elif self.import_type == 'buildings':
                        result = self._import_building(record)
                    elif self.import_type == 'floors':
                        result = self._import_floor(record)
                    elif self.import_type == 'rooms':
                        result = self._import_room(record)
                    elif self.import_type == 'assets':
                        result = self._import_asset(record)
                    else:
                        raise UserError(_("Unsupported import type."))
                    
                    if result == 'created':
                        imported += 1
                    elif result == 'updated':
                        updated += 1
                        
                except Exception as e:
                    errors += 1
                    log_messages.append(f"Row {i+1}: {str(e)}")
                    
                    if not self.skip_errors:
                        raise UserError(_("Error in row %d: %s") % (i+1, str(e)))
            
            # Update results
            self.write({
                'imported_records': imported,
                'updated_records': updated,
                'error_records': errors,
                'import_log': '\n'.join(log_messages) if log_messages else 'Import completed successfully'
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import Completed',
                    'message': f'Imported: {imported}, Updated: {updated}, Errors: {errors}',
                    'type': 'success' if errors == 0 else 'warning'
                }
            }
            
        except Exception as e:
            raise UserError(_("Error processing CSV file: %s") % str(e))
    
    def _import_excel(self, file_content):
        """Import data from Excel file"""
        try:
            import xlrd
            
            # Read Excel file
            workbook = xlrd.open_workbook(file_contents=file_content)
            sheet = workbook.sheet_by_index(0)
            
            # Get headers from first row
            headers = [str(cell.value) for cell in sheet.row(0)]
            
            records = []
            for row_idx in range(1, sheet.nrows):
                row_data = {}
                for col_idx, header in enumerate(headers):
                    cell_value = sheet.cell(row_idx, col_idx).value
                    row_data[header] = cell_value
                records.append(row_data)
            
            self.total_records = len(records)
            
            # Process records (similar to CSV processing)
            imported = 0
            updated = 0
            errors = 0
            log_messages = []
            
            for i, record in enumerate(records):
                try:
                    if self.import_type == 'facilities':
                        result = self._import_facility(record)
                    elif self.import_type == 'buildings':
                        result = self._import_building(record)
                    elif self.import_type == 'floors':
                        result = self._import_floor(record)
                    elif self.import_type == 'rooms':
                        result = self._import_room(record)
                    elif self.import_type == 'assets':
                        result = self._import_asset(record)
                    else:
                        raise UserError(_("Unsupported import type."))
                    
                    if result == 'created':
                        imported += 1
                    elif result == 'updated':
                        updated += 1
                        
                except Exception as e:
                    errors += 1
                    log_messages.append(f"Row {i+1}: {str(e)}")
                    
                    if not self.skip_errors:
                        raise UserError(_("Error in row %d: %s") % (i+1, str(e)))
            
            # Update results
            self.write({
                'imported_records': imported,
                'updated_records': updated,
                'error_records': errors,
                'import_log': '\n'.join(log_messages) if log_messages else 'Import completed successfully'
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import Completed',
                    'message': f'Imported: {imported}, Updated: {updated}, Errors: {errors}',
                    'type': 'success' if errors == 0 else 'warning'
                }
            }
            
        except ImportError:
            raise UserError(_("Excel import requires xlrd library. Please install it first."))
        except Exception as e:
            raise UserError(_("Error processing Excel file: %s") % str(e))
    
    def _import_facility(self, record):
        """Import facility record"""
        # Map CSV columns to facility fields
        facility_data = {
            'name': record.get('name', ''),
            'code': record.get('code', ''),
            'address': record.get('address', ''),
            'city': record.get('city', ''),
            'zip_code': record.get('zip_code', ''),
            'property_type': record.get('property_type', 'commercial'),
            'area_sqm': float(record.get('area_sqm', 0)),
            'number_of_floors': int(record.get('number_of_floors', 0)),
            'year_built': int(record.get('year_built', 0)) if record.get('year_built') else None,
            'occupancy_status': record.get('occupancy_status', 'occupied'),
            'capacity': int(record.get('capacity', 0)),
            'phone': record.get('phone', ''),
            'email': record.get('email', ''),
            'latitude': float(record.get('latitude', 0)) if record.get('latitude') else None,
            'longitude': float(record.get('longitude', 0)) if record.get('longitude') else None,
        }
        
        # Handle country and state
        if record.get('country'):
            country = self.env['res.country'].search([('name', '=', record['country'])], limit=1)
            if country:
                facility_data['country_id'] = country.id
        
        if record.get('state'):
            state = self.env['res.country.state'].search([('name', '=', record['state'])], limit=1)
            if state:
                facility_data['state_id'] = state.id
        
        # Handle manager
        if record.get('manager'):
            manager = self.env['hr.employee'].search([('name', '=', record['manager'])], limit=1)
            if manager:
                facility_data['manager_id'] = manager.id
        
        # Check if facility exists
        existing_facility = None
        if self.update_existing:
            if record.get('code'):
                existing_facility = self.env['facilities.facility'].search([('code', '=', record['code'])], limit=1)
            if not existing_facility and record.get('name'):
                existing_facility = self.env['facilities.facility'].search([('name', '=', record['name'])], limit=1)
        
        if existing_facility:
            existing_facility.write(facility_data)
            return 'updated'
        else:
            self.env['facilities.facility'].create(facility_data)
            return 'created'
    
    def _import_building(self, record):
        """Import building record"""
        building_data = {
            'name': record.get('name', ''),
            'code': record.get('code', ''),
            'address': record.get('address', ''),
            'number_of_floors': int(record.get('number_of_floors', 0)),
            'year_built': int(record.get('year_built', 0)) if record.get('year_built') else None,
        }
        
        # Handle facility
        if record.get('facility'):
            facility = self.env['facilities.facility'].search([('name', '=', record['facility'])], limit=1)
            if facility:
                building_data['facility_id'] = facility.id
        
        # Check if building exists
        existing_building = None
        if self.update_existing:
            if record.get('code'):
                existing_building = self.env['facilities.building'].search([('code', '=', record['code'])], limit=1)
            if not existing_building and record.get('name'):
                existing_building = self.env['facilities.building'].search([('name', '=', record['name'])], limit=1)
        
        if existing_building:
            existing_building.write(building_data)
            return 'updated'
        else:
            self.env['facilities.building'].create(building_data)
            return 'created'
    
    def _import_floor(self, record):
        """Import floor record"""
        floor_data = {
            'name': record.get('name', ''),
            'floor_number': int(record.get('floor_number', 0)),
            'area_sqm': float(record.get('area_sqm', 0)),
        }
        
        # Handle building
        if record.get('building'):
            building = self.env['facilities.building'].search([('name', '=', record['building'])], limit=1)
            if building:
                floor_data['building_id'] = building.id
        
        # Check if floor exists
        existing_floor = None
        if self.update_existing:
            if record.get('name') and record.get('building'):
                building = self.env['facilities.building'].search([('name', '=', record['building'])], limit=1)
                if building:
                    existing_floor = self.env['facilities.floor'].search([
                        ('name', '=', record['name']),
                        ('building_id', '=', building.id)
                    ], limit=1)
        
        if existing_floor:
            existing_floor.write(floor_data)
            return 'updated'
        else:
            self.env['facilities.floor'].create(floor_data)
            return 'created'
    
    def _import_room(self, record):
        """Import room record"""
        room_data = {
            'name': record.get('name', ''),
            'room_number': record.get('room_number', ''),
            'room_type': record.get('room_type', 'office'),
            'area_sqm': float(record.get('area_sqm', 0)),
            'capacity': int(record.get('capacity', 0)),
        }
        
        # Handle floor
        if record.get('floor'):
            floor = self.env['facilities.floor'].search([('name', '=', record['floor'])], limit=1)
            if floor:
                room_data['floor_id'] = floor.id
        
        # Check if room exists
        existing_room = None
        if self.update_existing:
            if record.get('room_number') and record.get('floor'):
                floor = self.env['facilities.floor'].search([('name', '=', record['floor'])], limit=1)
                if floor:
                    existing_room = self.env['facilities.room'].search([
                        ('room_number', '=', record['room_number']),
                        ('floor_id', '=', floor.id)
                    ], limit=1)
        
        if existing_room:
            existing_room.write(room_data)
            return 'updated'
        else:
            self.env['facilities.room'].create(room_data)
            return 'created'
    
    def _import_asset(self, record):
        """Import asset record"""
        asset_data = {
            'name': record.get('name', ''),
            'asset_code': record.get('asset_code', ''),
            'serial_number': record.get('serial_number', ''),
            'model_number': record.get('model_number', ''),
            'purchase_value': float(record.get('purchase_value', 0)),
            'condition': record.get('condition', 'good'),
            'criticality': record.get('criticality', 'medium'),
        }
        
        # Handle facility
        if record.get('facility'):
            facility = self.env['facilities.facility'].search([('name', '=', record['facility'])], limit=1)
            if facility:
                asset_data['facility_id'] = facility.id
        
        # Handle room
        if record.get('room'):
            room = self.env['facilities.room'].search([('name', '=', record['room'])], limit=1)
            if room:
                asset_data['room_id'] = room.id
        
        # Handle category
        if record.get('category'):
            category = self.env['facilities.asset.category'].search([('name', '=', record['category'])], limit=1)
            if category:
                asset_data['category_id'] = category.id
        
        # Handle dates
        if record.get('purchase_date'):
            try:
                asset_data['purchased_date'] = datetime.strptime(record['purchase_date'], '%Y-%m-%d').date()
            except:
                pass
        
        if record.get('warranty_expiration_date'):
            try:
                asset_data['warranty_expires_date'] = datetime.strptime(record['warranty_expiration_date'], '%Y-%m-%d').date()
            except:
                pass
        
        # Check if asset exists
        existing_asset = None
        if self.update_existing:
            if record.get('asset_code'):
                existing_asset = self.env['facilities.asset'].search([('asset_code', '=', record['asset_code'])], limit=1)
            if not existing_asset and record.get('serial_number'):
                existing_asset = self.env['facilities.asset'].search([('serial_number', '=', record['serial_number'])], limit=1)
        
        if existing_asset:
            existing_asset.write(asset_data)
            return 'updated'
        else:
            self.env['facilities.asset'].create(asset_data)
            return 'created'
    
    def action_export_data(self):
        """Export data to file"""
        self.ensure_one()
        
        if self.export_type == 'facilities':
            records = self.facility_ids or self.env['facilities.facility'].search([])
        elif self.export_type == 'buildings':
            records = self.env['facilities.building'].search([])
        elif self.export_type == 'floors':
            records = self.env['facilities.floor'].search([])
        elif self.export_type == 'rooms':
            records = self.env['facilities.room'].search([])
        elif self.export_type == 'assets':
            records = self.env['facilities.asset'].search([])
        else:
            raise UserError(_("Unsupported export type."))
        
        if self.export_format == 'csv':
            return self._export_csv(records)
        elif self.export_format == 'xlsx':
            return self._export_excel(records)
        else:
            raise UserError(_("Unsupported export format."))
    
    def _export_csv(self, records):
        """Export records to CSV"""
        import csv
        
        # Prepare data
        data = []
        for record in records:
            if self.export_type == 'facilities':
                row = {
                    'name': record.name,
                    'code': record.code,
                    'address': record.address,
                    'city': record.city,
                    'zip_code': record.zip_code,
                    'property_type': record.property_type,
                    'area_sqm': record.area_sqm,
                    'number_of_floors': record.number_of_floors,
                    'year_built': record.year_built,
                    'occupancy_status': record.occupancy_status,
                    'capacity': record.capacity,
                    'phone': record.phone,
                    'email': record.email,
                    'latitude': record.latitude,
                    'longitude': record.longitude,
                    'country': record.country_id.name if record.country_id else '',
                    'state': record.state_id.name if record.state_id else '',
                    'manager': record.manager_id.name if record.manager_id else '',
                }
            elif self.export_type == 'buildings':
                row = {
                    'name': record.name,
                    'code': record.code,
                    'address': record.address,
                    'number_of_floors': record.number_of_floors,
                    'year_built': record.year_built,
                    'facility': record.facility_id.name if record.facility_id else '',
                }
            elif self.export_type == 'floors':
                row = {
                    'name': record.name,
                    'floor_number': record.floor_number,
                    'area_sqm': record.area_sqm,
                    'building': record.building_id.name if record.building_id else '',
                }
            elif self.export_type == 'rooms':
                row = {
                    'name': record.name,
                    'room_number': record.room_number,
                    'room_type': record.room_type,
                    'area_sqm': record.area_sqm,
                    'capacity': record.capacity,
                    'floor': record.floor_id.name if record.floor_id else '',
                }
            elif self.export_type == 'assets':
                row = {
                    'name': record.name,
                    'asset_code': record.asset_code,
                    'serial_number': record.serial_number,
                    'model_number': record.model_number,
                    'purchase_value': record.purchase_value,
                    'current_value': record.current_value,
                    'condition': record.condition,
                    'criticality': record.criticality,
                    'facility': record.facility_id.name if record.facility_id else '',
                    'room': record.room_id.name if record.room_id else '',
                    'category': record.category_id.name if record.category_id else '',
                    'purchase_date': record.purchased_date.strftime('%Y-%m-%d') if record.purchased_date else '',
                    'warranty_expiration_date': record.warranty_expires_date.strftime('%Y-%m-%d') if record.warranty_expires_date else '',
                }
            
            data.append(row)
        
        # Create CSV content
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        
        csv_content = output.getvalue()
        
        # Create attachment
        filename = f"{self.export_type}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(csv_content.encode('utf-8')),
            'res_model': self._name,
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def _export_excel(self, records):
        """Export records to Excel"""
        try:
            import xlsxwriter
            
            # Create Excel file in memory
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet()
            
            # Prepare data (similar to CSV)
            data = []
            for record in records:
                if self.export_type == 'facilities':
                    row = {
                        'name': record.name,
                        'code': record.code,
                        'address': record.address,
                        'city': record.city,
                        'zip_code': record.zip_code,
                        'property_type': record.property_type,
                        'area_sqm': record.area_sqm,
                        'number_of_floors': record.number_of_floors,
                        'year_built': record.year_built,
                        'occupancy_status': record.occupancy_status,
                        'capacity': record.capacity,
                        'phone': record.phone,
                        'email': record.email,
                        'latitude': record.latitude,
                        'longitude': record.longitude,
                        'country': record.country_id.name if record.country_id else '',
                        'state': record.state_id.name if record.state_id else '',
                        'manager': record.manager_id.name if record.manager_id else '',
                    }
                elif self.export_type == 'buildings':
                    row = {
                        'name': record.name,
                        'code': record.code,
                        'address': record.address,
                        'number_of_floors': record.number_of_floors,
                        'year_built': record.year_built,
                        'facility': record.facility_id.name if record.facility_id else '',
                    }
                elif self.export_type == 'floors':
                    row = {
                        'name': record.name,
                        'floor_number': record.floor_number,
                        'area_sqm': record.area_sqm,
                        'building': record.building_id.name if record.building_id else '',
                    }
                elif self.export_type == 'rooms':
                    row = {
                        'name': record.name,
                        'room_number': record.room_number,
                        'room_type': record.room_type,
                        'area_sqm': record.area_sqm,
                        'capacity': record.capacity,
                        'floor': record.floor_id.name if record.floor_id else '',
                    }
                elif self.export_type == 'assets':
                    row = {
                        'name': record.name,
                        'asset_code': record.asset_code,
                        'serial_number': record.serial_number,
                        'model_number': record.model_number,
                        'purchase_value': record.purchase_value,
                        'current_value': record.current_value,
                        'condition': record.condition,
                        'criticality': record.criticality,
                        'facility': record.facility_id.name if record.facility_id else '',
                        'room': record.room_id.name if record.room_id else '',
                        'category': record.category_id.name if record.category_id else '',
                        'purchase_date': record.purchased_date.strftime('%Y-%m-%d') if record.purchased_date else '',
                        'warranty_expiration_date': record.warranty_expires_date.strftime('%Y-%m-%d') if record.warranty_expires_date else '',
                    }
                
                data.append(row)
            
            # Write headers
            if data:
                headers = list(data[0].keys())
                for col, header in enumerate(headers):
                    worksheet.write(0, col, header)
                
                # Write data
                for row, record_data in enumerate(data, 1):
                    for col, value in enumerate(record_data.values()):
                        worksheet.write(row, col, value)
            
            workbook.close()
            
            # Create attachment
            filename = f"{self.export_type}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(output.getvalue()),
                'res_model': self._name,
                'res_id': self.id,
            })
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
            
        except ImportError:
            raise UserError(_("Excel export requires xlsxwriter library. Please install it first."))
        except Exception as e:
            raise UserError(_("Error creating Excel file: %s") % str(e))
    
    def action_download_template(self):
        """Download CSV template for import"""
        template_data = self._get_template_data()
        
        # Create CSV template
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(template_data['headers'])
        writer.writerow(template_data['sample'])
        
        csv_content = output.getvalue()
        
        # Create attachment
        filename = f"{self.import_type}_template.csv"
        
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(csv_content.encode('utf-8')),
            'res_model': self._name,
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def _get_template_data(self):
        """Get template data for the selected import type"""
        if self.import_type == 'facilities':
            return {
                'headers': ['name', 'code', 'address', 'city', 'zip_code', 'property_type', 'area_sqm', 'number_of_floors', 'year_built', 'occupancy_status', 'capacity', 'phone', 'email', 'latitude', 'longitude', 'country', 'state', 'manager'],
                'sample': ['Main Office', 'FAC001', '123 Main St', 'New York', '10001', 'commercial', '5000.00', '10', '2020', 'occupied', '500', '+1-555-0123', 'office@company.com', '40.7128', '-74.0060', 'United States', 'New York', 'John Manager']
            }
        elif self.import_type == 'buildings':
            return {
                'headers': ['name', 'code', 'address', 'number_of_floors', 'year_built', 'facility'],
                'sample': ['Building A', 'BLD001', '123 Main St', '5', '2020', 'Main Office']
            }
        elif self.import_type == 'floors':
            return {
                'headers': ['name', 'floor_number', 'area_sqm', 'building'],
                'sample': ['Ground Floor', '0', '1000.00', 'Building A']
            }
        elif self.import_type == 'rooms':
            return {
                'headers': ['name', 'room_number', 'room_type', 'area_sqm', 'capacity', 'floor'],
                'sample': ['Conference Room 1', 'CR001', 'conference', '50.00', '20', 'Ground Floor']
            }
        elif self.import_type == 'assets':
            return {
                'headers': ['name', 'asset_code', 'serial_number', 'model_number', 'purchase_cost', 'current_value', 'condition', 'criticality', 'facility', 'room', 'category', 'purchase_date', 'warranty_expiration_date'],
                'sample': ['HVAC Unit 1', 'AST001', 'SN123456', 'HVAC-2020', '50000.00', '45000.00', 'good', 'medium', 'Main Office', 'Conference Room 1', 'HVAC', '2020-01-15', '2025-01-15']
            }
        
        return {'headers': [], 'sample': []}