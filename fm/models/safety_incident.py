# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class SafetyIncident(models.Model):
    _name = 'facilities.safety.incident'
    _description = 'Safety Incident Reporting'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'incident_date desc, severity desc'

    name = fields.Char(
        string='Incident Title',
        required=True,
        tracking=True,
        help='Brief title of the incident'
    )
    
    incident_number = fields.Char(
        string='Incident Number',
        required=True,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
        help='Unique incident number'
    )
    
    incident_date = fields.Datetime(
        string='Incident Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help='Date and time when incident occurred'
    )
    
    reported_date = fields.Datetime(
        string='Reported Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help='Date and time when incident was reported'
    )
    
    # Incident Classification
    incident_type = fields.Selection([
        ('injury', 'Personal Injury'),
        ('near_miss', 'Near Miss'),
        ('property_damage', 'Property Damage'),
        ('environmental', 'Environmental Incident'),
        ('fire', 'Fire Incident'),
        ('chemical_spill', 'Chemical Spill'),
        ('equipment_failure', 'Equipment Failure'),
        ('security', 'Security Incident'),
        ('other', 'Other')
    ], string='Incident Type', required=True, tracking=True)
    
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Severity', required=True, default='medium', tracking=True)
    
    injury_type = fields.Selection([
        ('first_aid', 'First Aid'),
        ('medical_treatment', 'Medical Treatment'),
        ('lost_time', 'Lost Time Injury'),
        ('restricted_work', 'Restricted Work'),
        ('fatality', 'Fatality'),
        ('none', 'No Injury')
    ], string='Injury Type', help='Type of injury sustained')
    
    # Location Information
    facility_id = fields.Many2one(
        'facilities.facility',
        string='Facility',
        required=True,
        tracking=True,
        help='Facility where incident occurred'
    )
    
    building_id = fields.Many2one(
        'facilities.building',
        string='Building',
        help='Building where incident occurred'
    )
    
    floor_id = fields.Many2one(
        'facilities.floor',
        string='Floor',
        help='Floor where incident occurred'
    )
    
    room_id = fields.Many2one(
        'facilities.room',
        string='Room',
        help='Room where incident occurred'
    )
    
    location_description = fields.Text(
        string='Location Description',
        help='Detailed description of incident location'
    )
    
    # People Involved
    reporter_id = fields.Many2one(
        'res.users',
        string='Reported By',
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        help='Person who reported the incident'
    )
    
    injured_person_ids = fields.Many2many(
        'hr.employee',
        'incident_injured_person_rel',
        string='Injured Persons',
        help='Employees who were injured'
    )
    
    witness_ids = fields.Many2many(
        'hr.employee',
        'incident_witness_rel',
        string='Witnesses',
        help='Witnesses to the incident'
    )
    
    contractor_involved = fields.Boolean(
        string='Contractor Involved',
        help='Whether a contractor was involved'
    )
    
    contractor_name = fields.Char(
        string='Contractor Name',
        help='Name of the contractor involved'
    )
    
    # Incident Details
    description = fields.Html(
        string='Incident Description',
        required=True,
        help='Detailed description of what happened'
    )
    
    immediate_cause = fields.Html(
        string='Immediate Cause',
        help='Immediate cause of the incident'
    )
    
    contributing_factors = fields.Html(
        string='Contributing Factors',
        help='Factors that contributed to the incident'
    )
    
    weather_conditions = fields.Char(
        string='Weather Conditions',
        help='Weather conditions at time of incident'
    )
    
    lighting_conditions = fields.Selection([
        ('daylight', 'Daylight'),
        ('artificial', 'Artificial Light'),
        ('poor', 'Poor Lighting'),
        ('dark', 'Dark')
    ], string='Lighting Conditions', help='Lighting conditions')
    
    # Equipment/Asset Involved
    asset_ids = fields.Many2many(
        'facilities.asset',
        string='Assets Involved',
        help='Assets involved in the incident'
    )
    
    equipment_damage = fields.Boolean(
        string='Equipment Damage',
        help='Whether equipment was damaged'
    )
    
    damage_description = fields.Text(
        string='Damage Description',
        help='Description of equipment damage'
    )
    
    estimated_damage_cost = fields.Monetary(
        string='Estimated Damage Cost',
        currency_field='currency_id',
        help='Estimated cost of damage'
    )
    
    # Immediate Actions
    immediate_actions = fields.Html(
        string='Immediate Actions Taken',
        help='Actions taken immediately after the incident'
    )
    
    emergency_services_called = fields.Boolean(
        string='Emergency Services Called',
        help='Whether emergency services were called'
    )
    
    medical_attention_given = fields.Boolean(
        string='Medical Attention Given',
        help='Whether medical attention was provided'
    )
    
    area_secured = fields.Boolean(
        string='Area Secured',
        help='Whether the incident area was secured'
    )
    
    # Investigation
    investigation_required = fields.Boolean(
        string='Investigation Required',
        default=True,
        help='Whether formal investigation is required'
    )
    
    investigator_id = fields.Many2one(
        'res.users',
        string='Lead Investigator',
        help='Person leading the investigation'
    )
    
    investigation_team_ids = fields.Many2many(
        'res.users',
        'incident_investigation_team_rel',
        string='Investigation Team',
        help='Investigation team members'
    )
    
    investigation_start_date = fields.Date(
        string='Investigation Start Date',
        help='Date investigation started'
    )
    
    investigation_completion_date = fields.Date(
        string='Investigation Completion Date',
        help='Date investigation was completed'
    )
    
    root_cause_analysis = fields.Html(
        string='Root Cause Analysis',
        help='Root cause analysis findings'
    )
    
    # Corrective Actions
    corrective_action_ids = fields.One2many(
        'facilities.incident.corrective.action',
        'incident_id',
        string='Corrective Actions',
        help='Corrective actions from the incident'
    )
    
    # Status and Workflow
    state = fields.Selection([
        ('reported', 'Reported'),
        ('under_investigation', 'Under Investigation'),
        ('pending_actions', 'Pending Actions'),
        ('closed', 'Closed')
    ], string='Status', default='reported', tracking=True)
    
    # Regulatory Reporting
    regulatory_reporting_required = fields.Boolean(
        string='Regulatory Reporting Required',
        help='Whether incident must be reported to authorities'
    )
    
    regulatory_body = fields.Char(
        string='Regulatory Body',
        help='Regulatory body to report to'
    )
    
    regulatory_report_date = fields.Date(
        string='Regulatory Report Date',
        help='Date reported to regulatory body'
    )
    
    regulatory_reference = fields.Char(
        string='Regulatory Reference',
        help='Reference number from regulatory body'
    )
    
    # Documents and Evidence
    document_ids = fields.Many2many(
        'ir.attachment',
        string='Documents & Photos',
        help='Photos, documents, and other evidence'
    )
    
    # Cost Information
    medical_costs = fields.Monetary(
        string='Medical Costs',
        currency_field='currency_id',
        help='Medical treatment costs'
    )
    
    lost_time_cost = fields.Monetary(
        string='Lost Time Cost',
        currency_field='currency_id',
        help='Cost of lost work time'
    )
    
    repair_costs = fields.Monetary(
        string='Repair Costs',
        currency_field='currency_id',
        help='Equipment/property repair costs'
    )
    
    total_cost = fields.Monetary(
        string='Total Cost',
        currency_field='currency_id',
        compute='_compute_total_cost',
        store=True,
        help='Total incident cost'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # Lessons Learned
    lessons_learned = fields.Html(
        string='Lessons Learned',
        help='Lessons learned from the incident'
    )
    
    preventive_measures = fields.Html(
        string='Preventive Measures',
        help='Measures to prevent similar incidents'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('incident_number', _('New')) == _('New'):
                vals['incident_number'] = self.env['ir.sequence'].next_by_code('facilities.safety.incident') or _('New')
        return super().create(vals_list)
    
    @api.depends('medical_costs', 'lost_time_cost', 'repair_costs', 'estimated_damage_cost')
    def _compute_total_cost(self):
        for incident in self:
            incident.total_cost = (
                incident.medical_costs +
                incident.lost_time_cost +
                incident.repair_costs +
                incident.estimated_damage_cost
            )
    
    @api.constrains('incident_date', 'reported_date')
    def _check_dates(self):
        for incident in self:
            if incident.incident_date and incident.reported_date:
                if incident.incident_date > incident.reported_date:
                    raise ValidationError(_('Incident date cannot be after reported date.'))
    
    def action_start_investigation(self):
        """Start formal investigation"""
        if not self.investigator_id:
            raise UserError(_('Please assign a lead investigator before starting investigation.'))
        
        self.write({
            'state': 'under_investigation',
            'investigation_start_date': fields.Date.today()
        })
        self.message_post(body=_('Investigation started by %s') % self.investigator_id.name)
        
        # Create activity for investigation
        self.activity_schedule(
            'fm.mail_activity_incident_investigation',
            date_deadline=fields.Date.today() + timedelta(days=7),
            summary=_('Complete Incident Investigation'),
            note=_('Please complete investigation for incident: %s') % self.name,
            user_id=self.investigator_id.id
        )
    
    def action_complete_investigation(self):
        """Complete investigation and move to corrective actions"""
        if not self.root_cause_analysis:
            raise UserError(_('Please complete root cause analysis before finishing investigation.'))
        
        self.write({
            'state': 'pending_actions',
            'investigation_completion_date': fields.Date.today()
        })
        self.message_post(body=_('Investigation completed'))
        
        # Create activities for corrective actions
        for action in self.corrective_action_ids.filtered(lambda a: a.state == 'open'):
            action.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=action.target_date or fields.Date.today() + timedelta(days=30),
                summary=_('Complete Corrective Action'),
                note=_('Please complete corrective action: %s') % action.name,
                user_id=action.responsible_id.id
            )
    
    def action_close_incident(self):
        """Close the incident"""
        # Check if all corrective actions are completed
        open_actions = self.corrective_action_ids.filtered(lambda a: a.state != 'completed')
        if open_actions:
            raise UserError(_('Please complete all corrective actions before closing the incident.'))
        
        self.write({'state': 'closed'})
        self.message_post(body=_('Incident closed'))
    
    def action_create_corrective_action(self):
        """Create new corrective action"""
        return {
            'name': _('New Corrective Action'),
            'type': 'ir.actions.act_window',
            'res_model': 'facilities.incident.corrective.action',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_incident_id': self.id}
        }
    
    def action_regulatory_report(self):
        """Mark as reported to regulatory body"""
        self.write({
            'regulatory_report_date': fields.Date.today()
        })
        self.message_post(body=_('Incident reported to regulatory body'))
    
    @api.model
    def _cron_check_overdue_investigations(self):
        """Check for overdue investigations"""
        cutoff_date = fields.Date.today() - timedelta(days=7)
        overdue_incidents = self.search([
            ('state', '=', 'under_investigation'),
            ('investigation_start_date', '<', cutoff_date)
        ])
        
        for incident in overdue_incidents:
            incident.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=fields.Date.today(),
                summary=_('Overdue Investigation'),
                note=_('Investigation for incident %s is overdue') % incident.name,
                user_id=incident.investigator_id.id
            )


