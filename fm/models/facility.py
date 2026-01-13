# models/facility.py
from odoo import models, fields, api
import logging
from odoo.exceptions import UserError
from odoo.tools.translate import _
from datetime import date, datetime, timedelta
import base64

_logger = logging.getLogger(__name__)


class Facility(models.Model):
    _name = 'facilities.facility'
    _description = 'Facility Management'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Standard Odoo fields for multi-company and audit
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company, 
                                tracking=True, index=True)

    # Basic Information
    name = fields.Char(string='Facility Name', required=True, help="The official name of the facility or property.")
    code = fields.Char(string='Facility Code', required=True, copy=False, readonly=True, default='New', help="Unique identifier for the facility, often auto-generated.")
    manager_id = fields.Many2one('hr.employee', string='Facility Manager', tracking=True, help="The employee responsible for managing this facility.")
    active = fields.Boolean(string='Active', default=True, help="Set to false to archive the facility.")

    # Enhanced Location Details with Google Maps Integration
    address = fields.Char(string='Address', help="Street address of the facility.")
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip_code = fields.Char(string='Zip Code')
    country_id = fields.Many2one('res.country', string='Country')
    latitude = fields.Float(string='Latitude', digits=(10, 7), help="Geographical latitude coordinate.")
    longitude = fields.Float(string='Longitude', digits=(10, 7), help="Geographical longitude coordinate.")
    map_link = fields.Char(string='Map Link', help="Link to a map service (e.g., Google Maps) for the facility location.")
    
    # NEW: Enhanced Geo-location Support
    google_maps_embed_url = fields.Html(string='Google Maps Embed', compute='_compute_google_maps_url', store=True)
    location_accuracy = fields.Selection([
        ('exact', 'Exact'),
        ('approximate', 'Approximate'),
        ('estimated', 'Estimated')
    ], string='Location Accuracy', default='exact', help="Accuracy level of the GPS coordinates")
    
    # NEW: Hierarchy Navigation Support
    parent_facility_id = fields.Many2one('facilities.facility', string='Parent Facility', 
                                       help="Parent facility in the hierarchy (e.g., main campus)")
    child_facility_ids = fields.One2many('facilities.facility', 'parent_facility_id', string='Child Facilities')
    facility_level = fields.Integer(string='Hierarchy Level', compute='_compute_facility_level', store=True, recursive=True)
    full_hierarchy_path = fields.Char(string='Full Hierarchy Path', compute='_compute_hierarchy_path', store=True, recursive=True)
    
    # NEW: Bulk Import/Export Support
    import_batch_id = fields.Char(string='Import Batch ID', help="Batch identifier for bulk import operations")
    last_import_date = fields.Datetime(string='Last Import Date', help="Date of last bulk import")
    import_source = fields.Selection([
        ('csv', 'CSV Import'),
        ('xls', 'Excel Import'),
        ('api', 'API Import'),
        ('manual', 'Manual Entry')
    ], string='Import Source', default='manual')

    # Property Details
    property_type = fields.Selection([
        ('commercial', 'Commercial'),
        ('residential', 'Residential'),
        ('industrial', 'Industrial'),
        ('retail', 'Retail'),
        ('mixed_use', 'Mixed-Use'),
        ('other', 'Other'),
    ], string='Property Type', default='commercial', help="Categorization of the property.")
    area_sqm = fields.Float(string='Area (sqm)', digits=(10, 2), help="Total area of the facility in square meters.")
    number_of_floors = fields.Integer(string='Number of Floors', help="Total number of floors in the building.")
    year_built = fields.Integer(string='Year Built', help="The year the facility was constructed.")
    last_renovation_date = fields.Date(string='Last Renovation Date', help="Date of the last major renovation.")
    occupancy_status = fields.Selection([
        ('occupied', 'Occupied'),
        ('vacant', 'Vacant'),
        ('under_renovation', 'Under Renovation'),
    ], string='Occupancy Status', default='occupied', help="Current occupancy status of the facility.")
    capacity = fields.Integer(string='Capacity', help="Maximum occupancy or functional capacity of the facility.")

    # Contact & Access Information
    contact_person_id = fields.Many2one('res.partner', string='Primary Contact Person', help="Main contact person associated with this facility (e.g., owner, key tenant).")
    phone = fields.Char(string='Phone Number', help="Primary phone number for the facility.")
    email = fields.Char(string='Email Address', help="Primary email address for the facility.")
    
    # Tenant & Landlord Management
    landlord_partner_id = fields.Many2one('res.partner', string='Landlord', 
                                         domain="[('is_landlord', '=', True)]",
                                         tracking=True, help="Owner/landlord of this facility")
    tenant_partner_id = fields.Many2one('res.partner', string='Current Tenant',
                                       domain="[('is_tenant', '=', True)]", 
                                       tracking=True, help="Current primary tenant")
    lease_ids = fields.One2many('facilities.lease', 'facility_id', string='Leases')
    current_lease_id = fields.Many2one('facilities.lease', string='Current Lease',
                                      compute='_compute_current_lease', store=True)
    lease_count = fields.Integer(string='Lease Count', compute='_compute_lease_count')
    # Reporting configuration
    monthly_report_user_ids = fields.Many2many(
        'res.users',
        'facilities_facility_monthly_user_rel',
        'facility_id',
        'user_id',
        string='Monthly Report Recipients',
        help='Users who should receive the monthly facility report for this facility.',
        tracking=True,
    )
    access_instructions = fields.Html(string='Access Instructions', help="Detailed instructions for accessing the facility, e.g., gate codes, key locations.")

    # Utility & Services Information
    electricity_meter_id = fields.Char(string='Electricity Meter ID', help="Identifier for the electricity meter.")
    water_meter_id = fields.Char(string='Water Meter ID', help="Identifier for the water meter.")
    gas_meter_id = fields.Char(string='Gas Meter ID', help="Identifier for the gas meter.")
    internet_provider = fields.Char(string='Internet Provider', help="Main internet service provider.")

    # Documentation
    notes = fields.Html(string='Internal Notes', help="Any additional internal notes or remarks about the facility.")
    documents_ids = fields.Many2many('ir.attachment', string='Facility Documents',
                                    domain="[('res_model','=','facilities.facility')]", help="Attached documents related to the facility (e.g., blueprints, floor plans).")

    # One2many relationship to Buildings
    building_ids = fields.One2many('facilities.building', 'facility_id', string='Buildings', help="List of buildings associated with this facility.")
    building_count = fields.Integer(compute='_compute_building_count', string='Number of Buildings', store=True)

    # Work Order Statistics
    workorder_count = fields.Integer(compute='_compute_workorder_stats', string='Total Work Orders', store=True)
    workorder_completed_count = fields.Integer(compute='_compute_workorder_stats', string='Completed Work Orders', store=True)
    workorder_in_progress_count = fields.Integer(compute='_compute_workorder_stats', string='In Progress Work Orders', store=True)
    workorder_draft_count = fields.Integer(compute='_compute_workorder_stats', string='Draft Work Orders', store=True)
    workorder_cancelled_count = fields.Integer(compute='_compute_workorder_stats', string='Cancelled Work Orders', store=True)
    
    # SLA Statistics
    sla_compliant_count = fields.Integer(compute='_compute_workorder_stats', string='SLA Compliant', store=True)
    sla_breached_count = fields.Integer(compute='_compute_workorder_stats', string='SLA Breached', store=True)
    sla_at_risk_count = fields.Integer(compute='_compute_workorder_stats', string='SLA At Risk', store=True)
    sla_compliance_rate = fields.Float(compute='_compute_workorder_stats', string='SLA Compliance Rate (%)', store=True)
    
    # Cost Statistics
    total_workorder_cost = fields.Monetary(compute='_compute_workorder_stats', string='Total Work Order Cost', currency_field='currency_id', store=True)
    avg_workorder_cost = fields.Monetary(compute='_compute_workorder_stats', string='Average Work Order Cost', currency_field='currency_id', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Report Generation Fields
    report_generation_date = fields.Char(compute='_compute_report_generation_date', string='Report Generation Date', store=False)

    @api.depends('building_ids')
    def _compute_building_count(self):
        for rec in self:
            rec.building_count = len(rec.building_ids)

    @api.depends('building_ids', 'building_ids.asset_ids')
    def _compute_workorder_stats(self):
        """Compute work order statistics for the facility"""
        for facility in self:
            # Get all work orders for this facility
            workorders = self.env['facilities.workorder'].search([
                ('facility_id', '=', facility.id)
            ])
            
            # Work order counts by status
            facility.workorder_count = len(workorders)
            facility.workorder_completed_count = len(workorders.filtered(lambda w: w.state == 'completed'))
            facility.workorder_in_progress_count = len(workorders.filtered(lambda w: w.state == 'in_progress'))
            facility.workorder_draft_count = len(workorders.filtered(lambda w: w.state == 'draft'))
            facility.workorder_cancelled_count = len(workorders.filtered(lambda w: w.state == 'cancelled'))
            
            # SLA statistics
            facility.sla_compliant_count = len(workorders.filtered(lambda w: w.sla_status == 'on_time'))
            facility.sla_breached_count = len(workorders.filtered(lambda w: w.sla_status == 'breached'))
            facility.sla_at_risk_count = len(workorders.filtered(lambda w: w.sla_status == 'at_risk'))
            
            # Calculate SLA compliance rate
            if facility.workorder_count > 0:
                facility.sla_compliance_rate = (facility.sla_compliant_count / facility.workorder_count) * 100
            else:
                facility.sla_compliance_rate = 0.0
            
            # Cost statistics
            facility.total_workorder_cost = sum(workorders.mapped('total_cost'))
            if facility.workorder_count > 0:
                facility.avg_workorder_cost = facility.total_workorder_cost / facility.workorder_count
            else:
                facility.avg_workorder_cost = 0.0

    @api.depends('latitude', 'longitude')
    def _compute_google_maps_url(self):
        for facility in self:
            if facility.latitude and facility.longitude:
                embed_url = f"https://www.google.com/maps/embed/v1/view?key=YOUR_API_KEY&center={facility.latitude},{facility.longitude}&zoom=15"
                facility.google_maps_embed_url = f'''
                <iframe src="{embed_url}" 
                        width="100%" height="400" frameborder="0" 
                        style="border:0;" allowfullscreen="" 
                        loading="lazy" referrerpolicy="no-referrer-when-downgrade">
                </iframe>
                '''
            else:
                facility.google_maps_embed_url = False

    @api.depends('lease_ids', 'lease_ids.state')
    def _compute_current_lease(self):
        """Find the current active lease"""
        for facility in self:
            current_lease = facility.lease_ids.filtered(
                lambda l: l.state == 'active'
            )[:1]  # Get first active lease
            facility.current_lease_id = current_lease.id if current_lease else False

    @api.depends('lease_ids')
    def _compute_lease_count(self):
        """Count total leases for this facility"""
        for facility in self:
            facility.lease_count = len(facility.lease_ids)

    def action_view_leases(self):
        """View leases for this facility"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Leases for {self.name}',
            'res_model': 'facilities.lease',
            'view_mode': 'list,form',
            'domain': [('facility_id', '=', self.id)],
            'context': {'default_facility_id': self.id},
        }

    @api.depends('parent_facility_id', 'parent_facility_id.facility_level')
    def _compute_facility_level(self):
        for facility in self:
            if facility.parent_facility_id:
                facility.facility_level = facility.parent_facility_id.facility_level + 1
            else:
                facility.facility_level = 0

    @api.depends('name', 'parent_facility_id', 'parent_facility_id.full_hierarchy_path')
    def _compute_hierarchy_path(self):
        for facility in self:
            if facility.parent_facility_id and facility.parent_facility_id.full_hierarchy_path:
                facility.full_hierarchy_path = f"{facility.parent_facility_id.full_hierarchy_path} > {facility.name}"
            else:
                facility.full_hierarchy_path = facility.name

    @api.depends()
    def _compute_report_generation_date(self):
        """Compute the current date and time for report generation"""
        from datetime import datetime
        for facility in self:
            current_time = datetime.now()
            facility.report_generation_date = current_time.strftime('%B %d, %Y at %I:%M %p')

    @api.model_create_multi
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('facilities.facility') or 'New'
        
        return super(Facility, self).create(vals_list)

    def action_view_hierarchy(self):
        """Action to view the facility hierarchy in a tree view"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facility Hierarchy',
            'res_model': 'facilities.facility',
            'view_mode': 'list,form',
            'domain': [('id', 'child_of', self.id)],
            'context': {'default_parent_facility_id': self.id},
        }

    def action_export_facilities_csv(self):
        """Export facilities data to CSV format"""
        return {
            'type': 'ir.actions.act_url',
            'url': f'/facilities/export/csv?facility_ids={",".join(str(x) for x in self.ids)}',
            'target': 'self',
        }

    def action_import_facilities_csv(self):
        """Import facilities data from CSV format"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Import Facilities',
            'res_model': 'facilities.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_facility_ids': self.ids},
        }

    def get_facility_workorders(self):
        """Get all work orders for this facility with detailed information"""
        workorders = self.env['facilities.workorder'].search([
            ('facility_id', '=', self.id)
        ], order='priority desc, start_date desc')
        
        return workorders

    def action_generate_facility_report(self):
        """Generate comprehensive facility report with work orders and SLA status"""
        # Ensure we have a single facility record
        if len(self) != 1:
            raise UserError(_("Please select exactly one facility to generate the report."))
        
        facility = self[0]
        
        # Ensure all computed fields are computed before generating the report
        facility.ensure_computed_fields_ready()
        
        # Verify report readiness
        readiness_status = facility.verify_report_readiness()
        
        if not readiness_status['ready']:
            error_msg = _("Facility '%s' is not ready for report generation. ") % facility.name
            if not readiness_status['has_buildings'] and not readiness_status['has_workorders']:
                error_msg += _("Please ensure the facility has buildings or work orders before generating the report.")
            elif not readiness_status['computed_fields_ready']:
                error_msg += _("Some computed fields are not properly calculated. Please try refreshing the facility data.")
            else:
                error_msg += _("Unknown issue with report readiness.")
            
            raise UserError(error_msg)
        
        # Open the facility report wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Facility Report'),
            'res_model': 'facility.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_facility_id': facility.id},
        }

    def refresh_all_computed_fields(self):
        """Refresh all computed fields manually - useful for reporting"""
        self.ensure_one()
        
        # Force recompute of all computed fields
        self._compute_workorder_stats()
        self._compute_building_count()
        self._compute_google_maps_url()
        self._compute_facility_level()
        self._compute_hierarchy_path()
        
        # Log the computed values for debugging
        _logger.info(f"Facility {self.name} refreshed computed fields: "
                    f"workorder_count={self.workorder_count}, "
                    f"building_count={self.building_count}, "
                    f"sla_compliance_rate={self.sla_compliance_rate}")
        
        return True

    def ensure_computed_fields_ready(self):
        """Ensure all computed fields are properly calculated for reporting"""
        self.ensure_one()
        
        # Force recompute of all computed fields
        self._compute_workorder_stats()
        self._compute_building_count()
        self._compute_google_maps_url()
        self._compute_facility_level()
        self._compute_hierarchy_path()
        
        # Log the computed values for debugging
        _logger.info(f"Facility {self.name} computed fields: "
                    f"workorder_count={self.workorder_count}, "
                    f"building_count={self.building_count}, "
                    f"sla_compliance_rate={self.sla_compliance_rate}")
        
        return True

    def force_refresh_computed_fields(self):
        """Force refresh all computed fields by invalidating and recomputing"""
        self.ensure_one()
        
        # Invalidate all computed fields
        fields_to_invalidate = [
            'workorder_count', 'workorder_completed_count', 'workorder_in_progress_count',
            'workorder_draft_count', 'workorder_cancelled_count', 'sla_compliant_count',
            'sla_breached_count', 'sla_at_risk_count', 'sla_compliance_rate',
            'total_workorder_cost', 'avg_workorder_cost', 'building_count'
        ]
        
        self.invalidate_recordset(fields_to_invalidate)
        
        # Force recompute
        self.ensure_computed_fields_ready()
        
        return True

    def prepare_for_report(self):
        """Prepare the facility for report generation by ensuring all computed fields are computed"""
        self.ensure_one()
        
        # Force recompute of all computed fields
        self.ensure_computed_fields_ready()
        
        # Ensure the report generation date is computed
        self._compute_report_generation_date()
        
        return True

    def test_report_data(self):
        """Test method to verify report data is available"""
        self.ensure_one()
        
        # Ensure computed fields are ready
        self.ensure_one()
        
        # Get work orders
        workorders = self.get_facility_workorders()
        
        # Prepare test data
        test_data = {
            'facility_name': self.name,
            'facility_code': self.code,
            'workorder_count': self.workorder_count,
            'building_count': self.building_count,
            'workorders_found': len(workorders),
            'workorder_ids': workorders.ids,
            'computed_fields': {
                'workorder_completed_count': self.workorder_completed_count,
                'workorder_in_progress_count': self.workorder_in_progress_count,
                'sla_compliance_rate': self.sla_compliance_rate,
                'total_workorder_cost': self.total_workorder_cost,
            }
        }
        
        _logger.info(f"Test report data for facility {self.name}: {test_data}")
        return test_data

    def verify_report_readiness(self):
        """Verify that the facility is ready for report generation"""
        self.ensure_one()
        
        # Refresh computed fields
        self.refresh_all_computed_fields()
        
        # Check if we have the minimum required data
        has_buildings = bool(self.building_ids)
        has_workorders = bool(self.get_facility_workorders())
        
        # Check if computed fields are properly calculated
        computed_fields_ready = all([
            self.workorder_count is not None,
            self.building_count is not None,
            self.sla_compliance_rate is not None
        ])
        
        status = {
            'ready': has_buildings or has_workorders,
            'has_buildings': has_buildings,
            'has_workorders': has_workorders,
            'computed_fields_ready': computed_fields_ready,
            'workorder_count': self.workorder_count,
            'building_count': self.building_count,
            'sla_compliance_rate': self.sla_compliance_rate,
        }
        
        _logger.info(f"Facility {self.name} report readiness: {status}")
        return status

    def action_refresh_facility_data(self):
        """Action method for the refresh button - provides user feedback"""
        self.ensure_one()
        
        # Refresh all computed fields
        self.refresh_all_computed_fields()
        
        # Get readiness status
        readiness = self.verify_report_readiness()
        
        # Prepare user message
        if readiness['ready']:
            message = _("✅ Facility data refreshed successfully!\n\n")
            message += _("📊 Current status:\n")
            message += _("• Work orders: %d\n") % readiness['workorder_count']
            message += _("• Buildings: %d\n") % readiness['building_count']
            message += _("• SLA compliance: %.1f%%\n") % readiness['sla_compliance_rate']
            message += _("\nThe facility is ready for report generation.")
        else:
            message = _("⚠️ Facility data refreshed, but some issues were found:\n\n")
            if not readiness['has_buildings'] and not readiness['has_workorders']:
                message += _("• No buildings or work orders found\n")
            if not readiness['computed_fields_ready']:
                message += _("• Some computed fields could not be calculated\n")
            message += _("\nPlease ensure the facility has the necessary data before generating reports.")
        
        # Show user message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Facility Data Refresh'),
                'message': message,
                'type': 'success' if readiness['ready'] else 'warning',
                'sticky': False,
            }
        }

    def test_report_generation(self):
        """Test method to verify report generation without actually generating the report"""
        self.ensure_one()
        
        try:
            # Verify report readiness
            readiness = self.verify_report_readiness()
            
            # Test the wizard action creation
            wizard_action = self.action_generate_facility_report()
            
            # Prepare test results
            test_results = {
                'success': True,
                'readiness_status': readiness,
                'wizard_action': wizard_action,
                'message': _("✅ Report generation test successful! The facility is ready for reporting. Click 'Generate Report' to open the wizard.")
            }
            
            _logger.info(f"Report generation test successful for facility {self.name}: {test_results}")
            
        except Exception as e:
            test_results = {
                'success': False,
                'error': str(e),
                'message': _("❌ Report generation test failed: %s") % str(e)
            }
            
            _logger.error(f"Report generation test failed for facility {self.name}: {test_results}")
        
        # Show user message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Report Generation Test'),
                'message': test_results['message'],
                'type': 'success' if test_results['success'] else 'error',
                'sticky': False,
            }
        }

    # ===============================
    # Automated Monthly/Weekly/Daily Report Emailing
    # ===============================

    def _get_default_recipient_email(self):
        """Determine the best recipient email for this facility."""
        self.ensure_one()
        manager_email = getattr(self.manager_id, 'user_id', False) and self.manager_id.user_id.email_formatted or False
        return manager_email or (self.email or False)

    def _generate_facility_report_attachment(self, date_from, date_to):
        """Generate the PDF report for the given period and return an ir.attachment.

        The report is rendered using the existing monthly.building.report.wizard to
        compute the data payload expected by the QWeb template.
        """
        self.ensure_one()

        # Create the wizard with the requested period
        wizard = self.env['monthly.building.report.wizard'].create({
            'facility_id': self.id,
            'date_from': date_from,
            'date_to': date_to,
        })

        # Use the wizard's action to compute the report data payload
        try:
            action = wizard.action_generate_pdf_report()
        except Exception as e:
            _logger.exception("Failed to generate action for facility report (%s): %s", self.name, e)
            raise

        # Render the PDF using the same report action and computed data
        try:
            pdf_bin, content_type = self.env['ir.actions.report']._render_qweb_pdf(
                'fm.monthly_building_report_pdf_action',
                [wizard.id],
                data=action.get('data') if isinstance(action, dict) else None,
            )
        except Exception as e:
            _logger.exception("Failed to render PDF for facility report (%s): %s", self.name, e)
            raise

        filename = "Facility_Maintenance_Report_%s_%s_to_%s.pdf" % (
            self.name,
            date_from.strftime('%Y-%m-%d'),
            date_to.strftime('%Y-%m-%d'),
        )

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'res_model': 'facilities.facility',
            'res_id': self.id,
            'type': 'binary',
            'mimetype': 'application/pdf',
            'datas': base64.b64encode(pdf_bin),
        })

        return attachment

    def _send_facility_report_email(self, attachment, period_label):
        """Send the report via email using the dedicated mail template.

        If no template is found, silently skip sending.
        """
        self.ensure_one()
        template = self.env.ref('fm.email_template_monthly_facility_report', raise_if_not_found=False)
        if not template:
            _logger.warning("Monthly facility report email template not found. Skipping email for %s.", self.name)
            return False

        # Resolve recipient emails: facility-specific recipients first, then configured report recipients, then fallback
        recipient_emails = []
        if self.monthly_report_user_ids:
            recipient_emails = [u.email for u in self.monthly_report_user_ids if u.email]

        # Pull recipients from global configuration for this report
        if not recipient_emails:
            recipient_emails = self.env['facilities.report.recipient'].get_recipient_emails(
                report_action_xmlid='fm.monthly_building_report_pdf_action',
                facility=self,
            )

        # Fallback to manager/facility email
        if not recipient_emails:
            fallback = self._get_default_recipient_email()
            recipient_emails = [fallback] if fallback else []

        if not recipient_emails:
            _logger.info("No recipient email defined for facility %s. Skipping email.", self.name)
            return False

        email_values = {
            'attachment_ids': [(4, attachment.id)],
            'email_to': ','.join(recipient_emails),
        }

        template.with_context(report_period=period_label).send_mail(
            self.id,
            force_send=True,
            raise_exception=False,
            email_values=email_values,
        )
        return True

    @api.model
    def _compute_period_range(self, period='monthly'):
        """Compute date_from and date_to for a given period.

        - daily: yesterday
        - weekly: last full week (Mon..Sun) before current week
        - monthly: previous calendar month
        """
        today = fields.Date.context_today(self)

        if period == 'daily':
            y = today - timedelta(days=1)
            return y, y
        elif period == 'weekly':
            # Start of current week (Monday)
            start_current_week = today - timedelta(days=today.weekday())
            end_last_week = start_current_week - timedelta(days=1)
            start_last_week = end_last_week - timedelta(days=6)
            return start_last_week, end_last_week
        else:
            # monthly (default): previous month
            first_day_current = date(today.year, today.month, 1)
            last_day_prev = first_day_current - timedelta(days=1)
            first_day_prev = date(last_day_prev.year, last_day_prev.month, 1)
            return first_day_prev, last_day_prev

    @api.model
    def cron_send_periodic_facility_report(self, period='monthly'):
        """Cron entry point to send periodic facility reports by email.

        period: 'daily' | 'weekly' | 'monthly'
        """
        date_from, date_to = self._compute_period_range(period=period)
        period_label = f"{date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}"

        facilities = self.search([('active', '=', True)])
        _logger.info("Starting %s facility report email job for %d facilities (%s -> %s)", period, len(facilities), date_from, date_to)

        for facility in facilities:
            try:
                recipient = facility._get_default_recipient_email()
                if not recipient:
                    continue
                attachment = facility._generate_facility_report_attachment(date_from, date_to)
                facility._send_facility_report_email(attachment, period_label)
            except Exception as e:
                _logger.exception("Failed to send %s report for facility %s: %s", period, facility.name, e)
                continue

        _logger.info("Completed %s facility report email job.", period)
        return True
    
    @api.constrains('parent_facility_id')
    def _check_facility_hierarchy(self):
        """Prevent circular references in facility hierarchy."""
        for facility in self:
            if facility.parent_facility_id:
                # Check for circular reference
                current = facility.parent_facility_id
                visited = set()
                while current:
                    if current.id == facility.id:
                        raise ValidationError(_("Circular reference detected in facility hierarchy. A facility cannot be its own parent."))
                    if current.id in visited:
                        raise ValidationError(_("Circular reference detected in facility hierarchy."))
                    visited.add(current.id)
                    current = current.parent_facility_id
                
                # Check hierarchy depth (max 5 levels)
                if len(visited) > 5:
                    raise ValidationError(_("Facility hierarchy cannot exceed 5 levels deep."))
    
    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        """Validate GPS coordinates are within valid ranges."""
        for facility in self:
            if facility.latitude and (facility.latitude < -90 or facility.latitude > 90):
                raise ValidationError(_("Latitude must be between -90 and 90 degrees."))
            if facility.longitude and (facility.longitude < -180 or facility.longitude > 180):
                raise ValidationError(_("Longitude must be between -180 and 180 degrees."))
    
    @api.constrains('code')
    def _check_facility_code_unique(self):
        """Ensure facility codes are unique within the same parent facility."""
        for facility in self:
            if facility.code and facility.code != 'New':
                domain = [('code', '=', facility.code), ('id', '!=', facility.id)]
                if facility.parent_facility_id:
                    domain.append(('parent_facility_id', '=', facility.parent_facility_id.id))
                else:
                    domain.append(('parent_facility_id', '=', False))
                
                existing = self.search(domain, limit=1)
                if existing:
                    raise ValidationError(_("Facility code '%s' already exists at this hierarchy level.") % facility.code)