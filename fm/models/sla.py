# models/sla.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

class FacilitiesSLA(models.Model):
    _name = 'facilities.sla'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Service Level Agreement'
    _order = 'priority desc, name'

    name = fields.Char(string='SLA Name', required=True)
    description = fields.Html(string='Description')
    active = fields.Boolean(string='Active', default=True)
    priority = fields.Integer(string='Priority', default=10, help="Higher number = higher priority")
    
    # Activation tracking
    activated_by_id = fields.Many2one('res.users', string='Activated By', readonly=True)
    activated_date = fields.Datetime(string='Activated Date', readonly=True)
    deactivated_by_id = fields.Many2one('res.users', string='Deactivated By', readonly=True)
    deactivated_date = fields.Datetime(string='Deactivated Date', readonly=True)
    deactivation_reason = fields.Html(string='Deactivation Reason')
    
    # SLA Timeframes
    response_time_hours = fields.Float(string='Response Time (Hours)', required=True, default=4.0)
    resolution_time_hours = fields.Float(string='Resolution Time (Hours)', required=True, default=24.0)
    warning_threshold_hours = fields.Float(string='Warning Threshold (Hours)', default=2.0, 
                                         help="Hours before deadline to trigger warning")
    escalation_delay_hours = fields.Float(string='Escalation Delay (Hours)', default=2.0,
                                        help="Hours after breach to trigger escalation")
    
    # SLA Percentage Thresholds for Status Computation
    warning_threshold = fields.Float(string='Warning Threshold (%)', default=80.0,
                                   help="Percentage of time elapsed to trigger warning status")
    critical_threshold = fields.Float(string='Critical Threshold (%)', default=95.0,
                                    help="Percentage of time elapsed to trigger critical status")
    
    # Enhanced Assignment Rules - Facilities Management Standards
    asset_criticality = fields.Selection([
        ('critical', 'Critical - Safety/Production Critical'),
        ('high', 'High - Operational Impact'),
        ('medium', 'Medium - Limited Impact'),
        ('low', 'Low - Minimal Impact')
    ], string='Asset Criticality', help="Apply to assets with this criticality level", tracking=True)
    
    maintenance_type = fields.Selection([
        ('emergency', 'Emergency - Safety/Production Critical'),
        ('urgent', 'Urgent - High Priority'),
        ('corrective', 'Corrective - Scheduled Repair'),
        ('preventive', 'Preventive - Scheduled Maintenance'),
        ('predictive', 'Predictive - Condition Based'),
        ('inspection', 'Inspection - Compliance/Quality')
    ], string='Maintenance Type', help="Apply to this maintenance type", tracking=True)
    
    priority_level = fields.Selection([
        ('0', 'Very Low'), ('1', 'Low'), ('2', 'Normal'), ('3', 'High'), ('4', 'Critical')
    ], string='Priority Level', help="Apply to work orders with this priority", tracking=True)
    
    facility_ids = fields.Many2many('facilities.facility', string='Facilities', 
                                   help="Apply to assets in these facilities")
    
    # Enhanced Escalation Configuration
    escalation_enabled = fields.Boolean(string='Enable Escalation', default=True)
    max_escalation_level = fields.Integer(string='Max Escalation Level', default=3)
    escalation_intervals_hours = fields.Text(string='Escalation Intervals (Hours)', default='2,4,8',
                                           help="Comma-separated list of hours between escalation levels")
    escalation_recipients = fields.Many2many('res.users', string='Escalation Recipients')
    
    # Escalation Matrix for Facilities Management Hierarchy
    escalation_matrix = fields.Text(string='Escalation Matrix', default='{}',
                                   help="JSON configuration for escalation hierarchy")
    
    # Notification Settings
    email_notifications = fields.Boolean(string='Email Notifications', default=True)
    sms_notifications = fields.Boolean(string='SMS Notifications', default=False)
    notification_template_id = fields.Many2one('mail.template', string='Notification Template')
    
    # Enhanced Compliance & KPI Targets
    target_mttr_hours = fields.Float(string='Target MTTR (Hours)', default=8.0,
                                    help="Target Mean Time To Repair")
    target_first_time_fix_rate = fields.Float(string='Target First Time Fix Rate (%)', default=85.0,
                                             help="Target percentage of issues resolved on first attempt")
    target_sla_compliance_rate = fields.Float(string='Target SLA Compliance Rate (%)', default=95.0,
                                             help="Target percentage of SLAs met")
    target_response_compliance = fields.Float(string='Target Response Compliance (%)', default=95.0,
                                             help="Target percentage of response SLAs met")
    target_resolution_compliance = fields.Float(string='Target Resolution Compliance (%)', default=90.0,
                                               help="Target percentage of resolution SLAs met")
    
    # Enhanced Business Hours Configuration
    business_hours_only = fields.Boolean(string='Business Hours Only', default=False,
                                        help="Apply SLA only during business hours (7 AM - 7 PM, Mon-Fri)")
    business_hours_start = fields.Float(string='Business Hours Start', default=7.0,
                                       help="Business hours start time (24-hour format)")
    business_hours_end = fields.Float(string='Business Hours End', default=19.0,
                                     help="Business hours end time (24-hour format)")
    business_days = fields.Char(string='Business Days', default='monday,tuesday,wednesday,thursday,friday',
                               help="Comma-separated list of business days")
    include_weekends = fields.Boolean(string='Include Weekends', default=True,
                                     help="Include weekends in SLA calculations")
    include_holidays = fields.Boolean(string='Include Holidays', default=False,
                                     help="Include company holidays in SLA calculations")
    
    # Performance Tracking
    total_workorders = fields.Integer(string='Total Work Orders', compute='_compute_performance_metrics', store=True)
    compliant_workorders = fields.Integer(string='Compliant Work Orders', compute='_compute_performance_metrics', store=True)
    breached_workorders = fields.Integer(string='Breached Work Orders', compute='_compute_performance_metrics', store=True)
    compliance_rate = fields.Float(string='Compliance Rate (%)', compute='_compute_performance_metrics', store=True)
    avg_mttr = fields.Float(string='Average MTTR (Hours)', compute='_compute_performance_metrics', store=True)
    
    @api.depends('name', 'active')
    def _compute_performance_metrics(self):
        # This method will be triggered when the SLA record changes
        # For reverse relationship updates, we need to handle it differently
        # Note: Since this depends on work orders, we need to ensure proper updates
        for sla in self:
            try:
                # Get all work orders for this SLA (not just completed ones for total count)
                all_workorders = self.env['facilities.workorder'].search([
                    ('sla_id', '=', sla.id)
                ])
                
                # Calculate basic metrics
                sla.total_workorders = len(all_workorders)
                
                if sla.total_workorders > 0:
                    # Count compliant and breached work orders
                    compliant_count = len(all_workorders.filtered(lambda w: w.sla_status == 'completed'))
                    breached_count = len(all_workorders.filtered(lambda w: w.sla_status == 'breached'))
                    
                    sla.compliant_workorders = compliant_count
                    sla.breached_workorders = breached_count
                    
                    # Calculate compliance rate
                    sla.compliance_rate = (compliant_count / sla.total_workorders) * 100
                    
                    # Calculate average MTTR
                    mttr_values = [w.mttr for w in all_workorders if w.mttr and w.mttr > 0]
                    sla.avg_mttr = sum(mttr_values) / len(mttr_values) if mttr_values else 0.0
                else:
                    # Set default values if no work orders
                    sla.compliant_workorders = 0
                    sla.breached_workorders = 0
                    sla.compliance_rate = 0.0
                    sla.avg_mttr = 0.0
                    
            except Exception as e:
                _logger.error(f"Error computing performance metrics for SLA {sla.id}: {str(e)}")
                # Set default values on error
                sla.total_workorders = 0
                sla.compliant_workorders = 0
                sla.breached_workorders = 0
                sla.compliance_rate = 0.0
                sla.avg_mttr = 0.0

    def get_escalation_matrix(self):
        """Get escalation matrix configuration"""
        self.ensure_one()
        try:
            return json.loads(self.escalation_matrix) if self.escalation_matrix else self._get_default_escalation_matrix()
        except (json.JSONDecodeError, TypeError):
            return self._get_default_escalation_matrix()

    def _get_default_escalation_matrix(self):
        """Get default escalation matrix based on asset criticality and maintenance type"""
        return {
            'critical': {
                'level_1': {'delay_minutes': 15, 'recipients': ['technician']},
                'level_2': {'delay_minutes': 30, 'recipients': ['supervisor']},
                'level_3': {'delay_minutes': 60, 'recipients': ['facilities_manager']},
                'level_4': {'delay_minutes': 120, 'recipients': ['operations_director']},
                'level_5': {'delay_minutes': 240, 'recipients': ['ceo']}
            },
            'high': {
                'level_1': {'delay_minutes': 30, 'recipients': ['technician']},
                'level_2': {'delay_minutes': 60, 'recipients': ['supervisor']},
                'level_3': {'delay_minutes': 120, 'recipients': ['facilities_manager']},
                'level_4': {'delay_minutes': 240, 'recipients': ['operations_director']}
            },
            'medium': {
                'level_1': {'delay_minutes': 60, 'recipients': ['technician']},
                'level_2': {'delay_minutes': 120, 'recipients': ['supervisor']},
                'level_3': {'delay_minutes': 240, 'recipients': ['facilities_manager']}
            },
            'low': {
                'level_1': {'delay_minutes': 120, 'recipients': ['technician']},
                'level_2': {'delay_minutes': 240, 'recipients': ['supervisor']}
            }
        }

    def calculate_business_hours_deadline(self, start_time, hours):
        """Calculate deadline considering business hours"""
        self.ensure_one()
        
        if not self.business_hours_only:
            # If not business hours only, add hours directly
            return start_time + timedelta(hours=hours)
        
        # Calculate business hours deadline
        current_time = start_time
        remaining_hours = hours
        
        while remaining_hours > 0:
            # Check if current time is within business hours
            if self._is_business_hour(current_time):
                # Calculate hours until end of business day
                end_of_day = self._get_end_of_business_day(current_time)
                hours_until_end = (end_of_day - current_time).total_seconds() / 3600
                
                if hours_until_end >= remaining_hours:
                    # Can complete within current business day
                    return current_time + timedelta(hours=remaining_hours)
                else:
                    # Use remaining hours of current day
                    remaining_hours -= hours_until_end
                    current_time = end_of_day
            else:
                # Move to next business day start
                current_time = self._get_next_business_day_start(current_time)
        
        return current_time

    def _is_business_hour(self, datetime_obj):
        """Check if datetime is within business hours"""
        if not self.include_weekends and datetime_obj.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        if not self.include_holidays and self._is_holiday(datetime_obj):
            return False
        
        hour = datetime_obj.hour + datetime_obj.minute / 60.0
        return self.business_hours_start <= hour < self.business_hours_end

    def _is_holiday(self, datetime_obj):
        """Check if datetime is a company holiday"""
        # This would typically check against a company holidays calendar
        # For now, return False (no holidays)
        return False

    def _get_end_of_business_day(self, datetime_obj):
        """Get end of business day for given datetime"""
        return datetime_obj.replace(
            hour=int(self.business_hours_end),
            minute=int((self.business_hours_end % 1) * 60),
            second=0,
            microsecond=0
        )

    def _get_next_business_day_start(self, datetime_obj):
        """Get next business day start time"""
        next_day = datetime_obj + timedelta(days=1)
        while not self._is_business_day(next_day):
            next_day += timedelta(days=1)
        
        return next_day.replace(
            hour=int(self.business_hours_start),
            minute=int((self.business_hours_start % 1) * 60),
            second=0,
            microsecond=0
        )

    def _is_business_day(self, datetime_obj):
        """Check if datetime is a business day"""
        if not self.include_weekends and datetime_obj.weekday() >= 5:
            return False
        
        if not self.include_holidays and self._is_holiday(datetime_obj):
            return False
        
        return True

    @api.constrains('response_time_hours', 'resolution_time_hours')
    def _check_timeframes(self):
        """Ensure response time is less than resolution time"""
        for sla in self:
            if sla.response_time_hours >= sla.resolution_time_hours:
                raise ValidationError(_('Response time must be less than resolution time'))

    @api.constrains('warning_threshold', 'critical_threshold')
    def _check_thresholds(self):
        """Ensure warning threshold is less than critical threshold"""
        for sla in self:
            if sla.warning_threshold >= sla.critical_threshold:
                raise ValidationError(_('Warning threshold must be less than critical threshold'))

    @api.constrains('max_escalation_level')
    def _check_escalation_levels(self):
        """Ensure escalation level is positive"""
        for sla in self:
            if sla.max_escalation_level <= 0:
                raise ValidationError(_('Maximum escalation level must be greater than 0'))

    def action_activate_sla(self):
        """Activate the SLA"""
        self.ensure_one()
        if not self.active:
            self.write({
                'active': True,
                'activated_by_id': self.env.user.id,
                'activated_date': fields.Datetime.now(),
                'deactivated_by_id': False,
                'deactivated_date': False,
                'deactivation_reason': False
            })
            self.message_post(body=_('SLA activated by %s') % self.env.user.name)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('SLA Activated'),
                    'message': _('SLA "%s" has been activated successfully.') % self.name,
                    'type': 'success',
                }
            }

    def action_deactivate_sla(self):
        """Deactivate the SLA"""
        self.ensure_one()
        if self.active:
            self.write({
                'active': False,
                'deactivated_by_id': self.env.user.id,
                'deactivated_date': fields.Datetime.now(),
                'activated_by_id': False,
                'activated_date': False
            })
            self.message_post(body=_('SLA deactivated by %s') % self.env.user.name)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('SLA Deactivated'),
                    'message': _('SLA "%s" has been deactivated successfully.') % self.name,
                    'type': 'warning',
                }
            }

    def action_view_workorders(self):
        """View work orders associated with this SLA"""
        self.ensure_one()
        return {
            'name': _('Work Orders - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.workorder',
            'view_mode': 'list,form',
            'domain': [('sla_id', '=', self.id)],
            'context': {'default_sla_id': self.id}
        }

    @api.model
    def create_default_sla_records(self):
        """Create default SLA records for common scenarios"""
        created_slas = self.env['facilities.sla']
        
        # Default SLA for critical assets
        critical_sla = self.search([('name', '=', 'Critical Asset SLA')], limit=1)
        if not critical_sla:
            critical_sla = self.create({
                'name': 'Critical Asset SLA',
                'description': 'Standard SLA for critical assets requiring immediate attention',
                'priority': 10,
                'response_time_hours': 2.0,
                'resolution_time_hours': 8.0,
                'warning_threshold_hours': 1.0,
                'escalation_delay_hours': 1.0,
                'asset_criticality': 'critical',
                'maintenance_type': 'corrective',
                'priority_level': '4',
                'escalation_enabled': True,
                'max_escalation_level': 3,
                'target_mttr_hours': 4.0,
                'target_first_time_fix_rate': 90.0,
                'target_sla_compliance_rate': 98.0
            })
            created_slas |= critical_sla
            _logger.info(f"Created default SLA: {critical_sla.name}")
        
        return created_slas

    def _invalidate_sla_metrics_from_workorder(self, workorder):
        """
        Invalidate SLA performance metrics when a workorder changes.
        This method is called from maintenance workorder write/create operations
        to ensure SLA metrics are recalculated when relevant fields change.
        
        Args:
            workorder: The maintenance workorder record that triggered the invalidation
        """
        if not workorder or not workorder.sla_id:
            return
        
        try:
            # Invalidate the computed fields for this SLA
            workorder.sla_id.invalidate_recordset(['total_workorders', 'compliant_workorders', 
                                                 'breached_workorders', 'compliance_rate', 'avg_mttr'])
            
            # Force recomputation of performance metrics
            workorder.sla_id._compute_performance_metrics()
            
            _logger.debug(f"SLA metrics invalidated for SLA {workorder.sla_id.id} due to workorder {workorder.id} changes")
            
        except Exception as e:
            _logger.error(f"Error invalidating SLA metrics for SLA {workorder.sla_id.id}: {str(e)}")

    def _invalidate_performance_metrics(self):
        """
        Invalidate all performance metrics for this SLA.
        This method is called when workorders are deleted to ensure metrics are updated.
        """
        try:
            # Invalidate the computed fields
            self.invalidate_recordset(['total_workorders', 'compliant_workorders', 
                                     'breached_workorders', 'compliance_rate', 'avg_mttr'])
            
            # Force recomputation
            self._compute_performance_metrics()
            
            _logger.debug(f"Performance metrics invalidated for SLA {self.id}")
            
        except Exception as e:
            _logger.error(f"Error invalidating performance metrics for SLA {self.id}: {str(e)}")
    
    def unlink(self):
        """Prevent deletion of SLAs that are in use by workorders."""
        for record in self:
            # Check for active workorders using this SLA
            workorders_using_sla = self.env['facilities.workorder'].search([
                ('sla_id', '=', record.id)
            ])
            if workorders_using_sla:
                raise ValidationError(_("Cannot delete SLA '%s' as it is being used by %d work order(s). Please reassign the work orders to a different SLA first.") % (record.name, len(workorders_using_sla)))
        
        return super().unlink()