class IncidentCorrectiveAction(models.Model):
    _name = 'facilities.incident.corrective.action'
    _description = 'Incident Corrective Action'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, target_date'

    incident_id = fields.Many2one(
        'facilities.safety.incident',
        string='Incident',
        required=True,
        ondelete='cascade'
    )
    
    name = fields.Char(
        string='Action Description',
        required=True,
        tracking=True,
        help='Description of the corrective action'
    )
    
    action_type = fields.Selection([
        ('training', 'Training'),
        ('procedure_update', 'Procedure Update'),
        ('equipment_repair', 'Equipment Repair/Replacement'),
        ('engineering_control', 'Engineering Control'),
        ('administrative_control', 'Administrative Control'),
        ('ppe', 'Personal Protective Equipment'),
        ('signage', 'Warning Signs/Labels'),
        ('other', 'Other')
    ], string='Action Type', required=True)
    
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Priority', default='medium', tracking=True)
    
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsible Person',
        required=True,
        tracking=True,
        help='Person responsible for implementing this action'
    )
    
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        help='Department responsible for this action'
    )
    
    target_date = fields.Date(
        string='Target Completion Date',
        required=True,
        tracking=True,
        help='Target date for completion'
    )
    
    completion_date = fields.Date(
        string='Actual Completion Date',
        tracking=True,
        help='Actual completion date'
    )
    
    state = fields.Selection([
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue')
    ], string='Status', default='open', tracking=True)
    
    description = fields.Html(
        string='Detailed Description',
        help='Detailed description of the action'
    )
    
    implementation_notes = fields.Html(
        string='Implementation Notes',
        help='Notes on how the action was implemented'
    )
    
    cost = fields.Monetary(
        string='Estimated Cost',
        currency_field='currency_id',
        help='Estimated cost of implementing this action'
    )
    
    actual_cost = fields.Monetary(
        string='Actual Cost',
        currency_field='currency_id',
        help='Actual cost incurred'
    )
    
    currency_id = fields.Many2one(
        related='incident_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    # Verification
    verification_required = fields.Boolean(
        string='Verification Required',
        default=True,
        help='Whether verification is required'
    )
    
    verified_by = fields.Many2one(
        'res.users',
        string='Verified By',
        help='Person who verified the action'
    )
    
    verification_date = fields.Date(
        string='Verification Date',
        help='Date of verification'
    )
    
    verification_notes = fields.Text(
        string='Verification Notes',
        help='Notes from verification'
    )
    
    document_ids = fields.Many2many(
        'ir.attachment',
        string='Supporting Documents',
        help='Documents related to this action'
    )
    
    def action_start_progress(self):
        """Start working on action"""
        self.write({'state': 'in_progress'})
        self.message_post(body=_('Corrective action started'))
    
    def action_complete(self):
        """Complete the action"""
        if self.verification_required:
            # Create activity for verification
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=fields.Date.today() + timedelta(days=3),
                summary=_('Verify Corrective Action'),
                note=_('Please verify corrective action: %s') % self.name,
                user_id=self.incident_id.investigator_id.id or self.env.user.id
            )
        
        self.write({
            'state': 'completed',
            'completion_date': fields.Date.today()
        })
        self.message_post(body=_('Corrective action completed'))
    
    def action_verify(self):
        """Verify the corrective action"""
        self.write({
            'verified_by': self.env.user.id,
            'verification_date': fields.Date.today()
        })
        self.message_post(body=_('Corrective action verified by %s') % self.env.user.name)
    
    @api.model
    def _cron_check_overdue_actions(self):
        """Check for overdue corrective actions"""
        today = fields.Date.today()
        overdue_actions = self.search([
            ('state', 'in', ['open', 'in_progress']),
            ('target_date', '<', today)
        ])
        
        for action in overdue_actions:
            action.write({'state': 'overdue'})
            
            # Create activity for overdue action
            action.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=today,
                summary=_('Overdue Corrective Action'),
                note=_('Corrective action %s is overdue. Target date was %s.') % (
                    action.name, action.target_date
                ),
                user_id=action.responsible_id.id
            )


class SafetyStatistics(models.Model):
    _name = 'facilities.safety.statistics'
    _description = 'Safety Statistics'
    _order = 'period_start desc'

    name = fields.Char(
        string='Period Name',
        compute='_compute_name',
        store=True,
        help='Name of the statistics period'
    )
    
    period_start = fields.Date(
        string='Period Start',
        required=True,
        help='Start date of the statistics period'
    )
    
    period_end = fields.Date(
        string='Period End',
        required=True,
        help='End date of the statistics period'
    )
    
    period_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly')
    ], string='Period Type', required=True, default='monthly')
    
    # Incident Statistics
    total_incidents = fields.Integer(
        string='Total Incidents',
        compute='_compute_statistics',
        store=True,
        help='Total number of incidents'
    )
    
    injury_incidents = fields.Integer(
        string='Injury Incidents',
        compute='_compute_statistics',
        store=True,
        help='Number of injury incidents'
    )
    
    near_miss_incidents = fields.Integer(
        string='Near Miss Incidents',
        compute='_compute_statistics',
        store=True,
        help='Number of near miss incidents'
    )
    
    property_damage_incidents = fields.Integer(
        string='Property Damage Incidents',
        compute='_compute_statistics',
        store=True,
        help='Number of property damage incidents'
    )
    
    # Severity Statistics
    critical_incidents = fields.Integer(
        string='Critical Incidents',
        compute='_compute_statistics',
        store=True,
        help='Number of critical incidents'
    )
    
    high_severity_incidents = fields.Integer(
        string='High Severity Incidents',
        compute='_compute_statistics',
        store=True,
        help='Number of high severity incidents'
    )
    
    # Cost Statistics
    total_incident_cost = fields.Monetary(
        string='Total Incident Cost',
        currency_field='currency_id',
        compute='_compute_statistics',
        store=True,
        help='Total cost of all incidents'
    )
    
    average_incident_cost = fields.Monetary(
        string='Average Incident Cost',
        currency_field='currency_id',
        compute='_compute_statistics',
        store=True,
        help='Average cost per incident'
    )
    
    # Safety Performance Indicators
    ltir = fields.Float(
        string='Lost Time Injury Rate',
        compute='_compute_safety_kpis',
        store=True,
        help='Lost Time Injury Rate per 200,000 hours'
    )
    
    trir = fields.Float(
        string='Total Recordable Incident Rate',
        compute='_compute_safety_kpis',
        store=True,
        help='Total Recordable Incident Rate per 200,000 hours'
    )
    
    # Work Hours
    total_work_hours = fields.Float(
        string='Total Work Hours',
        help='Total work hours in the period'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    @api.depends('period_start', 'period_end', 'period_type')
    def _compute_name(self):
        for stat in self:
            if stat.period_start and stat.period_end:
                if stat.period_type == 'monthly':
                    stat.name = stat.period_start.strftime('%B %Y')
                elif stat.period_type == 'quarterly':
                    quarter = (stat.period_start.month - 1) // 3 + 1
                    stat.name = f'Q{quarter} {stat.period_start.year}'
                else:
                    stat.name = str(stat.period_start.year)
            else:
                stat.name = 'Safety Statistics'
    
    @api.depends('period_start', 'period_end')
    def _compute_statistics(self):
        for stat in self:
            if not stat.period_start or not stat.period_end:
                continue
            
            # Get incidents in the period
            incidents = self.env['facilities.safety.incident'].search([
                ('incident_date', '>=', stat.period_start),
                ('incident_date', '<=', stat.period_end),
                ('company_id', '=', stat.company_id.id)
            ])
            
            stat.total_incidents = len(incidents)
            stat.injury_incidents = len(incidents.filtered(lambda i: i.incident_type == 'injury'))
            stat.near_miss_incidents = len(incidents.filtered(lambda i: i.incident_type == 'near_miss'))
            stat.property_damage_incidents = len(incidents.filtered(lambda i: i.incident_type == 'property_damage'))
            stat.critical_incidents = len(incidents.filtered(lambda i: i.severity == 'critical'))
            stat.high_severity_incidents = len(incidents.filtered(lambda i: i.severity == 'high'))
            
            stat.total_incident_cost = sum(incidents.mapped('total_cost'))
            if stat.total_incidents:
                stat.average_incident_cost = stat.total_incident_cost / stat.total_incidents
            else:
                stat.average_incident_cost = 0
    
    @api.depends('total_incidents', 'injury_incidents', 'total_work_hours')
    def _compute_safety_kpis(self):
        for stat in self:
            if stat.total_work_hours:
                # Calculate rates per 200,000 hours (standard)
                stat.ltir = (stat.injury_incidents * 200000) / stat.total_work_hours
                stat.trir = (stat.total_incidents * 200000) / stat.total_work_hours
            else:
                stat.ltir = 0
                stat.trir = 0
    
    @api.model
    def generate_monthly_statistics(self, year, month):
        """Generate monthly safety statistics"""
        from datetime import date
        from calendar import monthrange
        
        start_date = date(year, month, 1)
        end_date = date(year, month, monthrange(year, month)[1])
        
        existing = self.search([
            ('period_start', '=', start_date),
            ('period_end', '=', end_date),
            ('period_type', '=', 'monthly')
        ])
        
        if existing:
            return existing
        
        return self.create({
            'period_start': start_date,
            'period_end': end_date,
            'period_type': 'monthly',
            'total_work_hours': 0  # This should be calculated from HR records
        })
    
    @api.constrains('severity')
    def _check_severity_escalation_requirements(self):
        """Ensure high severity incidents have required fields."""
        for incident in self:
            if incident.severity in ['high', 'critical']:
                if not incident.investigator_id:
                    raise ValidationError(_("High and critical severity incidents must have an assigned investigator."))
                if not incident.reported_by_id:
                    raise ValidationError(_("High and critical severity incidents must have a reporter assigned."))
    
    @api.constrains('estimated_damage_cost', 'repair_costs', 'lost_time_cost')
    def _check_incident_costs(self):
        """Validate incident cost amounts."""
        for incident in self:
            if incident.estimated_damage_cost and incident.estimated_damage_cost < 0:
                raise ValidationError(_("Estimated damage cost cannot be negative."))
            if incident.repair_costs and incident.repair_costs < 0:
                raise ValidationError(_("Repair costs cannot be negative."))
            if incident.lost_time_cost and incident.lost_time_cost < 0:
                raise ValidationError(_("Lost time cost cannot be negative."))
    
    @api.constrains('state', 'investigation_start_date', 'resolution_date')
    def _check_investigation_timeline(self):
        """Validate investigation timeline makes sense."""
        for incident in self:
            if incident.state == 'under_investigation' and not incident.investigation_start_date:
                raise ValidationError(_("Investigation start date is required for incidents under investigation."))
            
            if incident.state == 'closed' and not incident.resolution_date:
                raise ValidationError(_("Resolution date is required for closed incidents."))
            
            if incident.investigation_start_date and incident.resolution_date:
                if incident.investigation_start_date > incident.resolution_date:
                    raise ValidationError(_("Investigation start date cannot be after resolution date."))
    
    @api.constrains('incident_type', 'description')
    def _check_incident_details(self):
        """Ensure adequate incident documentation."""
        for incident in self:
            if incident.severity in ['high', 'critical'] and not incident.description:
                raise ValidationError(_("High and critical severity incidents must have a detailed description."))
            
            if incident.incident_type == 'injury' and not incident.injured_person_name:
                raise ValidationError(_("Injury incidents must specify the injured person's name."))
    
    @api.constrains('incident_date')
    def _check_incident_date_reasonable(self):
        """Validate incident date is not too far in the past or future."""
        from datetime import date, timedelta
        for incident in self:
            if incident.incident_date:
                today = date.today()
                # Allow incidents up to 1 year in the past
                if incident.incident_date < today - timedelta(days=365):
                    raise ValidationError(_("Incident date cannot be more than 1 year in the past."))
                # Don't allow future incidents (except today)
                if incident.incident_date > today:
                    raise ValidationError(_("Incident date cannot be in the future."))